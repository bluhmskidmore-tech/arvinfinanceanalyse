#!/usr/bin/env node
// Runtime mode is deliberately limited to a clean, isolated GitHub Linux checkout.
import fs from 'node:fs/promises';
import path from 'node:path';
import net from 'node:net';
import { randomUUID } from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';

const execute = promisify(execFile);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const arguments_ = process.argv.slice(2);
const mode = arguments_.shift();
if (!['--config-only', '--run'].includes(mode) ||
    (arguments_.length && (arguments_.length !== 2 || arguments_[0] !== '--output'))) {
  throw new Error('Usage: node scripts/verify_compose_runtime.mjs --config-only|--run [--output .codex-tmp/<directory>]');
}
const project = `moss-compose-smoke-${randomUUID().slice(0, 12)}`;
const output = path.resolve(root, arguments_[1] || `.codex-tmp/${project}`);
const relativeOutput = path.relative(path.join(root, '.codex-tmp'), output);
if (!relativeOutput || relativeOutput.startsWith('..') || path.isAbsolute(relativeOutput)) {
  throw new Error('Output must be a new directory inside this checkout .codex-tmp.');
}
const hostEnv = Object.fromEntries(Object.entries(process.env).filter(([key]) =>
  /^(PATH|HOME|USERPROFILE|APPDATA|LOCALAPPDATA|SystemRoot|WINDIR|COMSPEC|PATHEXT|TEMP|TMP|ProgramData|ProgramFiles|ProgramFiles\(x86\)|ProgramW6432)$/i.test(key)));
const receipt = { schemaVersion: 1, project, mode, observedAt: new Date().toISOString(),
  codeRoot: root, configurationValid: false, runtimeExecuted: false, readinessPassed: false,
  workerHeartbeatPassed: false, shutdownPassed: false, cleanupPassed: false,
  scope: 'Six original Compose services; synthetic development storage, local object store, disabled business prewarm; MinIO infrastructure health only.' };
let dockerPrefix = [];
let composePrefix = [];
let configuration;
let startupAttempted = false;
let outputCreated = false;

async function run(executable, args, timeout = 30000) {
  return execute(executable, args, { cwd: root, env: hostEnv, timeout, windowsHide: true,
    maxBuffer: 8 * 1024 * 1024, encoding: 'utf8' });
}
const docker = (...args) => run('docker', [...dockerPrefix, ...args]);
const compose = (args, timeout) => run('docker', [...composePrefix, ...args], timeout);
const exists = async target => { try { await fs.lstat(target); return true; } catch (error) {
  if (error.code === 'ENOENT') return false; throw error; } };
const save = (name, value) => fs.writeFile(path.join(output, name),
  typeof value === 'string' ? value : `${JSON.stringify(value, null, 2)}\n`, 'utf8');

async function verifyCheckout() {
  if (process.platform !== 'linux' || process.env.RUNNER_OS !== 'Linux' ||
      process.env.GITHUB_ACTIONS !== 'true' || !process.env.GITHUB_WORKSPACE ||
      path.resolve(process.env.GITHUB_WORKSPACE) !== root || /^\/mnt\/[cdf](?:\/|$)/i.test(root)) {
    throw new Error('--run requires an isolated GitHub Actions Linux checkout, outside mounted Windows working trees.');
  }
  if (await fs.realpath(root) !== root) throw new Error('Runtime checkout must not resolve through a symbolic link.');
  if ((await run('git', ['status', '--porcelain', '--untracked-files=normal'])).stdout.trim()) {
    throw new Error('Runtime checkout must be clean before creating synthetic inputs.');
  }
  for (const name of ['.env', 'config/.env', 'data', 'data_input', 'data_warehouse', '.venv',
    'backend/.venv', 'node_modules', 'frontend/node_modules', 'frontend/.env', 'frontend/.env.local',
    'frontend/.env.development', 'frontend/.env.development.local']) {
    if (await exists(path.join(root, name))) throw new Error(`Runtime checkout contains forbidden local material: ${name}`);
  }
  receipt.commit = (await run('git', ['rev-parse', 'HEAD'])).stdout.trim();
  if (process.env.GITHUB_SHA && process.env.GITHUB_SHA !== receipt.commit) {
    throw new Error('Checkout HEAD does not match GITHUB_SHA.');
  }
}

async function freePort() {
  const server = net.createServer();
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  const port = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return port;
}

function verifyConfiguration(config) {
  const services = Object.keys(config.services).sort();
  if (JSON.stringify(services) !== JSON.stringify(['api', 'frontend', 'minio', 'postgres', 'redis', 'worker'])) {
    throw new Error('Expected exactly the original six services.');
  }
  for (const [name, service] of Object.entries(config.services)) {
    if (service.container_name || service.env_file || service.privileged || service.network_mode === 'host') {
      throw new Error(`Unexpected container/environment/network boundary in ${name}.`);
    }
    for (const port of service.ports || []) {
      if (port.host_ip !== '127.0.0.1') throw new Error(`Non-loopback published port in ${name}.`);
    }
    for (const volume of service.volumes || []) {
      if (volume.type === 'bind' && ![root, path.join(output, 'runtime')].includes(path.resolve(volume.source))) {
        throw new Error(`Unexpected bind mount in ${name}.`);
      }
    }
  }
  for (const volume of Object.values(config.volumes || {})) {
    if (volume.external || !volume.name.startsWith(`${project}_`)) throw new Error('Unexpected external/shared volume.');
  }
  for (const network of Object.values(config.networks || {})) {
    if (network.external || !network.name.startsWith(`${project}_`)) throw new Error('Unexpected external/shared network.');
  }
}

async function ownedResources() {
  const containerIds = (await docker('ps', '-aq', '--filter', `label=com.docker.compose.project=${project}`)).stdout.trim().split(/\s+/).filter(Boolean);
  const volumes = (await docker('volume', 'ls', '-q', '--filter', `label=com.docker.compose.project=${project}`)).stdout.trim().split(/\s+/).filter(Boolean);
  const expectedVolumes = new Set(Object.values(configuration.volumes).map(volume => volume.name));
  const networks = (await docker('network', 'ls', '-q', '--filter', `label=com.docker.compose.project=${project}`)).stdout.trim().split(/\s+/).filter(Boolean);
  for (const volume of volumes) {
    const [metadata] = JSON.parse((await docker('volume', 'inspect', volume)).stdout);
    if (!expectedVolumes.has(volume) || metadata.Labels?.['com.docker.compose.project'] !== project) {
      throw new Error('Volume ownership cannot be proved.');
    }
  }
  const containers = containerIds.length ? JSON.parse((await docker('inspect', ...containerIds)).stdout) : [];
  for (const container of containers) {
    if (container.Config.Labels?.['com.docker.compose.project'] !== project ||
        container.Config.Labels?.['com.docker.compose.project.working_dir'] !== root) {
      throw new Error('Container ownership cannot be proved.');
    }
    for (const mount of container.Mounts) {
      if (mount.Type === 'volume' && !volumes.includes(mount.Name)) throw new Error('Unowned or anonymous volume mounted.');
      if (mount.Type === 'bind' && ![root, path.join(output, 'runtime')].includes(path.resolve(mount.Source))) {
        throw new Error('Unowned host bind mounted.');
      }
    }
  }
  return { containers, volumes, networks };
}

async function probe(url, check, timeout = 120000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(3000) });
      const body = await response.text();
      if (response.status === 200 && check(body)) return body;
    } catch { /* A service may still be installing its locked dependencies. */ }
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  throw new Error(`Readiness deadline exceeded: ${url}`);
}

try {
  if (mode === '--run') await verifyCheckout();
  const context = (await run('docker', ['context', 'show'])).stdout.trim();
  const [contextMetadata] = JSON.parse((await run('docker', ['context', 'inspect', context])).stdout);
  const endpoint = contextMetadata.Endpoints?.docker?.Host || '';
  if (!/^unix:\/\/\//.test(endpoint) && !/^npipe:\/\/\/\/\.\/pipe\/[A-Za-z0-9_.-]+$/.test(endpoint)) {
    throw new Error('Only local Unix sockets or local Windows named pipes are allowed.');
  }
  receipt.engineEndpointKind = endpoint.startsWith('unix:') ? 'unix' : 'npipe';
  for (let ancestor = path.dirname(output); ancestor !== root; ancestor = path.dirname(ancestor)) {
    if (await exists(ancestor) && (await fs.lstat(ancestor)).isSymbolicLink()) throw new Error('Temporary output must not traverse a symbolic link.');
  }
  await fs.mkdir(path.dirname(output), { recursive: true });
  await fs.mkdir(output, { recursive: false });
  outputCreated = true;
  await fs.mkdir(path.join(output, 'docker-config'));
  await fs.writeFile(path.join(output, 'docker-config', 'config.json'), '{}\n');
  await fs.mkdir(path.join(output, 'runtime'));
  for (const folder of ['governance', 'input', 'archive', 'publication', 'balance-publication']) {
    await fs.mkdir(path.join(output, 'runtime', folder));
  }
  await save('owner.json', { project, codeRoot: root, createdBy: 'scripts/verify_compose_runtime.mjs' });
  const portNames = ['POSTGRES', 'REDIS', 'MINIO', 'MINIO_CONSOLE', 'FRONTEND'];
  const ports = {};
  for (const name of portNames) { let port; do { port = await freePort(); } while (Object.values(ports).includes(port)); ports[name] = port; }
  receipt.ports = ports;
  const interpolation = { MOSS_POSTGRES_USER: 'moss_smoke', MOSS_POSTGRES_DB: 'moss_smoke',
    MOSS_POSTGRES_PASSWORD: `synthetic-${randomUUID()}`, MOSS_MINIO_ROOT_USER: 'moss_smoke',
    MOSS_MINIO_ROOT_PASSWORD: `synthetic-${randomUUID()}`,
    ...Object.fromEntries(portNames.map(name => [`MOSS_${name}_PORT`, String(ports[name])])) };
  await save('synthetic.env', Object.entries(interpolation).map(([key, value]) => `${key}=${value}`).join('\n') + '\n');
  const syntheticSettings = { MOSS_DUCKDB_PATH: '/runtime/moss.duckdb', MOSS_GOVERNANCE_PATH: '/runtime/governance',
    MOSS_DATA_INPUT_ROOT: '/runtime/input', MOSS_PRODUCT_CATEGORY_SOURCE_DIR: '/runtime/input',
    MOSS_LOCAL_ARCHIVE_PATH: '/runtime/archive', MOSS_OBJECT_STORE_MODE: 'local', MOSS_AGENT_ENABLED: '0',
    MOSS_OTEL_ENABLED: '0', MOSS_SYSTEM_READ_PUBLICATION_ENABLED: '0', MOSS_FINANCIAL_PUBLICATION_ENABLED: '0',
    MOSS_BALANCE_ANALYSIS_PUBLICATION_ENABLED: '0', MOSS_FINANCIAL_PUBLICATION_ROOT: '/runtime/publication',
    MOSS_BALANCE_ANALYSIS_PUBLICATION_ROOT: '/runtime/balance-publication', MOSS_HOME_SNAPSHOT_PREWARM_ENABLED: '0',
    MOSS_HOME_INCOME_TREND_PREWARM_ENABLED: '0', MOSS_MARKET_HOME_PREWARM_ENABLED: '0', MOSS_SKIP_STORAGE_READINESS_CHECKS: '0' };
  const runtimeMount = { type: 'bind', source: path.join(output, 'runtime'), target: '/runtime' };
  const overlay = { services: {
    api: { environment: { ...syntheticSettings, MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS: '0', MOSS_SKIP_POSTGRES_MIGRATIONS: '0' }, volumes: [runtimeMount] },
    worker: { environment: syntheticSettings, volumes: [runtimeMount] },
    postgres: { volumes: ['smoke_postgres:/var/lib/postgresql/data'] },
    redis: { volumes: ['smoke_redis:/data'] }, minio: { volumes: ['smoke_minio:/data'] },
    frontend: { environment: { VITE_DATA_SOURCE: 'real', VITE_API_BASE_URL: '' } },
  }, volumes: { smoke_postgres: {}, smoke_redis: {}, smoke_minio: {} } };
  await save('override.json', overlay);
  dockerPrefix = ['--host', endpoint, '--config', path.join(output, 'docker-config')];
  composePrefix = [...dockerPrefix, 'compose', '--project-name', project, '--project-directory', root,
    '--env-file', path.join(output, 'synthetic.env'), '-f', path.join(root, 'docker-compose.yml'), '-f', path.join(output, 'override.json')];
  configuration = JSON.parse((await compose(['config', '--format', 'json'])).stdout);
  verifyConfiguration(configuration);
  receipt.configurationValid = true;
  if (mode === '--run') {
    const server = JSON.parse((await docker('info', '--format', '{{json .}}')).stdout);
    if (server.OSType !== 'linux') throw new Error('Runtime acceptance requires a Linux Docker engine.');
    receipt.engineVersion = server.ServerVersion;
    const existing = await ownedResources();
    const allVolumeNames = (await docker('volume', 'ls', '-q')).stdout.trim().split(/\s+/);
    if (existing.containers.length || existing.volumes.length || existing.networks.length || Object.values(configuration.volumes).some(v => allVolumeNames.includes(v.name))) {
      throw new Error('Refusing to reuse existing containers or volumes.');
    }
    startupAttempted = true;
    await compose(['up', '-d', '--wait', '--wait-timeout', '600'], 660000);
    receipt.runtimeExecuted = true;
    const origin = `http://127.0.0.1:${ports.FRONTEND}`;
    await probe(origin, body => body.includes('id="root"'));
    await probe(`${origin}/src/main.tsx`, body => body.includes('createRoot'));
    const ready = JSON.parse(await probe(`${origin}/health/ready`, body => {
      const payload = JSON.parse(body);
      return payload.status === 'ok' && ['postgresql', 'duckdb', 'redis', 'object_store'].every(key => payload.checks?.[key]?.ok === true);
    }));
    if (ready.checks.object_store.mode !== 'local') throw new Error('Object-store mode unexpectedly changed.');
    await save('readiness.json', ready);
    await probe(`http://127.0.0.1:${ports.MINIO}/minio/health/ready`, () => true);
    receipt.readinessPassed = true;
    const token = randomUUID();
    const heartbeat = path.join(output, 'runtime', 'worker-heartbeat.json');
    await compose(['exec', '-T', 'api', 'python', '-c',
      `from backend.app.tasks.dev_health import write_dev_worker_heartbeat; from backend.app.tasks.broker import get_broker; from dramatiq.brokers.redis import RedisBroker; assert isinstance(get_broker(), RedisBroker); write_dev_worker_heartbeat.send(heartbeat_path='/runtime/worker-heartbeat.json', token=${JSON.stringify(token)})`]);
    const deadline = Date.now() + 120000;
    while (Date.now() < deadline && !await exists(heartbeat)) await new Promise(resolve => setTimeout(resolve, 1000));
    const result = JSON.parse(await fs.readFile(heartbeat, 'utf8'));
    if (result.token !== token || !Number.isInteger(result.pid) || result.pid <= 0) throw new Error('Worker heartbeat identity mismatch.');
    receipt.workerHeartbeatPassed = true;
    const resources = await ownedResources();
    receipt.startup = resources.containers.map(container => ({ service: container.Config.Labels['com.docker.compose.service'], running: container.State.Running, health: container.State.Health?.Status || null }));
    if (resources.containers.length !== 6 || resources.containers.some(container => !container.State.Running)) throw new Error('Expected exactly six owned running containers.');
  }
} catch (error) {
  receipt.error = error.message;
  process.exitCode = 1;
} finally {
  if (startupAttempted) {
    try {
      await ownedResources();
      let stopSucceeded = true;
      try { await compose(['stop', '--timeout', '30'], 90000); }
      catch (error) { stopSucceeded = false; receipt.shutdownStopError = error.message; }
      const stopped = await ownedResources();
      let logText = '';
      try { logText = (await compose(['logs', '--no-color'])).stdout; await save('compose.log', logText); }
      catch (error) { receipt.shutdownLogError = error.message; }
      receipt.shutdown = stopped.containers.map(container => ({ service: container.Config.Labels['com.docker.compose.service'],
        running: container.State.Running, exitCode: container.State.ExitCode }));
      receipt.shutdownPassed = stopSucceeded && stopped.containers.length === 6 && stopped.containers.every(container =>
        !container.State.Running && [0, 143].includes(container.State.ExitCode)) && logText.includes('Application shutdown complete') && logText.includes('Worker has been shut down.');
      await compose(['down', '--volumes', '--timeout', '30'], 90000);
      const remaining = await ownedResources();
      const released = await Promise.all(Object.values(receipt.ports).map(port => new Promise(resolve => {
        const socket = net.createConnection({ host: '127.0.0.1', port });
        socket.setTimeout(2000); socket.once('connect', () => { socket.destroy(); resolve(false); });
        socket.once('timeout', () => { socket.destroy(); resolve(false); });
        socket.once('error', error => resolve(error.code === 'ECONNREFUSED'));
      })));
      receipt.portsReleased = released.every(Boolean);
      receipt.cleanupPassed = !remaining.containers.length && !remaining.volumes.length && !remaining.networks.length && receipt.portsReleased;
      if (!receipt.shutdownPassed || !receipt.cleanupPassed) throw new Error('Normal shutdown or owned-resource cleanup did not pass.');
    } catch (error) { receipt.cleanupError = error.message; process.exitCode = 1; }
  }
  receipt.status = receipt.error || receipt.cleanupError ? 'not_passed' : mode === '--config-only' && receipt.configurationValid ? 'configuration_valid_runtime_not_executed' :
    receipt.readinessPassed && receipt.workerHeartbeatPassed && receipt.shutdownPassed && receipt.cleanupPassed ? 'passed' : 'not_passed';
  receipt.sourceWriteBoundary = 'Runtime mode only: original editable installation may create egg-info in the exclusive runner checkout; Python packages remain in container layers and frontend packages in the project volume.';
  if (outputCreated) await save('acceptance.json', receipt);
  console.log(JSON.stringify(receipt, null, 2));
}
