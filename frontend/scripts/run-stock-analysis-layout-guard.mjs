import { spawn } from "node:child_process";
import net from "node:net";
import { fileURLToPath } from "node:url";

const DEFAULT_PORT_START = 5899;
const SPEC_PATH = "tests/playwright/stock-analysis-layout-density.spec.mjs";

function canListen(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.unref();
    server.once("error", () => resolve(false));
    server.listen(port, "127.0.0.1", () => {
      server.close(() => resolve(true));
    });
  });
}

async function findPort(start) {
  for (let port = start; port < start + 50; port += 1) {
    if (await canListen(port)) return String(port);
  }
  throw new Error(`No free localhost port found from ${start} to ${start + 49}.`);
}

const playwrightPort =
  process.env.MOSS_PLAYWRIGHT_PORT || (await findPort(DEFAULT_PORT_START));

const env = {
  ...process.env,
  MOSS_PLAYWRIGHT_USE_WEB_SERVER: "1",
  MOSS_PLAYWRIGHT_PORT: playwrightPort,
  MOSS_PLAYWRIGHT_BASE_URL: `http://127.0.0.1:${playwrightPort}`,
  VITE_DATA_SOURCE: "real",
};

const playwrightCli = fileURLToPath(
  new URL("../node_modules/playwright/cli.js", import.meta.url),
);
const command = process.execPath;
const args = [
  playwrightCli,
  "test",
  "-c",
  "playwright.config.mjs",
  SPEC_PATH,
];

const child = spawn(command, args, {
  cwd: process.cwd(),
  env,
  stdio: "inherit",
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});

child.on("error", (error) => {
  console.error(error);
  process.exit(1);
});
