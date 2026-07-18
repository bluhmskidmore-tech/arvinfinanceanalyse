import styles from "./dashboardHomeShell.module.css";

/**
 * 装饰画布占位（已静态化）
 * ─────────────────────────────────────────────────────────────
 * 原实现为持续 rAF 绘制的网格 + 节点漂移动画。
 * 依据 DESIGN.md §8（禁止无限循环装饰动效）与首页视觉降噪要求：
 * - 保留 aria-hidden 透明 canvas 作为布局占位；
 * - 不再启动 rAF 循环，不绘制网格/渐变/节点；
 * - prefers-reduced-motion 时进一步 display:none（由 CSS 接管）。
 * 视觉层由 .dhApiHero 面板背景表达层级，不再依赖装饰画布。
 */

export function DashboardHomeAmbientCanvas() {
  return (
    <canvas
      data-testid="dashboard-home-ambient-canvas"
      aria-hidden="true"
      className={styles.dhApiHeroCanvas}
    />
  );
}
