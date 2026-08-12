import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { join, relative, resolve } from "node:path";

/**
 * 生产代码 `as unknown as` 双跳强转守卫。
 *
 * 双跳强转会同时绕过结构检查与可赋值性检查，属于类型债。生产代码应改用：
 * - 窄类型收敛（类型别名单跳、泛型实例化赋值、显式注解）；
 * - 边界处最小运行时检查（关键字段存在性校验，失败走既有空态/错误态并 console.error 披露）。
 *
 * 白名单：经评审确需保留的生产文件按「相对 src 的 posix 路径 -> 允许计数」显式登记，
 * 计数必须精确匹配（新增超出或清理后残留旧登记都会失败），保证基线只降不升。
 */
const WHITELIST: Record<string, number> = {};

const CAST_PATTERN = /as unknown as/g;
const SOURCE_FILE_PATTERN = /\.(ts|tsx)$/;
const TEST_FILE_PATTERN = /\.test\.[jt]sx?$/;
const EXCLUDED_DIR_SEGMENTS = new Set(["test", "mocks"]);

function collectProductionSourceFiles(dir: string, acc: string[]): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (EXCLUDED_DIR_SEGMENTS.has(entry.name)) continue;
      collectProductionSourceFiles(fullPath, acc);
      continue;
    }
    if (!SOURCE_FILE_PATTERN.test(entry.name) || TEST_FILE_PATTERN.test(entry.name)) continue;
    acc.push(fullPath);
  }
  return acc;
}

describe("production `as unknown as` guard", () => {
  it("keeps double casts in production sources within the explicit whitelist", () => {
    const srcRoot = resolve(process.cwd(), "src");
    const files = collectProductionSourceFiles(srcRoot, []);
    expect(files.length).toBeGreaterThan(100);

    const actualCounts = new Map<string, number>();
    for (const file of files) {
      const count = (readFileSync(file, "utf8").match(CAST_PATTERN) ?? []).length;
      if (count === 0) continue;
      actualCounts.set(relative(srcRoot, file).replaceAll("\\", "/"), count);
    }

    const violations: string[] = [];
    for (const [file, count] of [...actualCounts.entries()].sort()) {
      const allowed = WHITELIST[file] ?? 0;
      if (count !== allowed) {
        violations.push(`${file}: 实际 ${count} 处，白名单允许 ${allowed} 处`);
      }
    }
    for (const [file, allowed] of Object.entries(WHITELIST)) {
      if (!actualCounts.has(file)) {
        violations.push(`${file}: 白名单登记 ${allowed} 处，但文件已无双跳强转，请移除过期登记`);
      }
    }

    expect(
      violations,
      `生产代码 \`as unknown as\` 与白名单不一致：\n${violations.join("\n")}\n` +
        "请优先用窄类型收敛 + 关键字段运行时检查消除；确需保留时在本文件 WHITELIST 显式登记并说明理由。",
    ).toEqual([]);
  });
});
