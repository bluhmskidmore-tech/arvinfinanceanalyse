

export function scrollRiskTensorTargetIntoView(target: HTMLElement | null | undefined) {
  // Reveal the requested evidence before scrolling, including nested disclosures.
  let disclosure = target?.closest("details");
  while (disclosure) {
    disclosure.open = true;
    disclosure = disclosure.parentElement?.closest("details") ?? null;
  }
  const scrollIntoView = target?.scrollIntoView;
  if (typeof scrollIntoView === "function") {
    scrollIntoView.call(target, { behavior: "smooth", block: "center" });
  }
}
