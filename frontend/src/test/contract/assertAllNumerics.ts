/**
 * Recursively traverse a mock payload looking for sub-objects that claim to
 * be a ``Numeric`` (structural hint: having every one of ``raw``, ``unit``,
 * ``display``, ``precision``, ``sign_aware`` keys) and assert they all pass
 * ``isNumeric``.
 *
 * Used by mock ↔ schema contract tests. Wave 2/3 will wire mockClient
 * methods into this helper as they upgrade their payload shapes.
 */
import { expect } from "vitest";

import { isNumeric } from "../../api/numeric";

const NUMERIC_KEYS = ["raw", "unit", "display", "precision", "sign_aware"] as const;

function looksLikeNumeric(value: unknown): boolean {
  if (value === null || typeof value !== "object") return false;
  const obj = value as Record<string, unknown>;
  return NUMERIC_KEYS.every((k) => k in obj);
}

/**
 * Walk ``payload`` depth-first; at every node that structurally "looks like"
 * a Numeric, assert that ``isNumeric`` returns true. Non-Numeric-looking
 * nodes are recursed into (for arrays and plain objects).
 *
 * Path reporting gives you exact dotted path for failing nodes:
 *   e.g. "root.metrics[2].value"
 */
export function assertAllNumerics(payload: unknown, rootPath = "root"): void {
  walk(payload, rootPath);
}

function walk(node: unknown, path: string): void {
  if (node === null || node === undefined) return;

  if (looksLikeNumeric(node)) {
    const ok = isNumeric(node);
    expect(
      ok,
      `Expected Numeric-shaped node at ${path} to pass isNumeric() but it did not: ${safeStringify(node)}`,
    ).toBe(true);
    return;
  }

  if (Array.isArray(node)) {
    node.forEach((item, idx) => walk(item, `${path}[${idx}]`));
    return;
  }

  if (typeof node === "object") {
    for (const [key, value] of Object.entries(node as Record<string, unknown>)) {
      walk(value, `${path}.${key}`);
    }
  }
  // primitives: nothing to assert
}

function safeStringify(value: unknown): string {
  try {
    return JSON.stringify(value).slice(0, 200);
  } catch {
    return "[unserializable]";
  }
}
