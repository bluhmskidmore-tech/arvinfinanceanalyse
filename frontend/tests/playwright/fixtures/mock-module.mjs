import fs from "node:fs";
import ts from "typescript";

// Browser fixtures reuse existing mock builders without loading the app/client
// runtime or relying on Node's unsupported JSON import-attribute combination.
export function loadMock(url) {
  const code = ts.transpileModule(fs.readFileSync(url, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const exports = {};
  new Function("exports", "require", code)(exports, (name) => name.endsWith(".json")
    ? { default: JSON.parse(fs.readFileSync(new URL(name, url), "utf8")) }
    : loadMock(new URL(`${name}.ts`, url)));
  return exports;
}
