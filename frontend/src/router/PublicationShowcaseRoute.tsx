import { lazy } from "react";

import { isPublicationShowcaseEnabled } from "./publicationShowcaseGate";
import { WorkbenchNotFoundPage } from "./WorkbenchRouteStatusPages";

const PublicationShowcasePage = lazy(
  () => import("../features/publication-showcase/PublicationShowcasePage"),
);

export function PublicationShowcaseRoute() {
  return isPublicationShowcaseEnabled() ? (
    <PublicationShowcasePage />
  ) : (
    <WorkbenchNotFoundPage />
  );
}
