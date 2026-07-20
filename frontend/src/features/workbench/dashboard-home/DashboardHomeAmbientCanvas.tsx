import { useEffect, useRef } from "react";

import styles from "./dashboardHomeShell.module.css";

/**
 * 经营日报首页 hero 环境画布（网格 + 节点漂移 + 呼吸光）。
 * DESIGN.md §8 单点豁免（2026-07-19 业主拍板保留）：
 * - 豁免仅限本组件，禁止扩散到其他页面；
 * - prefers-reduced-motion 下不启动 rAF，只静态绘制一帧，
 *   CSS 层进一步 display:none。
 */

type Node = {
  x: number;
  y: number;
  radius: number;
  drift: number;
  phase: number;
};

const NODE_COUNT = 34;
const MAX_DISTANCE = 180;

function buildNodes(width: number, height: number): Node[] {
  return Array.from({ length: NODE_COUNT }, (_, index) => {
    const column = index % 8;
    const row = Math.floor(index / 8);
    return {
      x: ((column + 0.45 + ((index * 17) % 11) / 32) / 8.5) * width,
      y: ((row + 0.35 + ((index * 13) % 9) / 28) / 5) * height,
      radius: 1.1 + (index % 4) * 0.32,
      drift: 4 + (index % 5) * 1.4,
      phase: index * 0.62,
    };
  });
}

function drawCanvas(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  nodes: Node[],
  time: number,
) {
  context.clearRect(0, 0, width, height);

  const grid = context.createLinearGradient(0, 0, width, height);
  grid.addColorStop(0, "rgba(114, 167, 220, 0.16)");
  grid.addColorStop(0.55, "rgba(232, 238, 247, 0.035)");
  grid.addColorStop(1, "rgba(201, 165, 101, 0.12)");
  context.strokeStyle = grid;
  context.lineWidth = 1;

  const step = 44;
  for (let x = 0; x <= width + step; x += step) {
    context.beginPath();
    context.moveTo(x + 0.5, 0);
    context.lineTo(x - width * 0.08, height);
    context.stroke();
  }
  for (let y = 0; y <= height + step; y += step) {
    context.beginPath();
    context.moveTo(0, y + 0.5);
    context.lineTo(width, y - height * 0.06);
    context.stroke();
  }

  const animated = nodes.map((node) => ({
    ...node,
    ax: node.x + Math.sin(time * 0.00045 + node.phase) * node.drift,
    ay: node.y + Math.cos(time * 0.00038 + node.phase) * node.drift,
  }));

  for (let index = 0; index < animated.length; index += 1) {
    const source = animated[index];
    for (let nextIndex = index + 1; nextIndex < animated.length; nextIndex += 1) {
      const target = animated[nextIndex];
      const distance = Math.hypot(source.ax - target.ax, source.ay - target.ay);
      if (distance > MAX_DISTANCE) {
        continue;
      }
      const opacity = (1 - distance / MAX_DISTANCE) * 0.18;
      context.strokeStyle = `rgba(114, 167, 220, ${opacity.toFixed(3)})`;
      context.beginPath();
      context.moveTo(source.ax, source.ay);
      context.lineTo(target.ax, target.ay);
      context.stroke();
    }
  }

  animated.forEach((node, index) => {
    context.fillStyle = index % 6 === 0 ? "rgba(201, 165, 101, 0.68)" : "rgba(203, 224, 247, 0.56)";
    context.beginPath();
    context.arc(node.ax, node.ay, node.radius, 0, Math.PI * 2);
    context.fill();
  });
}

export function DashboardHomeAmbientCanvas() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return undefined;
    }
    if (navigator.userAgent.toLowerCase().includes("jsdom")) {
      return undefined;
    }

    let context: CanvasRenderingContext2D | null = null;
    try {
      context = canvas.getContext("2d");
    } catch {
      context = null;
    }
    if (!context) {
      return undefined;
    }

    let frame = 0;
    let nodes: Node[] = [];
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

    const resize = () => {
      const bounds = canvas.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.max(Math.round(bounds.width * ratio), 1);
      const height = Math.max(Math.round(bounds.height * ratio), 1);
      canvas.width = width;
      canvas.height = height;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      nodes = buildNodes(bounds.width, bounds.height);
      drawCanvas(context, bounds.width, bounds.height, nodes, 0);
    };

    const animate = (time: number) => {
      const bounds = canvas.getBoundingClientRect();
      drawCanvas(context, bounds.width, bounds.height, nodes, time);
      if (!reducedMotion) {
        frame = window.requestAnimationFrame(animate);
      }
    };

    resize();
    if (!reducedMotion) {
      frame = window.requestAnimationFrame(animate);
    }

    const observer = new ResizeObserver(resize);
    observer.observe(canvas);

    return () => {
      observer.disconnect();
      if (frame) {
        window.cancelAnimationFrame(frame);
      }
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      data-testid="dashboard-home-ambient-canvas"
      aria-hidden="true"
      className={styles.dhApiHeroCanvas}
    />
  );
}
