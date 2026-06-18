import { useEffect, useState } from "react";

const NARROW_VIEWPORT_MAX_WIDTH = 980;

export function isMarketDataNarrowViewport(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return window.matchMedia(`(max-width: ${NARROW_VIEWPORT_MAX_WIDTH}px)`).matches;
}

export function useMarketDataNarrowViewport(): boolean {
  const [narrow, setNarrow] = useState(isMarketDataNarrowViewport);

  useEffect(() => {
    const media = window.matchMedia(`(max-width: ${NARROW_VIEWPORT_MAX_WIDTH}px)`);
    const sync = () => setNarrow(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  return narrow;
}
