import fs from "node:fs";
import path from "node:path";

import ts from "typescript";
import { describe, expect, it } from "vitest";

import {
  isNumeric,
  normalizeNumeric,
  numericChartNumberOrNull,
  numericDecimalOrNull,
  numericExactTextOrNull,
  parseNumeric,
} from "./numeric";

function numericPayload(raw: number | null, rawText?: string | null) {
  return {
    raw,
    raw_text: rawText,
    unit: "yuan" as const,
    display: rawText ?? (raw === null ? "—" : String(raw)),
    precision: 8,
    sign_aware: false,
  };
}

function findForbiddenRawTextNumberCasts(source: string): string[] {
  const sourceFile = ts.createSourceFile("policy-guard.ts", source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const offenders: string[] = [];

  const visit = (node: ts.Node) => {
    if (ts.isPrefixUnaryExpression(node) && node.operator === ts.SyntaxKind.PlusToken && isRawTextReference(node.operand)) {
      offenders.push(`+${node.operand.getText(sourceFile)}`);
    }

    if (ts.isCallExpression(node) && node.arguments.length === 1 && isRawTextReference(node.arguments[0])) {
      const callee = node.expression.getText(sourceFile);
      if (callee === "Number" || callee === "parseFloat" || callee === "Number.parseFloat") {
        offenders.push(`${callee}(${node.arguments[0].getText(sourceFile)})`);
      }
    }

    ts.forEachChild(node, visit);
  };

  visit(sourceFile);
  return offenders;
}

function isRawTextReference(node: ts.Expression): boolean {
  if (ts.isIdentifier(node)) {
    return node.text === "raw_text" || node.text === "rawText";
  }
  if (ts.isPropertyAccessExpression(node)) {
    return node.name.text === "raw_text" || node.name.text === "rawText";
  }
  if (ts.isElementAccessExpression(node) && ts.isStringLiteral(node.argumentExpression)) {
    return node.argumentExpression.text === "raw_text" || node.argumentExpression.text === "rawText";
  }
  return false;
}

describe("normalizeNumeric", () => {
  it("keeps backend raw unchanged when a governed Numeric also carries raw_text", () => {
    const value = numericPayload(Number("9007199254740993.00005"), "9007199254740993.00005");

    const normalized = normalizeNumeric(value, "yuan", false, 8);

    expect(normalized).toBe(value);
    expect(normalized.raw).toBe(Number("9007199254740993.00005"));
    expect(normalized.raw_text).toBe("9007199254740993.00005");
  });

  it("preserves plain decimal string raw_text while keeping raw as an approximate compatibility number", () => {
    const normalized = normalizeNumeric("12345678901234567890.12345678901234567890", "yuan", false, 8);

    expect(normalized.raw_text).toBe("12345678901234567890.12345678901234567890");
    expect(normalized.raw).toBe(Number("12345678901234567890.12345678901234567890"));
  });

  it("preserves trailing zeros, negative values, and zero in accepted plain decimal strings", () => {
    expect(normalizeNumeric("12.3400", "yuan", false).raw_text).toBe("12.3400");
    expect(normalizeNumeric("-42.500", "yuan", false).raw_text).toBe("-42.500");
    expect(normalizeNumeric("0", "yuan", false).raw_text).toBe("0");
    expect(normalizeNumeric("-0.0000", "yuan", false).raw_text).toBe("-0.0000");
  });

  it("trims outer whitespace at the normalization boundary and keeps canonical exact text", () => {
    const normalized = normalizeNumeric("  -12.500  ", "bp", true, 2);

    expect(normalized.raw_text).toBe("-12.500");
    expect(normalized.raw).toBe(-12.5);
    expect(normalized.display).toBe("-12.50 bp");
  });

  it("treats null, empty, invalid tokens, scientific notation, and unsupported decimal shapes as missing", () => {
    for (const value of [null, "", "   ", "abc", "12abc", "1e5", "+1", ".5", "5.", "1 2.5"]) {
      const normalized = normalizeNumeric(value, "yuan", false);
      expect(normalized.raw).toBeNull();
      expect(normalized.raw_text).toBeUndefined();
    }
  });

  it("treats NaN and Infinity number inputs as missing", () => {
    expect(normalizeNumeric(Number.NaN, "yuan", false).raw).toBeNull();
    expect(normalizeNumeric(Number.POSITIVE_INFINITY, "yuan", false).raw).toBeNull();
    expect(normalizeNumeric(Number.NEGATIVE_INFINITY, "yuan", false).raw).toBeNull();
  });
});

describe("numericExactTextOrNull", () => {
  it("returns the authoritative raw_text from governed Numeric values", () => {
    expect(numericExactTextOrNull(numericPayload(1.25, "9007199254740993.00005"))).toBe("9007199254740993.00005");
  });

  it("accepts only plain decimal strings without trimming or exponent widening", () => {
    expect(numericExactTextOrNull("-0.0001200")).toBe("-0.0001200");
    expect(numericExactTextOrNull("  -0.0001200  ")).toBeNull();
    expect(numericExactTextOrNull("+1")).toBeNull();
    expect(numericExactTextOrNull(".5")).toBeNull();
    expect(numericExactTextOrNull("5.")).toBeNull();
  });

  it("rejects missing values, invalid tokens, and scientific notation", () => {
    expect(numericExactTextOrNull(null)).toBeNull();
    expect(numericExactTextOrNull("")).toBeNull();
    expect(numericExactTextOrNull("NaN")).toBeNull();
    expect(numericExactTextOrNull("Infinity")).toBeNull();
    expect(numericExactTextOrNull("1e6")).toBeNull();
  });
});

describe("numericDecimalOrNull", () => {
  it("prefers raw_text over approximate raw for explicit decimal comparisons", () => {
    const decimal = numericDecimalOrNull(numericPayload(9007199254740992, "9007199254740993.00005"));

    expect(decimal?.toFixed()).toBe("9007199254740993.00005");
  });

  it("preserves exact text through a neutral plus operation", () => {
    const decimal = numericDecimalOrNull(numericPayload(9007199254740992, "9007199254740993.00005"));

    expect(decimal?.plus(0).toFixed()).toBe("9007199254740993.00005");
  });

  it("preserves exact text through a neutral times operation", () => {
    const decimal = numericDecimalOrNull(numericPayload(9007199254740992, "9007199254740993.00005"));

    expect(decimal?.times(1).toFixed()).toBe("9007199254740993.00005");
  });

  it("preserves very long decimal text through neutral arithmetic", () => {
    const exact = "1234567890123456789012345678901234567890.1234567890123456789012345678901234567890";
    const decimal = numericDecimalOrNull(exact);
    const scale = exact.split(".")[1]?.length ?? 0;

    expect(decimal?.plus(0).toFixed(scale)).toBe(exact);
    expect(decimal?.times(1).toFixed(scale)).toBe(exact);
  });

  it("does not treat approximate governed raw as exact precision when raw_text is absent", () => {
    const decimal = numericDecimalOrNull(numericPayload(-42.5));

    expect(decimal).toBeNull();
  });

  it("does not treat governed Numeric with null raw and raw_text as exact", () => {
    const decimal = numericDecimalOrNull(numericPayload(null, "1.2500"));

    expect(decimal).toBeNull();
  });

  it("returns null for missing, invalid, and non-finite values", () => {
    expect(numericDecimalOrNull("1e5")).toBeNull();
    expect(numericDecimalOrNull("oops")).toBeNull();
    expect(numericDecimalOrNull(12.5)).toBeNull();
    expect(numericDecimalOrNull(Number.POSITIVE_INFINITY)).toBeNull();
    expect(numericDecimalOrNull(undefined)).toBeNull();
  });
});

describe("numericChartNumberOrNull", () => {
  it("converts accepted exact decimal text into a finite chart number", () => {
    expect(numericChartNumberOrNull("9007199254740993.00005")).toBe(Number("9007199254740993.00005"));
    expect(numericChartNumberOrNull("-12.3400")).toBe(-12.34);
  });

  it("falls back to finite approximate raw and number inputs for legacy chart compatibility", () => {
    expect(numericChartNumberOrNull(numericPayload(-42.5))).toBe(-42.5);
    expect(numericChartNumberOrNull(12.5)).toBe(12.5);
  });

  it("returns null for missing, invalid, scientific, and overflowing values", () => {
    expect(numericChartNumberOrNull("")).toBeNull();
    expect(numericChartNumberOrNull("1e9")).toBeNull();
    expect(numericChartNumberOrNull("not-a-number")).toBeNull();
    expect(numericChartNumberOrNull("9".repeat(400))).toBeNull();
  });
});

describe("parseNumeric", () => {
  it("accepts governed Numeric values that carry raw_text", () => {
    expect(parseNumeric(numericPayload(1.25, "1.2500")).raw_text).toBe("1.2500");
  });
});

describe("isNumeric", () => {
  it("rejects governed Numeric when raw_text is present but raw is null", () => {
    expect(isNumeric(numericPayload(null, "1.2500"))).toBe(false);
  });

  it("rejects governed Numeric when raw_text is not a plain decimal string", () => {
    expect(isNumeric(numericPayload(1.25, "1e5"))).toBe(false);
    expect(isNumeric(numericPayload(1.25, " 1.25 "))).toBe(false);
    expect(isNumeric(numericPayload(1.25, "+1"))).toBe(false);
    expect(isNumeric(numericPayload(1.25, ".5"))).toBe(false);
    expect(isNumeric(numericPayload(1.25, "5."))).toBe(false);
  });

  it("accepts governed Numeric when raw_text is a plain decimal string including signed zero", () => {
    expect(isNumeric(numericPayload(-0, "-0.0000"))).toBe(true);
  });
});

describe("numeric exact-text policy guard", () => {
  it("finds direct raw_text-to-number casts in code while ignoring comments and strings", () => {
    const source = `
      const raw_text = "1.25";
      const rawText = "2.5";
      const obj = { raw_text, rawText };
      const ignored = "Number(raw_text) parseFloat(rawText) +raw_text";
      // Number(raw_text)
      Number(raw_text);
      parseFloat(rawText);
      Number.parseFloat(obj.raw_text);
      +obj["rawText"];
    `;

    expect(findForbiddenRawTextNumberCasts(source)).toEqual([
      "Number(raw_text)",
      "parseFloat(rawText)",
      "Number.parseFloat(obj.raw_text)",
      '+obj["rawText"]',
    ]);
  });

  it("does not flag safe exact-text handling paths", () => {
    const source = `
      const exact = numericExactTextOrNull(raw_text);
      const decimal = exact === null ? null : new Decimal(exact);
      const chart = numericChartNumberOrNull(rawText);
      const labeled = "obj.raw_text should stay as text";
      // +obj.raw_text
      exact?.localeCompare("0");
    `;

    expect(findForbiddenRawTextNumberCasts(source)).toEqual([]);
  });

  it("keeps production api code free of direct raw_text number coercions", () => {
    const apiDir = path.resolve(import.meta.dirname, ".");
    const offenders: string[] = [];

    const scan = (dir: string) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        if (entry.name.endsWith(".test.ts") || entry.name.endsWith(".test.tsx")) continue;
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          scan(fullPath);
          continue;
        }
        if (!fullPath.endsWith(".ts") && !fullPath.endsWith(".tsx")) continue;
        const source = fs.readFileSync(fullPath, "utf8");
        const fileOffenders = findForbiddenRawTextNumberCasts(source);
        if (fileOffenders.length > 0) {
          offenders.push(`${path.relative(apiDir, fullPath)} => ${fileOffenders.join(", ")}`);
        }
      }
    };

    scan(apiDir);
    expect(offenders).toEqual([]);
  });
});
