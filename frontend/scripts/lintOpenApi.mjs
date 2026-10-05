import * as fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import spectralCore from '@stoplight/spectral-core';
import Parsers from '@stoplight/spectral-parsers';
import spectralRefResolver from '@stoplight/spectral-ref-resolver';
import spectralRulesetBundler from '@stoplight/spectral-ruleset-bundler/with-loader';
import spectralRuntime from '@stoplight/spectral-runtime';

const { Document, Spectral } = spectralCore;
const { createHttpAndFileResolver } = spectralRefResolver;
const { bundleAndLoadRuleset } = spectralRulesetBundler;
const { fetch, readParsable } = spectralRuntime;

export async function lintOpenApi(documentPath, rulesetPath) {
  const documentFile = path.resolve(documentPath);
  const spectral = new Spectral({ resolver: createHttpAndFileResolver() });
  spectral.setRuleset(await bundleAndLoadRuleset(path.resolve(rulesetPath), { fs, fetch }));
  const document = new Document(
    await readParsable(documentFile, { encoding: 'utf8' }),
    Parsers.Yaml,
    documentFile,
  );
  // These are the original CLI defaults: report unknown formats and fail only on errors.
  const results = await spectral.run(document, { ignoreUnknownFormat: false });
  return { results, exitCode: results.some((result) => result.severity <= 0) ? 1 : 0 };
}

export async function main(args = process.argv.slice(2)) {
  if (args.length !== 3 || args[1] !== '-r') {
    console.error('Usage: node lintOpenApi.mjs <document> -r <ruleset>');
    return 2;
  }
  try {
    const { results, exitCode } = await lintOpenApi(args[0], args[2]);
    const severities = ['error', 'warning', 'info', 'hint'];
    for (const result of results) {
      const start = result.range?.start;
      const location = start ? `:${start.line + 1}:${start.character + 1}` : '';
      console.log(`${result.source ?? args[0]}${location} ${severities[result.severity]} ${result.code}: ${result.message}`);
    }
    if (results.length === 0) console.log("No results with a severity of 'error' found!");
    return exitCode;
  } catch (error) {
    console.error(`Error running Spectral: ${error instanceof Error ? error.message : String(error)}`);
    return 2;
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main();
}
