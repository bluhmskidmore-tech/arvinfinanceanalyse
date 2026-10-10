export type PublicationShowcaseEnvironment = {
  DEV?: boolean;
  VITE_DATA_SOURCE?: string;
  dev?: boolean;
  dataSource?: string;
};

export function isPublicationShowcaseEnabled(
  environment: PublicationShowcaseEnvironment = import.meta.env,
) {
  const isDev = environment.DEV ?? environment.dev ?? false;
  const dataSource = (environment.VITE_DATA_SOURCE ?? environment.dataSource ?? "")
    .trim()
    .toLowerCase();

  return isDev === true && dataSource === "mock";
}
