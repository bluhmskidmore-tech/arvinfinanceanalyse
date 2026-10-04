import { createServer as createHttpServer, get } from "node:http";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import type { AddressInfo } from "node:net";
import { networkInterfaces, tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";
// This app uses legacy Node module resolution; use Vite's declared entry without changing app-wide resolution.
import { createServer, preview } from "../../node_modules/vite/dist/node/index.js";

async function request(url: string): Promise<string> {
  return new Promise((resolveBody, reject) => {
    const req = get(url, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk: string) => { body += chunk; });
      response.on("end", () => resolveBody(body));
    });
    req.setTimeout(1000, () => req.destroy(new Error("connection timed out")));
    req.on("error", reject);
  });
}

describe("Vite local proxy boundary", () => {
  it.each(["development", "preview"] as const)("%s only accepts local requests by default", async (mode) => {
    // Use the real configuration with a temporary static root and a synthetic API.
    // No requests are made to the normal application or its business database.
    const root = await mkdtemp(join(tmpdir(), "moss-vite-boundary-"));
    if (!resolve(root).startsWith(resolve(tmpdir(), "moss-vite-boundary-"))) {
      throw new Error("temporary test root is outside the expected directory");
    }
    const backend = createHttpServer((_req, res) => res.end("synthetic-api-response"));
    await new Promise<void>((resolveListen) => backend.listen(0, "127.0.0.1", resolveListen));
    const backendPort = (backend.address() as AddressInfo).port;
    const proxy = { "/api": { target: `http://127.0.0.1:${backendPort}`, changeOrigin: true } };
    let closeFrontend: (() => Promise<unknown>) | undefined;
    try {
      await mkdir(join(root, "dist"));
      await writeFile(join(root, "index.html"), "<html><body>synthetic</body></html>");
      await writeFile(join(root, "dist/index.html"), "<html><body>synthetic</body></html>");
      const common = { root, configFile: resolve("vite.config.ts"), logLevel: "silent" as const };
      const server = mode === "development"
        ? await createServer({ ...common, server: { port: 0, proxy, watch: null }, optimizeDeps: { noDiscovery: true, include: [] } })
        : await preview({ ...common, preview: { port: 0, proxy } });
      closeFrontend = () => server.close();
      if (mode === "development" && "listen" in server) await server.listen();
      const address = server.httpServer!.address() as AddressInfo;
      expect(["127.0.0.1", "::1"]).toContain(address.address);
      const host = address.family === "IPv6" ? `[${address.address}]` : address.address;
      expect(await request(`http://${host}:${address.port}/api/probe`)).toBe("synthetic-api-response");
      const remote = Object.values(networkInterfaces()).flat().find((entry) => entry && !entry.internal && entry.family === "IPv4");
      if (remote) {
        await expect(request(`http://${remote.address}:${address.port}/api/probe`)).rejects.toThrow();
      }
    } finally {
      await closeFrontend?.();
      await new Promise<void>((resolveClose) => backend.close(() => resolveClose()));
      await rm(root, { recursive: true, force: true });
    }
  }, 30000);
});
