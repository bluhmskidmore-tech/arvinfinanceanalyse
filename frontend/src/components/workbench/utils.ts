import type { ReactNode } from "react";
import type { ResultMetaLike, WorkbenchTone } from "./types";

export function cx(...tokens: Array<string | false | null | undefined>): string {
  return tokens.filter(Boolean).join(" ");
}

export function toneClass(prefix: string, tone?: WorkbenchTone): string {
  return `${prefix}--${tone ?? "neutral"}`;
}

export function tagColorForTone(tone?: WorkbenchTone): string | undefined {
  if (!tone || tone === "neutral") return undefined;
  if (tone === "success") return "green";
  if (tone === "warning") return "gold";
  if (tone === "danger") return "red";
  if (tone === "accent") return "purple";
  return "blue";
}

export function renderValue(value: ReactNode, fallback: ReactNode = "--"): ReactNode {
  return value === null || value === undefined || value === "" ? fallback : value;
}

export function pickMeta(meta: ResultMetaLike, keys: string[]): unknown {
  if (!meta) return undefined;
  for (const key of keys) {
    const value = meta[key];
    if (value !== null && value !== undefined && value !== "") return value;
  }
  return undefined;
}

export function isTruthyMeta(meta: ResultMetaLike, keys: string[]): boolean {
  const value = pickMeta(meta, keys);
  return value === true || value === "true" || value === 1 || value === "1";
}
