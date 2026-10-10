export type MarketChangeDirection = "up" | "down" | "flat";

function directionFromNumeric(delta: number): MarketChangeDirection {
  if (delta > 0) {
    return "up";
  }
  if (delta < 0) {
    return "down";
  }
  return "flat";
}

function parseSignedDelta(text: string): number | undefined {
  const dailyMove = text.match(/日变动\s*([+-]?\d+(?:\.\d+)?)/);
  if (dailyMove) {
    return Number(dailyMove[1]);
  }

  const signedToken = text.match(/(^|[\s/])([+-]\d+(?:\.\d+)?)\s*(?:bp|%|index)?/i);
  if (signedToken) {
    return Number(signedToken[2]);
  }

  const unsignedBp = text.match(/(?:^|[\s/])(\d+(?:\.\d+)?)\s*bp\b/i);
  if (unsignedBp) {
    return Number(unsignedBp[1]);
  }

  return undefined;
}

export type MarketChangeClassPalette = {
  up: string;
  down: string;
  neutral: string;
};

export function marketChangePresentation(
  detail: string | undefined,
  sparkline: readonly number[] | undefined,
  palette: MarketChangeClassPalette,
) {
  const direction = resolveMarketChangeDirection(detail, sparkline);
  if (direction === "up") {
    return { direction, className: palette.up };
  }
  if (direction === "down") {
    return { direction, className: palette.down };
  }
  return { direction, className: palette.neutral };
}

export function resolveMarketChangeDirection(
  detail?: string,
  sparkline?: readonly number[],
): MarketChangeDirection | undefined {
  const text = detail?.trim();
  if (text) {
    const parsed = parseSignedDelta(text);
    if (parsed != null && Number.isFinite(parsed)) {
      return directionFromNumeric(parsed);
    }
  }

  if (sparkline && sparkline.length >= 2) {
    const last = sparkline[sparkline.length - 1];
    const prev = sparkline[sparkline.length - 2];
    if (Number.isFinite(last) && Number.isFinite(prev)) {
      return directionFromNumeric(last - prev);
    }
  }

  return undefined;
}
