/**
 * Executive Dashboard domain — type slice of ApiClient.
 * Imported and re-exported by client.ts for backward compatibility.
 */
import type {
  ApiEnvelope,
  AlertsPayload,
  ContributionPayload,
  GetHomeSnapshotOptions,
  HealthResponse,
  HomeSnapshotPayload,
  OverviewPayload,
  PlaceholderSnapshot,
  RiskOverviewPayload,
  RiskTensorDatesPayload,
  RiskTensorPayload,
  SummaryPayload,
} from "./contracts";

export type ExecutiveClientMethods = {
  getHealth: () => Promise<HealthResponse>;
  getOverview: (reportDate?: string) => Promise<ApiEnvelope<OverviewPayload>>;
  getHomeSnapshot: (
    options?: GetHomeSnapshotOptions,
  ) => Promise<ApiEnvelope<HomeSnapshotPayload>>;
  getSummary: () => Promise<ApiEnvelope<SummaryPayload>>;
  getRiskOverview: () => Promise<ApiEnvelope<RiskOverviewPayload>>;
  getRiskTensorDates: () => Promise<ApiEnvelope<RiskTensorDatesPayload>>;
  getRiskTensor: (reportDate: string) => Promise<ApiEnvelope<RiskTensorPayload>>;
  getContribution: () => Promise<ApiEnvelope<ContributionPayload>>;
  getAlerts: () => Promise<ApiEnvelope<AlertsPayload>>;
  getPlaceholderSnapshot: (key: string) => Promise<ApiEnvelope<PlaceholderSnapshot>>;
};
