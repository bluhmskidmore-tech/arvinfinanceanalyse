import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { resolve } from "node:path";

const DIST_DIR = resolve(process.cwd(), "dist");
const SENSITIVE_MARKERS = [
  "ledger_pnl_candidate_financial_indicators_frontend_demo_capture",
  "7f1b9d47dece2db850ef69cd9ab13b2520ad3bc09d6a2bce3a48ac6017777567",
  "c67f4c85390992a1929bcff65c2bbdbd5c5c382912af3ebcd49297b1e7ac6a66",
  "0ba128f1dca4084cfdf4aff410576f1945c11240a88778e00175cbc977e7493d",
  "29717578b92e107cc2fbcd5b66cd7c63191c24e1a7d245c103c94e235331c0b7",
  "49e9a5b06c30656aaa07ef583d459dfff514ddd478640b0fb6f0b355d9758498",
  "9a622783a9a6b719303b9bbdfa16246c9bd0a44b057210b8b87ef39b10edd710",
  "-93537785277.75",
  "57.3617558215",
  "2562.1231279298",
  "2689.6673237342",
  "3555.6258290425",
  "716.7135665145",
  "20.9344161012",
  "78.2961719227",
  "综本!G314",
];

function filesUnder(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name);
    return entry.isDirectory() ? filesUnder(path) : [path];
  });
}

if (!existsSync(DIST_DIR) || !statSync(DIST_DIR).isDirectory()) {
  throw new Error(`Candidate finance bundle guard requires a built dist directory: ${DIST_DIR}`);
}

const findings = [];
for (const file of filesUnder(DIST_DIR)) {
  const content = readFileSync(file);
  const text = content.toString("utf8");
  for (const marker of SENSITIVE_MARKERS) {
    if (text.includes(marker)) {
      findings.push(`${file}: ${marker}`);
    }
  }
}

if (findings.length > 0) {
  throw new Error(`Captured candidate finance data found in production bundle:\n${findings.join("\n")}`);
}

console.log(`Candidate finance bundle guard passed (${filesUnder(DIST_DIR).length} files scanned).`);
