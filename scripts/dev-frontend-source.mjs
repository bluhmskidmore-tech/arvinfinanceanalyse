import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function sourcePort(args) {
  if (args.length === 0) return 5890;
  const value = args.length === 2 && args[0] === '--port'
    ? args[1]
    : args.length === 1 && args[0].startsWith('--port=') ? args[0].slice(7) : '';
  if (!/^\d+$/.test(value) || Number(value) < 1 || Number(value) > 65535) {
    throw new Error('Use --port <1-65535> to select a source development port.');
  }
  const port = Number(value);
  if (port === 5888 || port === 5889) {
    throw new Error(`Port ${port} is reserved for the accepted frontend or Playwright. Use 5890 for source development.`);
  }
  return port;
}

function resolvePython(environment) {
  const venvExecutable = (directory) => path.join(directory,
    ...(process.platform === 'win32' ? ['Scripts', 'python.exe'] : ['bin', 'python']));
  const explicit = environment.MOSS_PYTHON || (environment.VIRTUAL_ENV
    ? venvExecutable(environment.VIRTUAL_ENV) : undefined);
  const candidates = explicit ? [explicit] : [
    venvExecutable(path.join(repoRoot, 'backend', '.venv')),
    venvExecutable(path.join(repoRoot, '.venv')),
  ].filter(existsSync);
  const rejected = [];
  for (const executable of candidates) {
    const result = spawnSync(executable, ['-X', 'utf8', '-c',
      'import json, sys; print(json.dumps({"path": sys.executable, "version": list(sys.version_info[:3])}))'],
    { cwd: repoRoot, env: environment, encoding: 'utf8', timeout: 10000, windowsHide: true });
    let observed;
    try { observed = result.status === 0 ? JSON.parse(result.stdout) : undefined; } catch { /* Report the failed probe below. */ }
    if (observed?.version?.[0] === 3 && observed.version[1] === 11 && observed.path) {
      return { executable: observed.path, version: observed.version.join('.') };
    }
    rejected.push(`${executable}: ${observed?.version?.join('.') ?? result.error?.message ?? 'interpreter probe failed'}`);
  }
  throw new Error(`Python 3.11 is required. ${rejected.join('; ') || 'No project virtual environment was found.'} `
    + 'Select an existing Python 3.11 executable with MOSS_PYTHON, or prepare the project environment using the documented locked install.');
}

async function main(args) {
  if (args.length === 1 && (args[0] === '--help' || args[0] === '-h')) {
    console.log('Usage: npm run dev:source -- [--port <1-65535>]\nDefaults: 127.0.0.1:5890, real data, API proxy http://127.0.0.1:7888.');
    return 0;
  }
  const port = sourcePort(args);
  const environment = {
    ...process.env,
    VITE_DATA_SOURCE: process.env.VITE_DATA_SOURCE || 'real',
    MOSS_VITE_API_PROXY: process.env.MOSS_VITE_API_PROXY || 'http://127.0.0.1:7888',
  };
  if (!['real', 'mock'].includes(environment.VITE_DATA_SOURCE)) {
    throw new Error('VITE_DATA_SOURCE must be real or mock for source development.');
  }
  const python = resolvePython(environment);
  const controller = path.join(repoRoot, 'scripts', 'dev_runtime_control.py');
  const check = spawnSync(python.executable, ['-X', 'utf8', controller, '--repo-root', repoRoot, 'check'],
    { cwd: repoRoot, env: environment, stdio: 'inherit', windowsHide: true });
  if (check.error) throw check.error;
  if (check.status !== 0) return check.status ?? 73;
  const vite = path.join(repoRoot, 'frontend', 'node_modules', 'vite', 'bin', 'vite.js');
  if (!existsSync(vite)) {
    throw new Error('Frontend dependencies are missing. Run npm ci from the frontend directory, then retry.');
  }
  const command = Buffer.from(JSON.stringify({
    argv: [process.execPath, vite, '--host', '127.0.0.1', '--port', String(port),
      '--strictPort', '--clearScreen', 'false'],
    cwd: path.join(repoRoot, 'frontend'),
  })).toString('base64');
  console.log('MOSS frontend mode: source development (Vite hot reload)');
  console.log(`Source development URL: http://127.0.0.1:${port}/`);
  console.log(`Frontend data source: ${environment.VITE_DATA_SOURCE}`);
  console.log(`API proxy: ${environment.MOSS_VITE_API_PROXY} (/api, /ui, /health)`);
  console.log(`Runtime Python: ${python.executable} (${python.version})`);
  if (environment.VITE_API_BASE_URL) console.log(`API base override: ${environment.VITE_API_BASE_URL}`);
  console.log('Vite development .env files also apply. The accepted frontend selection is unchanged.');
  return new Promise((resolve, reject) => {
    const child = spawn(python.executable,
      ['-X', 'utf8', controller, '--repo-root', repoRoot, 'run', '--command-base64', command,
        '--interrupt-grace-seconds', '5'],
      { cwd: repoRoot, env: environment, stdio: 'inherit', windowsHide: true });
    // Windows sends Ctrl+C to all attached console processes. Killing the Python
    // controller there would bypass its child cleanup; POSIX also supports an
    // interrupt delivered only to this wrapper, so forward that interrupt.
    let shutdownCode;
    const interrupt = (signal) => () => {
      if (shutdownCode !== undefined) return;
      shutdownCode = signal === 'SIGTERM' ? 143 : 130;
      if (process.platform !== 'win32' && child.exitCode === null) child.kill('SIGINT');
    };
    const onInterrupt = interrupt('SIGINT');
    const onTerminate = interrupt('SIGTERM');
    process.on('SIGINT', onInterrupt);
    if (process.platform !== 'win32') process.on('SIGTERM', onTerminate);
    const release = () => {
      process.off('SIGINT', onInterrupt);
      process.off('SIGTERM', onTerminate);
    };
    child.once('error', (error) => { release(); reject(error); });
    child.once('exit', (code, signal) => {
      release();
      resolve(shutdownCode ?? code ?? (signal === 'SIGINT' ? 130 : 1));
    });
  });
}

try {
  process.exitCode = await main(process.argv.slice(2));
} catch (error) {
  console.error(`Source development refused: ${error.message}`);
  process.exitCode = 73;
}
