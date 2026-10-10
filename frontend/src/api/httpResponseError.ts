/** Shared helpers for surfacing FastAPI-style JSON errors on failed fetch responses. */

function readSafeText(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed || undefined;
}

function formatStructuredDetail(detail: Record<string, unknown>): string | undefined {
  const message =
    readSafeText(detail.message) ??
    readSafeText(detail.error_message) ??
    readSafeText(detail.detail);
  const metadata = [
    ["code", readSafeText(detail.code)],
    ["run_id", readSafeText(detail.run_id)],
    ["last_status", readSafeText(detail.last_status)],
  ]
    .filter(([, value]) => value)
    .map(([key, value]) => `${key}=${value}`);
  if (!message && metadata.length === 0) {
    return undefined;
  }
  if (!message) {
    return `[${metadata.join(", ")}]`;
  }
  if (metadata.length === 0) {
    return message;
  }
  return `${message} [${metadata.join(", ")}]`;
}

export async function readHttpJsonDetail(response: Response): Promise<string | undefined> {
  try {
    const body: unknown = await response.json();
    if (!body || typeof body !== "object") {
      return undefined;
    }
    const detail = (body as Record<string, unknown>).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail.trim();
    }
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      return formatStructuredDetail(detail as Record<string, unknown>);
    }
    return undefined;
  } catch {
    return undefined;
  }
}

/** Matches backend 503 reserved surfaces (executive + Livermore wording). */
export function isReservedBoundaryHttpMessage(message: string): boolean {
  const t = message.trim().toLowerCase();
  if (!t.includes("reserved")) {
    return false;
  }
  return t.includes("boundary") || t.includes("this wave");
}
