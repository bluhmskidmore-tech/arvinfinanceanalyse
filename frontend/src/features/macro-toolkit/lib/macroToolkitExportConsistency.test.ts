import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import * as crisisSupport from "./macroToolkitCrisisSupport";

// Regression guard for the "used-but-not-exported / used-but-not-destructured" crash class
// (see commits 75bf12d48 / 0b39b53e4): Vitest's transform does not enforce ESM named-export
// bindings the way Vite dev/browser does, so a missing export or a helper missing from the
// big `const { ... } = crisisSupport;` destructure crashes the page while tests stay green.

const panelSource = readFileSync(
  path.resolve("src/features/macro-toolkit/panels/MacroToolkitCrisisPanels.tsx"),
  "utf8",
);
const pageSource = readFileSync(
  path.resolve("src/features/macro-toolkit/pages/MacroToolkitPage.tsx"),
  "utf8",
);

const runtimeExportNames = Object.keys(crisisSupport);

type DestructureSpecifier = {
  /** Property name on the crisisSupport namespace. */
  exportedName: string;
  /** Local binding name used in the panel body (differs only for `a: b` aliases). */
  localName: string;
};

function parseCrisisSupportDestructure(source: string): {
  specifiers: DestructureSpecifier[];
  bodyAfterDestructure: string;
} {
  const match = /const\s*\{([^}]+)\}\s*=\s*crisisSupport;/.exec(source);
  if (!match || match.index === undefined) {
    throw new Error(
      "Could not find `const { ... } = crisisSupport;` in MacroToolkitCrisisPanels.tsx; update this guard test if the destructure pattern changed.",
    );
  }
  const specifiers = match[1]
    .split(",")
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0 && !entry.startsWith("..."))
    .map((entry) => {
      const [exportedName, localName] = entry.split(":").map((part) => part.trim());
      return { exportedName, localName: localName ?? exportedName };
    });
  return {
    specifiers,
    bodyAfterDestructure: source.slice(match.index + match[0].length),
  };
}

/**
 * Strips string literals, template literals, comments, and `crisisSupport.foo`
 * qualified usages so the bare-identifier scan below does not produce false
 * positives from prose, JSX text, or namespace-qualified (often type-only) access.
 */
function sanitizeForIdentifierScan(source: string): string {
  return source
    .replace(/`(?:[^`\\]|\\.)*`/g, '""')
    .replace(/"(?:[^"\\\n]|\\.)*"/g, '""')
    .replace(/'(?:[^'\\\n]|\\.)*'/g, '""')
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\/\/[^\n]*/g, "")
    .replace(/crisisSupport\s*\.\s*[A-Za-z_$][\w$]*/g, "");
}

/**
 * True when `name` appears as a bare identifier: not preceded by `.` (member
 * access), not part of a longer identifier, and not used as an object key /
 * label (`name:`).
 */
function usesBareIdentifier(sanitizedSource: string, name: string): boolean {
  const pattern = new RegExp(`(?<![.\\w$])${name}\\b(?!\\s*:)`);
  return pattern.test(sanitizedSource);
}

function parseValueImportsFromCrisisSupport(source: string): string[] {
  const importPattern = /import\s+(type\s+)?\{([^}]+)\}\s*from\s*["']\.\.\/lib\/macroToolkitCrisisSupport["']/g;
  const names: string[] = [];
  for (const match of source.matchAll(importPattern)) {
    if (match[1]) continue; // `import type { ... }` is erased at runtime
    for (const entry of match[2].split(",")) {
      const trimmed = entry.trim();
      if (!trimmed || trimmed.startsWith("type ")) continue;
      // `exported as local` — the exported name is what must exist at runtime.
      names.push(trimmed.split(/\s+as\s+/)[0].trim());
    }
  }
  return names;
}

describe("macroToolkitCrisisSupport export/destructure consistency", () => {
  const { specifiers, bodyAfterDestructure } = parseCrisisSupportDestructure(panelSource);

  it("finds a non-empty destructure list in MacroToolkitCrisisPanels.tsx", () => {
    expect(specifiers.length).toBeGreaterThan(0);
  });

  it("every name destructured from crisisSupport is a defined runtime export", () => {
    const missing = specifiers
      .map((specifier) => specifier.exportedName)
      .filter((name) => typeof (crisisSupport as Record<string, unknown>)[name] === "undefined");
    expect(missing, `destructured from crisisSupport but not exported (or type-only): ${missing.join(", ")}`).toEqual([]);
  });

  it("every runtime export used in the panel body is present in the destructure list", () => {
    const destructuredLocals = new Set(specifiers.map((specifier) => specifier.localName));
    const sanitizedBody = sanitizeForIdentifierScan(bodyAfterDestructure);
    const usedButNotDestructured = runtimeExportNames.filter(
      (name) => !destructuredLocals.has(name) && usesBareIdentifier(sanitizedBody, name),
    );
    expect(
      usedButNotDestructured,
      `used in MacroToolkitCrisisPanels.tsx body but missing from the crisisSupport destructure: ${usedButNotDestructured.join(", ")}`,
    ).toEqual([]);
  });

  it("every named value import in MacroToolkitPage.tsx resolves to a defined runtime export", () => {
    const importedNames = parseValueImportsFromCrisisSupport(pageSource);
    expect(importedNames.length).toBeGreaterThan(0);
    const missing = importedNames.filter(
      (name) => typeof (crisisSupport as Record<string, unknown>)[name] === "undefined",
    );
    expect(missing, `imported by MacroToolkitPage.tsx but not exported at runtime: ${missing.join(", ")}`).toEqual([]);
  });
});
