import { Link, isRouteErrorResponse, useLocation, useRouteError } from "react-router-dom";

import styles from "./WorkbenchRouteStatusPages.module.css";

type RouteStatusPageProps = {
  status: "403" | "404" | "error";
  title: string;
  body: string;
  detail?: string;
  testId: string;
  reloadPage?: boolean;
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

function RouteStatusPage({ status, title, body, detail, testId, reloadPage }: RouteStatusPageProps) {
  const location = useLocation();
  return (
    <section className={styles.routeStatus} data-testid={testId} role="alert">
      <div className={styles.routeStatusHeader}>
        <span className={styles.routeStatusCode}>{status === "error" ? "暂不可用" : status}</span>
        <h1 className={styles.routeStatusTitle}>{title}</h1>
        <p className={styles.routeStatusBody}>{body}</p>
      </div>
      {detail ? (
        <details className={styles.routeStatusMeta}>
          <summary>技术诊断</summary>
          <p>{detail}</p>
        </details>
      ) : null}
      <div className={styles.routeStatusActions}>
        {reloadPage ? (
          <Link className={styles.routeStatusAction} reloadDocument to={`${location.pathname}${location.search}${location.hash}`}>
            重新加载当前页
          </Link>
        ) : null}
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
      body="当前页面不存在，请检查地址或返回工作台首页。"
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
        body="当前账号没有访问此页面的权限。如需使用，请联系管理员。"
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
        body="当前页面不存在，请检查地址或返回工作台首页。"
        detail={detail}
        testId="workbench-not-found-page"
      />
    );
  }

  return (
    <RouteStatusPage
      status="error"
      title="页面加载失败"
      body="暂时无法打开页面，请重新加载。若仍未恢复，请联系系统支持。"
      reloadPage
      detail={detail}
      testId="workbench-route-error-page"
    />
  );
}
