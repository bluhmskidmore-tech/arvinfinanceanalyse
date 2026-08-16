import { ConfigProvider } from "antd";
/* es 路径为原生 ESM：根路径 CJS 版经 Vite dev 中途预打包会丢 default interop，locale 静默失效。 */
import zhCN from "antd/es/locale/zh_CN";
import type { ReactNode } from "react";

import { workbenchTheme } from "../theme/theme";

type ThemedRouteBoundaryProps = {
  children: ReactNode;
};

export default function ThemedRouteBoundary({ children }: ThemedRouteBoundaryProps) {
  return (
    /* locale：antd 组件内建文案（表格空态「No data」等）随页面语域走中文。 */
    <ConfigProvider theme={workbenchTheme} locale={zhCN}>
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
