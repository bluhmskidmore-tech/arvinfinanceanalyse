import { ConfigProvider } from "antd";
import type { ReactNode } from "react";

import { workbenchTheme } from "../theme/theme";

type ThemedRouteBoundaryProps = {
  children: ReactNode;
};

export default function ThemedRouteBoundary({ children }: ThemedRouteBoundaryProps) {
  return (
    <ConfigProvider theme={workbenchTheme}>
      <div
        className="themed-route-boundary theme-dh-api"
        data-moss-theme="dark"
        data-moss-theme-scope="route"
      >
        {children}
      </div>
    </ConfigProvider>
  );
}
