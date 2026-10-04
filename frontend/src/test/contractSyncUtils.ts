/**
 * 前后端契约防漂移测试的共享解析辅助（测试基础设施，非生产代码）。
 *
 * 从 `AgentContractSync.test.ts`（Wave1 F04）抽取的机制原样复用，供 Wave3 F08
 * 新增的 balance / pnl / positions 契约同步测试共享，避免每个测试文件各自维护
 * 一份同构的正则解析逻辑。`AgentContractSync.test.ts` 本身不做修改（本任务只
 * 新增测试文件），因此这里的实现与其保持逐字一致。
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect } from "vitest";

/** 读取仓库内任意相对路径的后端源文件（相对仓库根目录，如 `backend/app/schemas/pnl.py`）。 */
export function readBackendFile(relativePathFromRepoRoot: string): string {
  return readFileSync(resolve(process.cwd(), "..", relativePathFromRepoRoot), "utf8");
}

/** 解析一个 Pydantic 模型类体内声明的字段名（4 空格缩进的 `name: annotation` 行）。 */
export function parsePydanticModelFields(source: string, className: string): string[] {
  const classStart = source.indexOf(`class ${className}(`);
  if (classStart < 0) {
    throw new Error(`backend schema is missing class ${className}`);
  }
  const rest = source.slice(classStart);
  const nextClassOffset = rest.slice(1).search(/\r?\nclass /);
  const block = nextClassOffset >= 0 ? rest.slice(0, nextClassOffset + 1) : rest;
  const fields: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    const match = /^ {4}([a-z_][a-zA-Z0-9_]*):/.exec(line);
    if (match && match[1] !== "model_config") {
      fields.push(match[1]);
    }
  }
  return fields;
}

/** 解析模块级 `Symbol = Literal[...]` 的取值列表。 */
export function parseLiteralValues(source: string, symbol: string): string[] {
  const match = new RegExp(`${symbol} = Literal\\[([^\\]]*)\\]`).exec(source);
  if (!match) {
    throw new Error(`backend schema is missing Literal ${symbol}`);
  }
  return [...match[1].matchAll(/"([^"]+)"/g)].map((entry) => entry[1]);
}

/** 解析类体内某个字段标注中的行内 `Literal["a", "b", ...]` 取值列表（字段级，非模块级）。 */
export function parseFieldLiteralValues(
  source: string,
  className: string,
  fieldName: string,
): string[] {
  const specs = parsePydanticModelFieldAnnotations(source, className);
  const annotation = specs[fieldName];
  if (annotation === undefined) {
    throw new Error(`backend model ${className} is missing field ${fieldName}`);
  }
  const match = /Literal\[([^\]]*)\]/.exec(annotation);
  if (!match) {
    throw new Error(`backend model ${className}.${fieldName} has no inline Literal[...] annotation`);
  }
  return [...match[1].matchAll(/"([^"]+)"/g)].map((entry) => entry[1]);
}

function parsePydanticModelFieldAnnotations(
  source: string,
  className: string,
): Record<string, string> {
  const classStart = source.indexOf(`class ${className}(`);
  if (classStart < 0) {
    throw new Error(`backend schema is missing class ${className}`);
  }
  const rest = source.slice(classStart);
  const nextClassOffset = rest.slice(1).search(/\r?\nclass /);
  const block = nextClassOffset >= 0 ? rest.slice(0, nextClassOffset + 1) : rest;
  const annotations: Record<string, string> = {};
  for (const line of block.split(/\r?\n/)) {
    const match = /^ {4}([a-z_][a-zA-Z0-9_]*):\s*([^=]+?)\s*(?:=\s*(.+?)\s*)?$/.exec(line);
    if (!match || match[1] === "model_config") {
      continue;
    }
    annotations[match[1]] = match[2];
  }
  return annotations;
}

export type PydanticFieldSpec = {
  /** 类型标注含 `| None` 或 `Optional[...]`：正常序列化（无 `exclude_none`）会显式输出 null。 */
  nullable: boolean;
  hasDefault: boolean;
  /** 默认值字面量原文（如 `"warning"`、`None`、`True`）；无默认值时为 null。 */
  defaultLiteral: string | null;
};

/**
 * 解析一个 Pydantic 模型类体内声明字段的可空性、是否有默认值及默认值字面量。
 * 与 parsePydanticModelFields 共用同一类体范围，但额外读取类型标注和默认值，
 * 用于捕获"字段名一致但可空性/默认值漂移"。
 */
export function parsePydanticModelFieldSpecs(
  source: string,
  className: string,
): Record<string, PydanticFieldSpec> {
  const classStart = source.indexOf(`class ${className}(`);
  if (classStart < 0) {
    throw new Error(`backend schema is missing class ${className}`);
  }
  const rest = source.slice(classStart);
  const nextClassOffset = rest.slice(1).search(/\r?\nclass /);
  const block = nextClassOffset >= 0 ? rest.slice(0, nextClassOffset + 1) : rest;
  const specs: Record<string, PydanticFieldSpec> = {};
  for (const line of block.split(/\r?\n/)) {
    const match = /^ {4}([a-z_][a-zA-Z0-9_]*):\s*([^=]+?)\s*(?:=\s*(.+?)\s*)?$/.exec(line);
    if (!match || match[1] === "model_config") {
      continue;
    }
    const [, name, annotation, defaultLiteral] = match;
    specs[name] = {
      nullable: /\bNone\b/.test(annotation) || /\bOptional\[/.test(annotation),
      hasDefault: defaultLiteral !== undefined,
      defaultLiteral: defaultLiteral ?? null,
    };
  }
  return specs;
}

/** 断言：后端该模型"可空字段"的集合与期望清单完全一致（多、少、拼错均失败）。 */
export function expectNullableFieldParity(
  source: string,
  className: string,
  expectedNullableFields: string[],
) {
  const specs = parsePydanticModelFieldSpecs(source, className);
  const actualNullable = Object.entries(specs)
    .filter(([, spec]) => spec.nullable)
    .map(([name]) => name)
    .sort();
  expect(actualNullable).toEqual([...expectedNullableFields].sort());
}

/** 断言：后端该模型"有默认值字段"的集合与期望清单完全一致（用于必填/可选 parity）。 */
export function expectOptionalFieldParity(
  source: string,
  className: string,
  expectedOptionalFields: string[],
) {
  const specs = parsePydanticModelFieldSpecs(source, className);
  const actualOptional = Object.entries(specs)
    .filter(([, spec]) => spec.hasDefault)
    .map(([name]) => name)
    .sort();
  expect(actualOptional).toEqual([...expectedOptionalFields].sort());
}

/** 断言：指定字段的后端默认值字面量与期望一致（防止治理默认口径静默漂移）。 */
export function expectFieldDefaultParity(
  source: string,
  className: string,
  expectedDefaults: Record<string, string>,
) {
  const specs = parsePydanticModelFieldSpecs(source, className);
  for (const [field, expectedDefault] of Object.entries(expectedDefaults)) {
    expect(specs[field]?.defaultLiteral, `${className}.${field} default`).toBe(expectedDefault);
  }
}

/** 断言：后端模型字段名集合与前端契约字段清单完全一致（多、少、拼错均失败）。 */
export function expectFieldParity(
  source: string,
  className: string,
  contractFields: Record<string, true>,
) {
  expect(parsePydanticModelFields(source, className).sort()).toEqual(
    Object.keys(contractFields).sort(),
  );
}
