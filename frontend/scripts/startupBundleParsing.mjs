// Shared parsing only; each startup guard owns its assertions and failure list.
function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function stripViteDependencyManifest(source) {
  return source.replace(/const __vite__mapDeps=.*?;\s*/s, "");
}

export function parseHtmlJavaScriptResources(indexHtml) {
  const resources = new Set();

  for (const match of indexHtml.matchAll(/<script\b[^>]*\bsrc=["']([^"']+)["'][^>]*>/gi)) {
    const tag = match[0];
    const src = match[1];
    if (/type=["']module["']/i.test(tag) && src.startsWith("/assets/") && src.endsWith(".js")) {
      resources.add(src.slice(1));
    }
  }

  for (const match of indexHtml.matchAll(/<link\b[^>]*\bhref=["']([^"']+)["'][^>]*>/gi)) {
    const tag = match[0];
    const href = match[1];
    if (/rel=["']modulepreload["']/i.test(tag) && href.startsWith("/assets/") && href.endsWith(".js")) {
      resources.add(href.slice(1));
    }
  }

  return [...resources];
}

export function parseViteDependencyManifest(entrySource, addFailure) {
  const match = /m\.f\s*=\s*(\[[^\]]*\])/.exec(entrySource);
  if (!match) {
    addFailure("Could not locate Vite dependency manifest in the production entry chunk.");
    return [];
  }

  try {
    return JSON.parse(match[1]);
  } catch (error) {
    addFailure(`Could not parse Vite dependency manifest: ${error.message}`);
    return [];
  }
}

export function parseRouteDeps(entrySource, manifest, routeChunk, addFailure) {
  const routePattern = new RegExp(
    `import\\((["'\`])\\.\\/${escapeRegExp(routeChunk)}\\1\\)[\\s\\S]{0,800}?__vite__mapDeps\\(\\[([^\\]]*)\\]\\)`,
  );
  const match = routePattern.exec(entrySource);
  if (!match) {
    addFailure(`Could not locate dependency preload list for ${routeChunk}.`);
    return [];
  }

  return match[2]
    .split(",")
    .map((value) => Number.parseInt(value.trim(), 10))
    .filter(Number.isInteger)
    .map((index) => manifest[index])
    .filter(Boolean);
}
