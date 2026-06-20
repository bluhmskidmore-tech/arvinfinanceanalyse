import { Link, isRouteErrorResponse, useLocation, useRouteError } from "react-router-dom";

import styles from "./WorkbenchRouteStatusPages.module.css";

type RouteStatusPageProps = {
  status: "403" | "404" | "error";
  title: string;
  body: string;
  detail?: string;
  testId: string;
};

function routeErrorMessage(error: unknown) {
  if (isRouteErrorResponse(error)) {
    const data = typeof error.data === "string" ? error.data.trim() : "";
    return data || `${error.status} ${error.statusText}`.trim();
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "";
}

function RouteStatusPage({ status, title, body, detail, testId }: RouteStatusPageProps) {
  return (
    <section className={styles.routeStatus} data-testid={testId} role="alert">
      <div className={styles.routeStatusHeader}>
        <span className={styles.routeStatusCode}>{status}</span>
        <h1 className={styles.routeStatusTitle}>{title}</h1>
        <p className={styles.routeStatusBody}>{body}</p>
      </div>
      {detail ? (
        <div className={styles.routeStatusMeta}>
          <span>{detail}</span>
        </div>
      ) : null}
      <div className={styles.routeStatusActions}>
        <Link className={styles.routeStatusAction} to="/">
          返回工作台首页
        </Link>
        <Link
          className={`${styles.routeStatusAction} ${styles.routeStatusActionSecondary}`}
          to="/platform-config"
        >
          查看平台状态
        </Link>
      </div>
    </section>
  );
}

export function WorkbenchNotFoundPage() {
  const location = useLocation();

  return (
    <RouteStatusPage
      status="404"
      title="页面不存在"
      body="当前地址没有匹配到已登记的工作台页面。"
      detail={`请求路径：${location.pathname}`}
      testId="workbench-not-found-page"
    />
  );
}

export function WorkbenchRouteErrorBoundary() {
  const error = useRouteError();
  const detail = routeErrorMessage(error);

  if (isRouteErrorResponse(error) && error.status === 403) {
    return (
      <RouteStatusPage
        status="403"
        title="没有访问权限"
        body="当前账号不能打开这个工作台入口。"
        detail={detail}
        testId="workbench-route-permission-page"
      />
    );
  }

  if (isRouteErrorResponse(error) && error.status === 404) {
    return (
      <RouteStatusPage
        status="404"
        title="页面不存在"
        body="当前地址没有匹配到已登记的工作台页面。"
        detail={detail}
        testId="workbench-not-found-page"
      />
    );
  }

  return (
    <RouteStatusPage
      status="error"
      title="页面加载失败"
      body="页面渲染或加载过程中发生异常，当前结果未作为正常页面展示。"
      detail={detail}
      testId="workbench-route-error-page"
    />
  );
}
