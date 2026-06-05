/** Shared helpers for surfacing FastAPI-style JSON errors on failed fetch responses. */

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
