import childProcess from "node:child_process";
import { syncBuiltinESMExports } from "node:module";

const originalExec = childProcess.exec;

childProcess.exec = function patchedExec(command, ...args) {
  if (command === "net use") {
    const callback = args.at(-1);
    if (typeof callback === "function") {
      setImmediate(() => callback(null, ""));
    }
    return {
      pid: 0,
      kill() {},
      on() {
        return this;
      },
      once() {
        return this;
      },
      stdout: null,
      stderr: null,
    };
  }
  return originalExec.call(this, command, ...args);
};

syncBuiltinESMExports();

const forwardedArgs = process.argv.slice(2);
const hasPoolArg = forwardedArgs.some(
  (arg, index) =>
    arg === "--pool" ||
    arg.startsWith("--pool=") ||
    (arg === "--no-pool" && index >= 0),
);

process.argv = [
  process.argv[0],
  "vitest",
  ...forwardedArgs,
  ...(hasPoolArg ? [] : ["--pool", "threads"]),
];

await import("../node_modules/vitest/vitest.mjs");
