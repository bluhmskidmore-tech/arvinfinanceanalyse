import { createContext, useContext } from "react";

export type SystemReadInteraction = {
  generation: string | null;
  coverageDates: Record<string, string[]>;
  refresh: () => void;
};

export const SystemReadInteractionContext = createContext<SystemReadInteraction | null>(null);

export function useSystemReadInteraction(): SystemReadInteraction {
  const interaction = useContext(SystemReadInteractionContext);
  if (!interaction) {
    throw new Error("SystemReadGenerationBoundary is missing");
  }
  return interaction;
}
