import { readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

type PackageJson = {
  dependencies?: Record<string, string>;
  devDependencies?: Record<string, string>;
};

type PackageLock = {
  packages?: Record<string, { version?: string }>;
};

const MIN_SAFE_VERSION = "7.18.2";
const FRONTEND_ROOT = resolve(process.cwd());
const SRC_ROOT = resolve(FRONTEND_ROOT, "src");
const FORBIDDEN_API_PATTERNS = [
  /@react-router\/dev/,
  /\bServerRouter\b/,
  /\bRSCHydratedRouter\b/,
  /\brouteRSCServerRequest\b/,
  /\bcreateRequestHandler\b/,
  /\breact-router\.config\b/,
  /\bentry\.server\b/,
];

function readJson<T>(path: string): T {
  return JSON.parse(readFileSync(path, "utf8")) as T;
}

function compareVersions(left: string, right: string): number {
  const parse = (value: string) => value.split(".").map((part) => Number.parseInt(part, 10));
  const [leftMajor, leftMinor, leftPatch] = parse(left);
  const [rightMajor, rightMinor, rightPatch] = parse(right);
  if (leftMajor !== rightMajor) return leftMajor - rightMajor;
  if (leftMinor !== rightMinor) return leftMinor - rightMinor;
  return leftPatch - rightPatch;
}

function dependencyFloor(range: string | undefined): string | null {
  if (!range) {
    return null;
  }

  const normalized = range.trim().split(/\s+\|\|\s+|\s+/)[0] ?? "";
  const match = normalized.match(/^(?:\^|~|>=)?\s*(\d+\.\d+\.\d+)$/);
  if (match) {
    return match[1]!;
  }
  if (/^\d+\.\d+\.\d+$/.test(normalized)) {
    return normalized;
  }
  return null;
}

function collectSourceFiles(root: string): string[] {
  const files: string[] = [];
  const stack = [root];

  while (stack.length > 0) {
    const current = stack.pop()!;
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      if (entry.name === "test" || entry.name === "tests" || entry.name === "mocks") {
        continue;
      }
      if (entry.isDirectory()) {
        stack.push(join(current, entry.name));
        continue;
      }
      if (/\.(test|spec)\.[cm]?[jt]sx?$/.test(entry.name)) {
        continue;
      }
      if (!/\.[cm]?[jt]sx?$/.test(entry.name)) {
        continue;
      }
      files.push(join(current, entry.name));
    }
  }

  return files;
}

function collectMatchingFiles(root: string, pattern: RegExp): string[] {
  const matches: string[] = [];
  const stack = [root];
  const excludedDirectories = new Set([
    ".git",
    ".vite",
    ".vitest",
    ".codex-tmp",
    "coverage",
    "dist",
    "node_modules",
  ]);

  while (stack.length > 0) {
    const current = stack.pop()!;
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      if (entry.isDirectory()) {
        if (!excludedDirectories.has(entry.name)) {
          stack.push(join(current, entry.name));
        }
        continue;
      }
      if (pattern.test(entry.name)) {
        matches.push(join(current, entry.name));
      }
    }
  }

  return matches;
}

function readSourceText(path: string): string {
  return readFileSync(path, "utf8");
}

describe("react-router security boundary", () => {
  it("keeps react-router-dom and react-router at or above 7.18.2", () => {
    const packageJson = readJson<PackageJson>(resolve(FRONTEND_ROOT, "package.json"));
    const lockFile = readJson<PackageLock>(resolve(FRONTEND_ROOT, "package-lock.json"));

    const packageDependencyFloor = dependencyFloor(packageJson.dependencies?.["react-router-dom"]);
    const resolvedDomVersion = lockFile.packages?.["node_modules/react-router-dom"]?.version;
    const resolvedRouterVersion = lockFile.packages?.["node_modules/react-router"]?.version;

    expect(packageDependencyFloor).not.toBeNull();
    expect(compareVersions(packageDependencyFloor!, MIN_SAFE_VERSION)).toBeGreaterThanOrEqual(0);
    expect(resolvedDomVersion).toBeDefined();
    expect(resolvedRouterVersion).toBeDefined();
    expect(compareVersions(resolvedDomVersion!, MIN_SAFE_VERSION)).toBeGreaterThanOrEqual(0);
    expect(compareVersions(resolvedRouterVersion!, MIN_SAFE_VERSION)).toBeGreaterThanOrEqual(0);
    expect(packageJson.devDependencies?.["@react-router/dev"]).toBeUndefined();
  });

  it("keeps the production app on client-side browser routing and out of framework/RSC APIs", () => {
    const sourceFiles = collectSourceFiles(SRC_ROOT);
    const routeRegistry = readSourceText(resolve(SRC_ROOT, "router/RouteRegistry.tsx"));
    const routes = readSourceText(resolve(SRC_ROOT, "router/routes.tsx"));
    const appEntry = readSourceText(resolve(SRC_ROOT, "app/App.tsx"));
    const mainEntry = readSourceText(resolve(SRC_ROOT, "main.tsx"));

    expect(routeRegistry).toContain("createBrowserRouter");
    expect(routeRegistry).toContain("RouterProvider");
    expect(mainEntry).toContain("./app/App");
    expect(appEntry).toContain("../router/RouteRegistry");

    const sourceBundle = [routeRegistry, routes, appEntry, mainEntry, ...sourceFiles.map(readSourceText)].join("\n");
    for (const forbiddenPattern of FORBIDDEN_API_PATTERNS) {
      expect(sourceBundle).not.toMatch(forbiddenPattern);
    }

    expect(routes).not.toMatch(/\bloader\s*:/);
    expect(routes).not.toMatch(/\baction\s*:/);
    expect(collectMatchingFiles(FRONTEND_ROOT, /^react-router\.config\./)).toEqual([]);
    expect(collectMatchingFiles(FRONTEND_ROOT, /^entry\.server\./)).toEqual([]);
  });
});
