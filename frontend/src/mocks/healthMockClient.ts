import type { HealthClientMethods } from "../api/healthClient";

type Delay = () => Promise<void>;

export function createDemoHealthClient(delay: Delay): HealthClientMethods {
  return {
    async getHealth() {
      await delay();
      return { status: "ok" };
    },
    async getHealthLive() {
      await delay();
      return { status: "ok" };
    },
    async getHealthSummary() {
      await delay();
      return { status: "ok" };
    },
  };
}

export const createMockHealthClient = createDemoHealthClient;
