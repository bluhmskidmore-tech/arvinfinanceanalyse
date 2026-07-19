import { ConfigProvider } from "antd";
import type { ReactNode } from "react";

import { workbenchTheme } from "../theme/theme";

type ThemedRouteBoundaryProps = {
  children: ReactNode;
};

export default function ThemedRouteBoundary({ children }: ThemedRouteBoundaryProps) {
  return <ConfigProvider theme={workbenchTheme}>{children}</ConfigProvider>;
}
