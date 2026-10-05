import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { lintOpenApi } from './lintOpenApi.mjs';

const script = fileURLToPath(new URL('./lintOpenApi.mjs', import.meta.url));
const ruleset = fileURLToPath(new URL('../../.spectral.yaml', import.meta.url));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'moss-openapi-lint-'));

function contract() {
  return {
    openapi: '3.0.3',
    info: { title: 'Contract fixture', version: '1.0.0' },
    tags: [{ name: 'items' }],
    paths: {
      '/items': {
        get: {
          tags: ['items'],
          operationId: 'listItems',
          parameters: [{ in: 'query', name: 'page_size', schema: { type: 'integer' } }],
          responses: { 200: { description: 'Success' } },
        },
      },
    },
  };
}

function write(name, value) {
  const file = path.join(directory, name);
  fs.writeFileSync(file, typeof value === 'string' ? value : JSON.stringify(value));
  return file;
}

test.after(() => fs.rmSync(directory, { recursive: true, force: true }));

test('the project OpenAPI rules accept a valid contract', async () => {
  const { results, exitCode } = await lintOpenApi(write('valid.json', contract()), ruleset);
  assert.deepEqual(results, []);
  assert.equal(exitCode, 0);
});

test('the custom query casing rule and inherited operation rules still fail', async () => {
  const document = contract();
  const operation = document.paths['/items'].get;
  operation.parameters[0].name = 'pageSize';
  delete operation.operationId;
  delete operation.tags;
  const { results, exitCode } = await lintOpenApi(write('violations.json', document), ruleset);
  for (const code of ['query-param-snake-case', 'operation-operationId', 'operation-tags']) {
    assert.ok(results.some((result) => result.code === code && result.severity === 0), code);
  }
  assert.equal(exitCode, 1);
});

test('warning diagnostics remain visible without changing the error exit threshold', async () => {
  const document = contract();
  document.components = { schemas: { Unused: { type: 'string' } } };
  const { results, exitCode } = await lintOpenApi(write('warning.json', document), ruleset);
  assert.ok(results.some((result) => result.code === 'oas3-unused-component' && result.severity === 1));
  assert.equal(exitCode, 0);
});

test('relative external references resolve and broken references fail', async () => {
  write('item.json', { type: 'object', properties: { id: { type: 'string' } } });
  const document = contract();
  document.paths['/items'].get.responses[200].content = {
    'application/json': { schema: { $ref: './item.json' } },
  };
  const valid = await lintOpenApi(write('external.json', document), ruleset);
  assert.equal(valid.exitCode, 0);
  document.paths['/items'].get.responses[200].content['application/json'].schema.$ref = './missing.json';
  const broken = await lintOpenApi(write('broken-ref.json', document), ruleset);
  assert.equal(broken.exitCode, 1);
  assert.ok(broken.results.some((result) => result.code === 'invalid-ref' && result.severity === 0));
});

test('malformed input fails and unknown formats still produce diagnostics', async () => {
  const malformed = await lintOpenApi(write('malformed.yaml', 'openapi: [\n'), ruleset);
  assert.equal(malformed.exitCode, 1);
  assert.ok(malformed.results.some((result) => result.code === 'parser' && result.severity === 0));
  const unknown = await lintOpenApi(write('unknown.json', { unrelated: true }), ruleset);
  assert.equal(unknown.exitCode, 0);
  assert.ok(unknown.results.some((result) => result.code === 'unrecognized-format'));
});

test('missing inputs and invalid rulesets use the original CLI execution-error exit code', () => {
  const document = write('execution-valid.json', contract());
  for (const args of [[path.join(directory, 'missing.json'), '-r', ruleset], [document, '-r', path.join(directory, 'missing.yaml')]]) {
    const run = spawnSync(process.execPath, [script, ...args], { encoding: 'utf8' });
    assert.equal(run.status, 2);
  }
});
