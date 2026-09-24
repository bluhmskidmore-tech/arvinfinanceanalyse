import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { primaryWorkbenchNavigation, workbenchNavigation } from "../app/navigation";
import { liveRouteReadinessContracts } from "./liveRouteReadinessContracts";

describe("live workbench route readiness contracts", () => {
  const visibleLiveRoutes = primaryWorkbenchNavigation.map((section) => section.path);
  const hiddenLiveRoutes = workbenchNavigation
    .filter((section) => section.readiness === "live")
    .filter((section) => section.navigationVisibility === "hidden")
    .map((section) => section.path);
  const contractRoutes = Object.keys(liveRouteReadinessContracts);
  const visibleContractRoutes = contractRoutes.filter((route) => !hiddenLiveRoutes.includes(route));

  it("has a real page readiness contract for every visible live navigation route", () => {
    expect(visibleContractRoutes.sort()).toEqual([...visibleLiveRoutes].sort());
  });

  it("keeps hidden live deep-link contracts without treating them as visible navigation routes", () => {
    expect(contractRoutes).toEqual(expect.arrayContaining(hiddenLiveRoutes));
  });

  it.each(Object.entries(liveRouteReadinessContracts))(
    "keeps %s tied to real page anchors and verification files",
    (_route, contract) => {
      const sourceFiles = contract.sourceFiles.map((file) => resolve(process.cwd(), file));
      const verificationFiles = contract.verificationFiles.map((file) =>
        resolve(process.cwd(), file),
      );

      for (const sourceFile of sourceFiles) {
        expect(existsSync(sourceFile), `${sourceFile} should exist`).toBe(true);
      }

      for (const verificationFile of verificationFiles) {
        expect(existsSync(verificationFile), `${verificationFile} should exist`).toBe(true);
      }

      const sourceText = sourceFiles.map((file) => readFileSync(file, "utf8")).join("\n");
      for (const anchor of contract.sourceAnchors) {
        expect(sourceText, `${anchor} should remain in ${contract.sourceFiles.join(", ")}`).toContain(
          anchor,
        );
      }
    },
  );
});
