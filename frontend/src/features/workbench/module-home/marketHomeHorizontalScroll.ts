import type { KeyboardEvent } from "react";

export function handleHorizontalScrollKeyboard(
  event: KeyboardEvent<HTMLElement>,
  step = 120,
) {
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
    return;
  }

  const target = event.currentTarget;
  if (!(target instanceof HTMLElement)) {
    return;
  }

  event.preventDefault();
  target.scrollBy({
    left: event.key === "ArrowRight" ? step : -step,
    behavior: "smooth",
  });
}
