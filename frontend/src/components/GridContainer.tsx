import { Row, Col } from "antd";
import type { ReactNode, CSSProperties } from "react";

export type GridContainerProps = {
  children: ReactNode;
  /**
   * Default gutter is [24, 24] aligned with the 24-grid system guidelines.
   */
  gutter?: [number, number];
  style?: CSSProperties;
  /** Passed through as `data-testid` on the Ant Design Row root for tests and QA. */
  testId?: string;
};

/**
 * Standardized Row wrapper to enforce 24-column grid spacing across the dashboard.
 */
export function GridContainer({ children, gutter = [24, 24], style, testId }: GridContainerProps) {
  return (
    <Row gutter={gutter} style={style} data-testid={testId}>
      {children}
    </Row>
  );
}

export type GridItemProps = {
  children: ReactNode;
  span?: number;
  sm?: number;
  md?: number;
  lg?: number;
  xl?: number;
  xxl?: number;
};

/**
 * Standardized Col wrapper for the 24-column grid (e.g., span={8} for 1/3 width).
 */
export function GridItem({ children, span = 24, sm, md, lg, xl, xxl }: GridItemProps) {
  return (
    <Col span={span} sm={sm} md={md} lg={lg} xl={xl} xxl={xxl}>
      {children}
    </Col>
  );
}
