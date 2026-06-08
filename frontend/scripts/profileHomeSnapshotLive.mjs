const apiBaseUrl = process.env.MOSS_HOME_SNAPSHOT_API_BASE_URL ?? "http://127.0.0.1:7888";
const sampleCount = Number.parseInt(process.env.MOSS_HOME_SNAPSHOT_PROFILE_SAMPLES ?? "7", 10);
const slowHitThresholdMs = Number.parseInt(process.env.MOSS_HOME_SNAPSHOT_SLOW_HIT_MS ?? "150", 10);
const requestDelayMs = Number.parseInt(process.env.MOSS_HOME_SNAPSHOT_PROFILE_DELAY_MS ?? "150", 10);

const boundedSampleCount = Number.isFinite(sampleCount) ? Math.max(1, Math.min(sampleCount, 30)) : 7;

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function percentile(values, p) {
  if (values.length === 0) {
    return null;
  }
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.ceil((p / 100) * sorted.length) - 1;
  return sorted[Math.max(0, Math.min(index, sorted.length - 1))];
}

function isStepDurationMap(value) {
  return (
    value != null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.values(value).every((duration) => Number.isFinite(duration))
  );
}

function slowestPrewarmSteps(homePrewarm, limit = 5) {
  const stepDurations = homePrewarm?.last_step_durations_ms;
  if (!isStepDurationMap(stepDurations)) {
    return [];
  }
  return Object.entries(stepDurations)
    .map(([step, durationMs]) => ({ step, durationMs }))
    .sort((a, b) => b.durationMs - a.durationMs)
    .slice(0, limit);
}

async function fetchJson(path) {
  const response = await fetch(`${apiBaseUrl}${path}`);
  const text = await response.text();
  let payload = null;
  try {
    payload = JSON.parse(text);
  } catch {
    payload = { raw: text };
  }
  return { response, payload };
}

async function sampleSnapshot(index) {
  const startedAt = performance.now();
  const { response, payload } = await fetchJson("/ui/home/snapshot");
  const durationMs = Math.round(performance.now() - startedAt);
  return {
    index,
    status: response.status,
    durationMs,
    reportDate: payload?.result?.report_date ?? null,
    resultKind: payload?.result_meta?.result_kind ?? null,
    sourceVersion: payload?.result_meta?.source_version ?? null,
  };
}

const ready = await fetchJson("/health/ready");
const homePrewarm = ready.payload?.checks?.home_snapshot_prewarm ?? null;
const failures = [];

if (!homePrewarm) {
  failures.push("health/ready is missing checks.home_snapshot_prewarm");
} else if (homePrewarm.status !== "ready") {
  failures.push(`home snapshot prewarm status is ${homePrewarm.status}, expected ready`);
} else if (!isStepDurationMap(homePrewarm.last_step_durations_ms)) {
  failures.push(
    "prewarm status is missing last_step_durations_ms; restart the API so cold snapshot step timings are exposed.",
  );
}

const samples = [];
if (failures.length === 0) {
  for (let index = 1; index <= boundedSampleCount; index += 1) {
    samples.push(await sampleSnapshot(index));
    if (index < boundedSampleCount) {
      await sleep(requestDelayMs);
    }
  }
}

const durations = samples.map((sample) => sample.durationMs);
const slowHits = samples.filter((sample) => sample.durationMs > slowHitThresholdMs);
if (slowHits.length > 0) {
  failures.push(
    `warm snapshot samples exceeded ${slowHitThresholdMs}ms: ${slowHits
      .map((sample) => `#${sample.index}=${sample.durationMs}ms`)
      .join(", ")}`,
  );
}

const summary = {
  apiBaseUrl,
  mode: "live-dev",
  thresholds: {
    sampleCount: boundedSampleCount,
    slowHitThresholdMs,
    requestDelayMs,
  },
  ready: {
    statusCode: ready.response.status,
    status: ready.payload?.status,
    homePrewarm,
    slowestPrewarmSteps: slowestPrewarmSteps(homePrewarm),
  },
  samples,
  stats: {
    minMs: durations.length > 0 ? Math.min(...durations) : null,
    p50Ms: percentile(durations, 50),
    p95Ms: percentile(durations, 95),
    maxMs: durations.length > 0 ? Math.max(...durations) : null,
  },
  failures,
};

if (failures.length > 0) {
  console.error("[home-snapshot-profile] Profile failed.");
  console.error(JSON.stringify(summary, null, 2));
  process.exitCode = 1;
} else {
  console.log("[home-snapshot-profile] Profile passed.");
  console.log(JSON.stringify(summary, null, 2));
}
