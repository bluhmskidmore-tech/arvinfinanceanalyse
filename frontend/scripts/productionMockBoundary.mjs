import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

// Payload implementations live in src/mocks. Keep rejecting named API-local
// samples if one is reintroduced, without maintaining a list of old filenames.
const apiMockSource = /^api\/[^/]*mock[^/]*\.[cm]?[jt]sx?$/i;

function normalize(id) {
  return id.split("?")[0].replaceAll("\\", "/");
}

export function productionMockBoundary() {
  let root;
  let sourceRoot;
  function sampleSource(id) {
    const normalized = normalize(resolve(root, id));
    if (!normalized.startsWith(`${sourceRoot}/`)) return undefined;
    const relative = normalized.slice(sourceRoot.length + 1);
    return relative.startsWith("mocks/") ||
      apiMockSource.test(relative)
      ? `src/${relative}` : undefined;
  }
  return {
    name: "moss-production-mock-boundary",
    apply: "build",
    configResolved(config) {
      root = config.root;
      sourceRoot = normalize(resolve(config.root, "src"));
    },
    generateBundle(_options, bundle) {
      const findings = new Set();
      const inlineAssets = new Map();
      for (const output of Object.values(bundle)) {
        if (output.type === "asset") {
          for (const original of output.originalFileNames ?? []) {
            const sample = sampleSource(original);
            if (sample) findings.add(sample);
          }
          continue;
        }
        // Vite's new URL(..., import.meta.url) can inline JSON without creating
        // a module. Inspect surviving data URLs, including explicit ?inline;
        // checking them before tree shaking would reject removed demo branches.
        for (const match of output.code.matchAll(/data:[^"'\s]*?;base64,([A-Za-z0-9+/=]+)/g)) {
          const bytes = Buffer.from(match[1], "base64");
          if (!inlineAssets.has(bytes.length)) inlineAssets.set(bytes.length, new Set());
          inlineAssets.get(bytes.length).add(createHash("sha256").update(bytes).digest("hex"));
        }
        for (const [id, module] of Object.entries(output.modules)) {
          // A module removed by tree shaking contributes no sample data.
          if (module.renderedLength === 0) continue;
          const sample = sampleSource(id);
          if (sample) findings.add(sample);
        }
      }
      // Only inspect this bounded source directory when the output contains an
      // inline asset. Never follow links into local data or generated output.
      const pending = inlineAssets.size > 0 ? [join(sourceRoot, "mocks")] : [];
      while (pending.length > 0) {
        const directory = pending.pop();
        let entries;
        try { entries = readdirSync(directory, { withFileTypes: true }); }
        catch (error) { if (error.code === "ENOENT") continue; throw error; }
        for (const entry of entries) {
          const file = join(directory, entry.name);
          if (entry.isDirectory()) { pending.push(file); continue; }
          if (!entry.isFile()) continue;
          const fingerprints = inlineAssets.get(statSync(file).size);
          if (fingerprints?.has(createHash("sha256").update(readFileSync(file)).digest("hex"))) {
            findings.add(sampleSource(file));
          }
        }
      }
      if (findings.size > 0) {
        this.error(`Mock sources remain in the production bundle:\n${[...findings].sort().join("\n")}`);
      }
    },
  };
}
