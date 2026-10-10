import assert from "node:assert/strict";
import test from "node:test";
import {
  parseHtmlJavaScriptResources,
  parseRouteDeps,
  parseViteDependencyManifest,
  stripViteDependencyManifest,
} from "./startupBundleParsing.mjs";

test("HTML startup resources exclude classic scripts, external URLs and styles, and deduplicate preloads", () => {
  const html = `
    <script type="module" src="/assets/index-123.js"></script>
    <script src="/assets/classic-123.js"></script>
    <script type="module" src="https://example.test/assets/external.js"></script>
    <link rel="modulepreload" href="/assets/vendor-123.js">
    <link href='/assets/index-123.js' rel='modulepreload'>
    <link rel="stylesheet" href="/assets/page.css">
    <link rel="modulepreload" href="/assets/page.css">
  `;
  assert.deepEqual(parseHtmlJavaScriptResources(html), ["assets/index-123.js", "assets/vendor-123.js"]);
});

test("Vite manifest and route preload parsing preserve dependency order including CSS", () => {
  const failures = [];
  const report = (message) => failures.push(message);
  const source = 'const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["assets/vendor.js","assets/page.css","assets/page.js"])))=>i.map(i=>d[i]); lazy(()=>preload(()=>import("./Page-a.1.js"),__vite__mapDeps([2,0,1])));';
  const manifest = parseViteDependencyManifest(source, report);
  assert.deepEqual(parseRouteDeps(source, manifest, "Page-a.1.js", report), ["assets/page.js", "assets/vendor.js", "assets/page.css"]);
  assert.deepEqual(failures, []);
});

test("route names are matched literally and select their own preload list", () => {
  const failures = [];
  const source = 'import("./Page-aX1.js"),__vite__mapDeps([0]); import("./Page-a.1.js"),__vite__mapDeps([1]);';
  assert.deepEqual(parseRouteDeps(source, ["assets/other.js", "assets/target.js"], "Page-a.1.js", (message) => failures.push(message)), ["assets/target.js"]);
  assert.deepEqual(failures, []);
});

test("missing or malformed manifests report failure instead of silently passing", () => {
  const failures = [];
  const report = (message) => failures.push(message);
  assert.deepEqual(parseViteDependencyManifest("const app = 1;", report), []);
  assert.deepEqual(parseViteDependencyManifest('m.f=["assets/page.js",]', report), []);
  assert.equal(failures.length, 2);
  assert.match(failures[0], /Could not locate Vite dependency manifest/);
  assert.match(failures[1], /Could not parse Vite dependency manifest/);
});

test("a missing route preload list reports the requested chunk to its owning guard", () => {
  const failures = [];
  assert.deepEqual(parseRouteDeps('import("./Other.js"),__vite__mapDeps([0]);', ["assets/other.js"], "Expected.js", (message) => failures.push(message)), []);
  assert.deepEqual(failures, ["Could not locate dependency preload list for Expected.js."]);
});

test("removing manifest references preserves executable endpoint markers for isolation checks", () => {
  const source = 'const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["assets/ag-grid.js"])))=>i.map(i=>d[i]);\nfetch("/api/dashboard/core_metrics");';
  assert.equal(stripViteDependencyManifest(source), 'fetch("/api/dashboard/core_metrics");');
});
