import assert from "node:assert/strict";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { test } from "node:test";
import { build } from "vite";

import { productionMockBoundary } from "./productionMockBoundary.mjs";

test("production builds reject reachable sample sources and retain real code", async (t) => {
  const parent = resolve(tmpdir());
  const root = await mkdtemp(join(parent, "moss-production-mock-"));
  async function buildFixture(name, files, assetsInlineLimit) {
    const fixture = join(root, name);
    for (const [relative, content] of Object.entries(files)) {
      const file = join(fixture, relative);
      await mkdir(dirname(file), { recursive: true });
      await writeFile(file, content, "utf8");
    }
    return build({
      configFile: false,
      root: fixture,
      logLevel: "silent",
      plugins: [productionMockBoundary()],
      build: {
        write: false,
        minify: false,
        assetsInlineLimit,
        rollupOptions: { input: join(fixture, "src/main.js") },
      },
    });
  }
  try {
    await t.test("blocks a statically imported sample", async () => {
      await assert.rejects(buildFixture("static", {
        "src/main.js": "import { sample } from './mocks/prices.js'; globalThis.result = sample;",
        "src/mocks/prices.js": "export const sample = 123456;",
      }), /Mock sources remain in the production bundle:[\s\S]*src\/mocks\/prices\.js/);
    });
    await t.test("blocks a dynamically loaded sample chunk", async () => {
      await assert.rejects(buildFixture("dynamic", {
        "src/main.js": "globalThis.loadSample = () => import('./mocks/prices.js');",
        "src/mocks/prices.js": "export const sample = 123456;",
      }), /Mock sources remain in the production bundle:[\s\S]*src\/mocks\/prices\.js/);
    });
    await t.test("blocks a reintroduced API-local sample module", async () => {
      await assert.rejects(buildFixture("legacy", {
        "src/main.js": "import { sample } from './api/pnlMockClient.ts'; globalThis.result = sample;",
        "src/api/pnlMockClient.ts": "export const sample = 123456;",
      }), /Mock sources remain in the production bundle:[\s\S]*src\/api\/pnlMockClient\.ts/);
    });
    await t.test("blocks a new API-local sample name without a filename allowlist", async () => {
      await assert.rejects(buildFixture("new-api-sample", {
        "src/main.js": "import { sample } from './api/newDomainMockClient.ts'; globalThis.result = sample;",
        "src/api/newDomainMockClient.ts": "export const sample = 123456;",
      }), /Mock sources remain in the production bundle:[\s\S]*src\/api\/newDomainMockClient\.ts/);
    });
    await t.test("allows a production branch with its sample import removed", async () => {
      const result = await buildFixture("real", {
        "src/main.js": "if (!import.meta.env.PROD) import('./mocks/prices.js'); globalThis.mode = 'real';",
        "src/mocks/prices.js": "export const sample = 123456;",
      });
      const outputs = Array.isArray(result) ? result : [result];
      assert.ok(outputs.flatMap((output) => output.output).some((output) => output.type === "chunk" && output.code.includes("real")));
    });
    for (const [name, suffix, limit] of [
      ["external", "", 0], ["inline", "", 4096],
      ["explicit-inline", "?inline", 0], ["explicit-external", "?no-inline", 4096],
    ]) {
      await t.test(`blocks a ${name} sample JSON asset`, async () => {
        await assert.rejects(buildFixture(name, {
          "src/main.js": `globalThis.sampleUrl = new URL('./mocks/prices.json${suffix}', import.meta.url);`,
          "src/mocks/prices.json": '{"price":123456,"source":"synthetic-only"}',
        }, limit), /Mock sources remain in the production bundle:[\s\S]*src\/mocks\/prices\.json/);
      });
    }
    await t.test("allows an inline sample asset removed by the production branch", async () => {
      await buildFixture("dead-inline", {
        "src/main.js": "if (!import.meta.env.PROD) globalThis.sampleUrl = new URL('./mocks/prices.json?inline', import.meta.url); globalThis.mode = 'real';",
        "src/mocks/prices.json": '{"price":123456,"source":"synthetic-only"}',
      });
    });
    await t.test("allows a real asset with different bytes", async () => {
      await buildFixture("real-asset", {
        "src/main.js": "globalThis.schemaUrl = new URL('./schema.json?inline', import.meta.url);",
        "src/schema.json": '{"type":"object"}',
        "src/mocks/prices.json": '{"price":123456,"source":"synthetic-only"}',
      });
    });
  } finally {
    if (!root.startsWith(join(parent, "moss-production-mock-"))) {
      throw new Error("Refusing to clean a fixture outside its temporary root");
    }
    await rm(root, { recursive: true, force: true });
  }
});
