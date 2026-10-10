import { useCallback, useState } from "react";

import type {
  ScenarioActionClosureStatus,
  ScenarioReviewActionStatus,
  ScenarioReviewIssueReason,
} from "./ProductCategoryScenarioPanels";

/** Keeps local review choices alive while the page switches analysis contexts. */
export function useProductCategoryScenarioReview() {
  const [
    selectedScenarioReviewCategoryId,
    setSelectedScenarioReviewCategoryId,
  ] = useState<string | null>(null);
  const [scenarioReviewActionStatuses, setScenarioReviewActionStatuses] =
    useState<Record<string, ScenarioReviewActionStatus>>({});
  const [scenarioReviewIssueReasons, setScenarioReviewIssueReasons] = useState<
    Record<string, ScenarioReviewIssueReason>
  >({});
  const [scenarioActionClosureStatuses, setScenarioActionClosureStatuses] =
    useState<Record<string, ScenarioActionClosureStatus>>({});
  const [
    scenarioActionClosureMemoCategoryId,
    setScenarioActionClosureMemoCategoryId,
  ] = useState<string | null>(null);

  const handleScenarioReviewActionStatus = useCallback(
    (
      categoryId: string,
      actionIndex: number,
      status: ScenarioReviewActionStatus,
    ) => {
      const actionStatusKey = `${categoryId}:${actionIndex}`;
      setScenarioReviewActionStatuses((current) => ({
        ...current,
        [actionStatusKey]: status,
      }));
      if (status !== "issue") {
        setScenarioReviewIssueReasons((current) => {
          if (!(actionStatusKey in current)) {
            return current;
          }
          const next = { ...current };
          delete next[actionStatusKey];
          return next;
        });
      }
    },
    [],
  );
  const handleScenarioReviewIssueReason = useCallback(
    (
      categoryId: string,
      actionIndex: number,
      reason: ScenarioReviewIssueReason,
    ) => {
      setScenarioReviewIssueReasons((current) => ({
        ...current,
        [`${categoryId}:${actionIndex}`]: reason,
      }));
      setScenarioReviewActionStatuses((current) => ({
        ...current,
        [`${categoryId}:${actionIndex}`]: "issue",
      }));
    },
    [],
  );
  const handleBulkScenarioReviewActionStatus = useCallback(
    (
      categoryId: string,
      actionCount: number,
      status: ScenarioReviewActionStatus,
    ) => {
      setScenarioReviewActionStatuses((current) => {
        const next = { ...current };
        for (let index = 0; index < actionCount; index += 1) {
          next[`${categoryId}:${index}`] = status;
        }
        return next;
      });
      if (status !== "issue") {
        setScenarioReviewIssueReasons((current) => {
          const next = { ...current };
          for (let index = 0; index < actionCount; index += 1) {
            delete next[`${categoryId}:${index}`];
          }
          return next;
        });
      }
    },
    [],
  );
  const handleResetScenarioReviewActions = useCallback(
    (categoryId: string, actionCount: number) => {
      setScenarioReviewActionStatuses((current) => {
        const next = { ...current };
        for (let index = 0; index < actionCount; index += 1) {
          delete next[`${categoryId}:${index}`];
        }
        return next;
      });
      setScenarioReviewIssueReasons((current) => {
        const next = { ...current };
        for (let index = 0; index < actionCount; index += 1) {
          delete next[`${categoryId}:${index}`];
        }
        return next;
      });
    },
    [],
  );
  const handleScenarioActionClosureStatus = useCallback(
    (categoryId: string, status: ScenarioActionClosureStatus) => {
      setScenarioActionClosureStatuses((current) => ({
        ...current,
        [categoryId]: status,
      }));
    },
    [],
  );

  return {
    selectedScenarioReviewCategoryId,
    setSelectedScenarioReviewCategoryId,
    scenarioReviewActionStatuses,
    scenarioReviewIssueReasons,
    scenarioActionClosureStatuses,
    scenarioActionClosureMemoCategoryId,
    setScenarioActionClosureMemoCategoryId,
    handleScenarioReviewActionStatus,
    handleScenarioReviewIssueReason,
    handleBulkScenarioReviewActionStatus,
    handleResetScenarioReviewActions,
    handleScenarioActionClosureStatus,
  };
}
