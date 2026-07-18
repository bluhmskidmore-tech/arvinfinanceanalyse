import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import postcss from "postcss";

const cssPath = resolve(
  process.cwd(),
  "src/features/stock-analysis/pages/StockAnalysisPage.css",
);
const source = readFileSync(cssPath, "utf8");
const root = postcss.parse(source, { from: cssPath });
const exactRules = new Map();
const selectorRules = new Map();
let ruleCount = 0;
let declarationCount = 0;

root.walkRules((rule) => {
  ruleCount += 1;
  const declarations = [];
  rule.walkDecls((declaration) => {
    declarationCount += 1;
    declarations.push(`${declaration.prop}:${declaration.value}${declaration.important ? "!important" : ""}`);
  });
  const normalizedSelector = rule.selector.replace(/\s+/g, " ").trim();
  const exactKey = `${normalizedSelector}{${declarations.join(";")}}`;
  const bytes = Buffer.byteLength(rule.toString());
  const line = rule.source?.start?.line ?? null;
  const exactEntry = exactRules.get(exactKey) ?? { selector: normalizedSelector, bytes: 0, occurrences: [] };
  exactEntry.bytes += bytes;
  exactEntry.occurrences.push({ line, bytes });
  exactRules.set(exactKey, exactEntry);

  const selectorEntry = selectorRules.get(normalizedSelector) ?? { bytes: 0, occurrences: [] };
  selectorEntry.bytes += bytes;
  selectorEntry.occurrences.push({ line, bytes, declarations });
  selectorRules.set(normalizedSelector, selectorEntry);
});

const exactDuplicates = [...exactRules.values()]
  .filter((entry) => entry.occurrences.length > 1)
  .map((entry) => ({
    selector: entry.selector,
    count: entry.occurrences.length,
    removableBytes: entry.occurrences.slice(0, -1).reduce((total, item) => total + item.bytes, 0),
    lines: entry.occurrences.map((item) => item.line),
  }))
  .sort((left, right) => right.removableBytes - left.removableBytes);

const repeatedSelectors = [...selectorRules.entries()]
  .filter(([, entry]) => entry.occurrences.length > 1)
  .map(([selector, entry]) => ({
    selector,
    count: entry.occurrences.length,
    bytes: entry.bytes,
    lines: entry.occurrences.map((item) => item.line),
  }))
  .sort((left, right) => right.bytes - left.bytes);

const lineBuckets = new Map();
root.walkRules((rule) => {
  const line = rule.source?.start?.line ?? 0;
  const bucket = `${Math.floor(line / 1000) * 1000}-${Math.floor(line / 1000) * 1000 + 999}`;
  lineBuckets.set(bucket, (lineBuckets.get(bucket) ?? 0) + Buffer.byteLength(rule.toString()));
});

console.log(
  JSON.stringify(
    {
      cssPath,
      sourceBytes: Buffer.byteLength(source),
      ruleCount,
      declarationCount,
      exactDuplicateRuleGroups: exactDuplicates.length,
      exactDuplicateRemovableBytes: exactDuplicates.reduce(
        (total, entry) => total + entry.removableBytes,
        0,
      ),
      topExactDuplicates: exactDuplicates.slice(0, 30),
      repeatedSelectorGroups: repeatedSelectors.length,
      topRepeatedSelectors: repeatedSelectors.slice(0, 40),
      ruleBytesByLineBucket: Object.fromEntries(lineBuckets),
    },
    null,
    2,
  ),
);
