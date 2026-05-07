// Run: node frontend/src/api/_cleanup_mock.mjs
import { readFileSync, writeFileSync } from 'fs';

const file = 'f:/MOSS-V3/frontend/src/api/client.ts';
const lines = readFileSync(file, 'utf-8').split(/\r?\n/);

console.log(`Original: ${lines.length} lines`);

// Find boundaries
let removeStart = -1;
let removeEnd = -1;

for (let i = 0; i < lines.length; i++) {
  const t = lines[i].trim();
  // First dead block starts at _buildMockNcdFundingProxyPayload or leftover blank after comment
  if (removeStart === -1 && t.startsWith('function _buildMockNcdFundingProxyPayload')) {
    removeStart = i;
  }
  // Live code resumes at reduceLatestManualAdjustments
  if (t.startsWith('function reduceLatestManualAdjustments')) {
    removeEnd = i;
    break;
  }
}

if (removeStart === -1 || removeEnd === -1) {
  console.error('Could not find boundaries!', { removeStart, removeEnd });
  process.exit(1);
}

// Also remove blank lines between comment and dead block
while (removeStart > 0 && lines[removeStart - 1].trim() === '') {
  removeStart--;
}

console.log(`Removing lines ${removeStart + 1} to ${removeEnd} (0-indexed: ${removeStart}-${removeEnd - 1})`);

const before = lines.slice(0, removeStart);
const comment = ['', '// Dead _MOCK_* payloads removed — live copies in marketDataClient.ts', ''];
const after = lines.slice(removeEnd);

const result = [...before, ...comment, ...after];
console.log(`New: ${result.length} lines (removed ${lines.length - result.length})`);

writeFileSync(file, result.join('\r\n'), 'utf-8');
console.log('Done.');
