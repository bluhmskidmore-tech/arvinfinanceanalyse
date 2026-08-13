import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Button,
  Checkbox,
  Col,
  Collapse,
  DatePicker,
  Pagination,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs, { type Dayjs } from "dayjs";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useApiClient } from "../../../api/client";
import type { CubeDrillPath, CubeQueryRequest, CubeQueryResult } from "../../../api/contracts";
import {
  EvidencePanel,
  PageHeader,
  PageStateSurface,
} from "../../../components/page/PagePrimitives";
import { EM_DASH } from "../../../utils/format";

import styles from "./CubeQueryPage.module.css";

const { Text } = Typography;

const FACT_OPTIONS = [
  { value: "bond_analytics", label: "债券分析" },
  { value: "pnl", label: "损益" },
  { value: "balance", label: "资产负债" },
  { value: "product_category", label: "产品类别" },
] as const;

const AGG_OPTIONS = ["sum", "avg", "count", "min", "max"] as const;
const AGG_LABELS: Record<(typeof AGG_OPTIONS)[number], string> = {
  sum: "求和",
  avg: "平均",
  count: "计数",
  min: "最小",
  max: "最大",
};

/** 与 Pagination pageSizeOptions 上限一致；防止超限 limit/offset 直达后端。 */
const MAX_PAGE_SIZE = 200;

type MeasureRow = { key: string; agg: string; field: string };
type FilterRow = { key: string; dimension: string; values: string[] };
type OrderRow = { key: string; field: string; descending: boolean };

let seq = 0;
const nextKey = () => `k${++seq}`;

const EMPTY_STRINGS: string[] = [];

const numberFmt = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) {
    return EM_DASH;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return numberFmt.format(value);
  }
  if (typeof value === "string" && value.trim() !== "" && /^-?\d/.test(value.trim())) {
    const n = Number(value);
    if (!Number.isNaN(n)) {
      return numberFmt.format(n);
    }
  }
  return String(value);
}

function aggLabel(value: string): string {
  return AGG_LABELS[value as (typeof AGG_OPTIONS)[number]] ?? value;
}

function resultMetaQualityLabel(value: string | undefined): string {
  if (value === "ok") return "正常";
  if (value === "warning") return "预警";
  if (value === "error") return "错误";
  if (value === "stale") return "陈旧";
  return value ?? "待定";
}

function buildFiltersMap(rows: FilterRow[]): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const row of rows) {
    if (!row.dimension || row.values.length === 0) {
      continue;
    }
    out[row.dimension] = [...new Set(row.values.map((v) => v.trim()).filter(Boolean))];
  }
  return out;
}

/**
 * 提交前用后端 /api/cube/dimensions/* 返回的元数据做白名单校验：
 * 度量字段/维度/筛选维度/排序字段必须在元数据清单内；
 * 非法项显式拒绝并列出原因，不静默丢弃。
 */
function collectConfigIssues({
  reportDateValid,
  measureRows,
  selectedDimensions,
  filterRows,
  orderRows,
  dimensionList,
  measureFields,
}: {
  reportDateValid: boolean;
  measureRows: MeasureRow[];
  selectedDimensions: string[];
  filterRows: FilterRow[];
  orderRows: OrderRow[];
  dimensionList: string[];
  measureFields: string[];
}): string[] {
  const issues = new Set<string>();
  if (!reportDateValid) {
    issues.add("请先填写有效的报告日");
  }

  const aggAllowed = new Set<string>(AGG_OPTIONS);
  const activeMeasures = measureRows.filter((r) => r.field && r.agg);
  if (activeMeasures.length === 0) {
    issues.add("请至少配置一个有效度量");
  }
  for (const row of activeMeasures) {
    if (!aggAllowed.has(row.agg)) {
      issues.add(`聚合方式「${row.agg}」不受支持`);
    }
    if (row.agg !== "count" && !measureFields.includes(row.field)) {
      issues.add(`度量字段「${row.field}」不在当前事实表可用清单`);
    }
  }

  for (const dim of selectedDimensions) {
    if (!dimensionList.includes(dim)) {
      issues.add(`维度「${dim}」不在当前事实表可用清单`);
    }
  }

  filterRows.forEach((row, index) => {
    const hasValues = row.values.some((v) => v.trim() !== "");
    if (!row.dimension) {
      if (hasValues) {
        issues.add(`第 ${index + 1} 个筛选条件已填写取值但未选择维度`);
      }
      return;
    }
    if (!dimensionList.includes(row.dimension)) {
      issues.add(`筛选维度「${row.dimension}」不在当前事实表可用清单`);
    }
  });

  const orderableFields = new Set<string>([...dimensionList, ...measureFields, "count"]);
  for (const row of orderRows) {
    const field = row.field.trim();
    if (field && !orderableFields.has(field)) {
      issues.add(`排序字段「${field}」不在可用字段清单`);
    }
  }

  return [...issues];
}

export default function CubeQueryPage() {
  const client = useApiClient();
  const [factTable, setFactTable] = useState<string>("bond_analytics");
  const [reportDate, setReportDate] = useState<Dayjs>(() => dayjs("2025-12-31"));
  const [selectedDimensions, setSelectedDimensions] = useState<string[]>([]);
  const [measureRows, setMeasureRows] = useState<MeasureRow[]>([]);
  const [filterRows, setFilterRows] = useState<FilterRow[]>([]);
  const [orderRows, setOrderRows] = useState<OrderRow[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [lastResult, setLastResult] = useState<CubeQueryResult | null>(null);
  const [validationIssues, setValidationIssues] = useState<string[]>([]);

  const dimensionsQuery = useQuery({
    queryKey: [client.mode, "cube-dimensions", factTable],
    queryFn: () => client.getCubeDimensions(factTable),
    enabled: Boolean(factTable),
  });

  const dimsPayload = dimensionsQuery.data;
  const dimensionList = useMemo(
    () => dimsPayload?.dimensions ?? EMPTY_STRINGS,
    [dimsPayload?.dimensions],
  );
  const measureFields = useMemo(
    () => dimsPayload?.measure_fields ?? EMPTY_STRINGS,
    [dimsPayload?.measure_fields],
  );

  useEffect(() => {
    if (!measureFields.length) {
      setMeasureRows([]);
      return;
    }
    setMeasureRows((prev) => {
      if (prev.length === 0) {
        return [{ key: nextKey(), agg: "sum", field: measureFields[0]! }];
      }
      return prev.map((row) =>
        measureFields.includes(row.field) ? row : { ...row, field: measureFields[0]! },
      );
    });
  }, [measureFields]);

  useEffect(() => {
    setSelectedDimensions((prev) => prev.filter((d) => dimensionList.includes(d)));
    setFilterRows((rows) =>
      rows.map((r) =>
        r.dimension && !dimensionList.includes(r.dimension)
          ? { ...r, dimension: "", values: [] }
          : r,
      ),
    );
    setOrderRows((rows) =>
      rows.map((r) =>
        r.field && !dimensionList.includes(r.field) && !measureFields.includes(r.field)
          ? { ...r, field: "" }
          : r,
      ),
    );
    setPage(1);
    setValidationIssues([]);
  }, [factTable, dimensionList, measureFields]);

  const buildRequest = useCallback(
    (
      overrides?: Partial<{
        filterRows: FilterRow[];
        page: number;
        pageSize: number;
      }>,
    ): CubeQueryRequest | null => {
      const rd = reportDate;
      if (!rd?.isValid()) {
        return null;
      }
      const rows = overrides?.filterRows ?? filterRows;
      const p = Math.max(1, overrides?.page ?? page);
      const ps = Math.min(Math.max(1, overrides?.pageSize ?? pageSize), MAX_PAGE_SIZE);
      const measures = measureRows
        .filter((r) => r.field && r.agg)
        .map((r) => (r.agg === "count" ? "count(*)" : `${r.agg}(${r.field})`));
      if (measures.length === 0) {
        return null;
      }
      const filters = buildFiltersMap(rows);
      const order_by = orderRows
        .filter((r) => r.field.trim())
        .map((r) => (r.descending ? `-${r.field.trim()}` : r.field.trim()));
      return {
        report_date: rd.format("YYYY-MM-DD"),
        fact_table: factTable,
        measures,
        dimensions: selectedDimensions,
        filters: Object.keys(filters).length ? filters : undefined,
        order_by: order_by.length ? order_by : undefined,
        limit: ps,
        offset: (p - 1) * ps,
        basis: "formal",
      };
    },
    [
      reportDate,
      factTable,
      measureRows,
      filterRows,
      orderRows,
      selectedDimensions,
      page,
      pageSize,
    ],
  );

  const executeMutation = useMutation({
    mutationFn: (req: CubeQueryRequest) => client.executeCubeQuery(req),
    onSuccess: (data) => {
      setLastResult(data);
    },
  });

  const submit = useCallback(
    (overrides?: Partial<{ filterRows: FilterRow[]; page: number; pageSize: number }>) => {
      const issues = collectConfigIssues({
        reportDateValid: Boolean(reportDate?.isValid()),
        measureRows,
        selectedDimensions,
        filterRows: overrides?.filterRows ?? filterRows,
        orderRows,
        dimensionList,
        measureFields,
      });
      if (issues.length > 0) {
        setValidationIssues(issues);
        return false;
      }
      const req = buildRequest(overrides);
      if (!req) {
        setValidationIssues(["查询请求构建失败，请检查报告日与度量配置"]);
        return false;
      }
      setValidationIssues([]);
      executeMutation.mutate(req);
      return true;
    },
    [
      buildRequest,
      executeMutation,
      reportDate,
      measureRows,
      selectedDimensions,
      filterRows,
      orderRows,
      dimensionList,
      measureFields,
    ],
  );

  const handleExecute = () => {
    setPage(1);
    submit({ page: 1, pageSize });
  };

  const tableColumns: ColumnsType<Record<string, unknown>> = useMemo(() => {
    if (!lastResult?.rows?.length) {
      const keys = [
        ...(lastResult?.dimensions ?? selectedDimensions),
        ...(lastResult?.measures ?? []),
      ];
      if (keys.length === 0 && measureRows.length) {
        return measureRows.map((m) => ({
          title: m.agg === "count" ? "计数" : `${aggLabel(m.agg)}(${m.field})`,
          dataIndex: m.agg === "count" ? "count" : m.field,
          key: `${m.agg}-${m.field}`,
          align: "right" as const,
          render: (v: unknown) => formatCellValue(v),
        }));
      }
      return keys.map((k) => ({
        title: String(k) === "count" ? "计数" : k,
        dataIndex: k,
        key: k,
        align:
          measureFields.includes(String(k)) || String(k) === "count"
            ? ("right" as const)
            : ("left" as const),
        render: (v: unknown) => formatCellValue(v),
      }));
    }
    const sample = lastResult.rows[0]!;
    return Object.keys(sample).map((key) => ({
      title: key === "count" ? "计数" : key,
      dataIndex: key,
      key,
      align: typeof sample[key] === "number" ? ("right" as const) : ("left" as const),
      render: (v: unknown) => formatCellValue(v),
    }));
  }, [lastResult, selectedDimensions, measureRows, measureFields]);

  const onDrillValue = (dimension: string, value: string) => {
    setPage(1);
    setFilterRows((prev) => {
      const existing = prev.find((r) => r.dimension === dimension);
      const next = existing
        ? prev.map((r) =>
            r.key === existing.key
              ? { ...r, values: [...new Set([...r.values, value])] }
              : r,
          )
        : [...prev, { key: nextKey(), dimension, values: [value] }];
      queueMicrotask(() => {
        submit({ filterRows: next, page: 1, pageSize });
      });
      return next;
    });
  };

  const drillPanel = (paths: CubeDrillPath[]) => (
    <Collapse
      items={paths.map((p) => ({
        key: p.dimension,
        label: `${p.label} (${p.dimension})`,
        children: (
          <Space wrap size={[4, 4]}>
            {p.available_values.slice(0, 80).map((v) => (
              <Tag
                key={`${p.dimension}:${v}`}
                className={styles.drillTag}
                onClick={() => onDrillValue(p.dimension, v)}
              >
                {v}
              </Tag>
            ))}
            {p.available_values.length > 80 ? <Text type="secondary">…</Text> : null}
          </Space>
        ),
      }))}
    />
  );

  const orderFieldOptions = useMemo(() => {
    const m = new Set<string>();
    for (const d of selectedDimensions) {
      m.add(d);
    }
    for (const row of measureRows) {
      if (row.agg === "count") {
        m.add("count");
      } else if (row.field) {
        m.add(row.field);
      }
    }
    return [...m];
  }, [selectedDimensions, measureRows]);

  return (
    <div className={styles.page} data-testid="cube-query-page">
      <PageHeader
        eyebrow="报表与数据"
        title="多维查询"
        description="对正式口径事实表进行维度聚合、筛选与钻取。"
      />

      <EvidencePanel heading="查询配置">
        <Space direction="vertical" size="middle" className={styles.stack}>
          <Row gutter={[16, 8]}>
            <Col xs={24} md={8}>
              <Text strong>事实表</Text>
              <Select
                aria-label="cube-fact-table"
                data-testid="cube-fact-select"
                className={styles.fieldControl}
                value={factTable}
                options={FACT_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
                onChange={(v) => {
                  setFactTable(v);
                  setLastResult(null);
                }}
              />
            </Col>
            <Col xs={24} md={8}>
              <Text strong>报告日期</Text>
              <DatePicker
                aria-label="cube-report-date"
                className={styles.fieldControl}
                value={reportDate}
                onChange={(d) => d && setReportDate(d)}
              />
            </Col>
            <Col xs={24} md={8}>
              <Button
                type="primary"
                data-testid="cube-execute"
                loading={executeMutation.isPending}
                onClick={handleExecute}
                className={styles.execute}
              >
                执行查询
              </Button>
            </Col>
          </Row>

          <div data-testid="cube-dimensions">
            <Text strong>维度（多选）</Text>
            <div className={styles.sectionBody}>
              {dimensionsQuery.isLoading ? (
                <PageStateSurface variant="loading" title="加载维度…" />
              ) : dimensionsQuery.isError ? (
                <PageStateSurface
                  variant="error"
                  title="维度加载失败"
                  description="维度清单请求失败，请稍后重试或切换事实表。"
                />
              ) : (
                <Checkbox.Group
                  options={dimensionList.map((d) => ({ label: d, value: d }))}
                  value={selectedDimensions}
                  onChange={(v) => setSelectedDimensions(v as string[])}
                />
              )}
            </div>
          </div>

          <div>
            <Space align="center">
              <Text strong>度量</Text>
              <Button
                size="small"
                onClick={() =>
                  setMeasureRows((r) => [
                    ...r,
                    {
                      key: nextKey(),
                      agg: "sum",
                      field: measureFields[0] ?? "",
                    },
                  ])
                }
              >
                添加度量
              </Button>
            </Space>
            <Space direction="vertical" className={`${styles.stack} ${styles.sectionBody}`}>
              {measureRows.map((row) => (
                <Space key={row.key} wrap>
                  <Select
                    className={styles.selectNarrow}
                    value={row.agg}
                    options={AGG_OPTIONS.map((a) => ({ value: a, label: AGG_LABELS[a] }))}
                    onChange={(agg) =>
                      setMeasureRows((rows) =>
                        rows.map((x) => (x.key === row.key ? { ...x, agg } : x)),
                      )
                    }
                  />
                  <Select
                    className={styles.selectMedium}
                    value={row.field || undefined}
                    placeholder="字段"
                    options={measureFields.map((f) => ({ value: f, label: f }))}
                    onChange={(field) =>
                      setMeasureRows((rows) =>
                        rows.map((x) => (x.key === row.key ? { ...x, field } : x)),
                      )
                    }
                  />
                  <Button
                    danger
                    type="text"
                    disabled={measureRows.length <= 1}
                    onClick={() =>
                      setMeasureRows((rows) => rows.filter((x) => x.key !== row.key))
                    }
                  >
                    删除
                  </Button>
                </Space>
              ))}
            </Space>
          </div>

          <div>
            <Space align="center">
              <Text strong>筛选</Text>
              <Button
                size="small"
                onClick={() =>
                  setFilterRows((r) => [...r, { key: nextKey(), dimension: "", values: [] }])
                }
              >
                添加条件
              </Button>
            </Space>
            <Space direction="vertical" className={`${styles.stack} ${styles.sectionBody}`}>
              {filterRows.map((row) => (
                <Space key={row.key} wrap className={styles.stack}>
                  <Select
                    data-testid="cube-filter-dimension"
                    className={styles.selectMedium}
                    placeholder="维度"
                    value={row.dimension || undefined}
                    options={dimensionList.map((d) => ({ value: d, label: d }))}
                    onChange={(dimension) =>
                      setFilterRows((rows) =>
                        rows.map((x) => (x.key === row.key ? { ...x, dimension, values: [] } : x)),
                      )
                    }
                  />
                  <Select
                    data-testid="cube-filter-values"
                    mode="tags"
                    className={styles.selectGrow}
                    placeholder="取值（可输入）"
                    value={row.values}
                    onChange={(values) =>
                      setFilterRows((rows) =>
                        rows.map((x) => (x.key === row.key ? { ...x, values: [...values] } : x)),
                      )
                    }
                  />
                  <Button
                    type="text"
                    danger
                    onClick={() => setFilterRows((rows) => rows.filter((x) => x.key !== row.key))}
                  >
                    删除
                  </Button>
                </Space>
              ))}
            </Space>
          </div>

          <div>
            <Space align="center">
              <Text strong>排序（可选）</Text>
              <Button
                size="small"
                onClick={() =>
                  setOrderRows((r) => [
                    ...r,
                    { key: nextKey(), field: orderFieldOptions[0] ?? "", descending: false },
                  ])
                }
              >
                添加排序
              </Button>
            </Space>
            <Space direction="vertical" className={`${styles.stack} ${styles.sectionBody}`}>
              {orderRows.map((row) => (
                <Space key={row.key} wrap>
                  <Select
                    className={styles.selectWide}
                    placeholder="字段"
                    value={row.field || undefined}
                    options={orderFieldOptions.map((f) => ({ value: f, label: f }))}
                    onChange={(field) =>
                      setOrderRows((rows) =>
                        rows.map((x) => (x.key === row.key ? { ...x, field } : x)),
                      )
                    }
                  />
                  <Select
                    className={styles.selectNarrow}
                    value={row.descending ? "desc" : "asc"}
                    options={[
                      { value: "asc", label: "升序" },
                      { value: "desc", label: "降序" },
                    ]}
                    onChange={(v) =>
                      setOrderRows((rows) =>
                        rows.map((x) =>
                          x.key === row.key ? { ...x, descending: v === "desc" } : x,
                        ),
                      )
                    }
                  />
                  <Button
                    type="text"
                    danger
                    onClick={() => setOrderRows((rows) => rows.filter((x) => x.key !== row.key))}
                  >
                    删除
                  </Button>
                </Space>
              ))}
            </Space>
          </div>

          {validationIssues.length > 0 ? (
            <PageStateSurface
              variant="error"
              testId="cube-config-validation-error"
              title="查询配置未通过校验，已阻止提交"
              description={validationIssues.join("；")}
            />
          ) : null}
        </Space>
      </EvidencePanel>

      <Row gutter={16} className={styles.resultsRow}>
        <Col xs={24} lg={17}>
          <EvidencePanel heading="查询结果">
            {executeMutation.isError ? (
              <PageStateSurface
                variant="error"
                testId="cube-query-error"
                title="查询执行失败"
                description={
                  executeMutation.error instanceof Error && executeMutation.error.message
                    ? executeMutation.error.message
                    : "查询失败，请稍后重试。"
                }
                actions={
                  <Button size="small" onClick={() => submit()}>
                    重试
                  </Button>
                }
              />
            ) : null}
            <Table<Record<string, unknown>>
              data-testid="cube-results-table"
              size="small"
              rowKey={(row) => JSON.stringify(row)}
              loading={executeMutation.isPending}
              columns={tableColumns}
              dataSource={(lastResult?.rows ?? []) as Record<string, unknown>[]}
              pagination={false}
              locale={{ emptyText: lastResult ? "暂无数据" : "点击「执行查询」加载" }}
            />
            {lastResult ? (
              <Pagination
                className={styles.pagination}
                current={page}
                pageSize={pageSize}
                total={lastResult.total_rows}
                showSizeChanger
                pageSizeOptions={[20, 50, 100, 200]}
                showTotal={(t) => `共 ${t} 行`}
                onChange={(p, ps) => {
                  setPage(p);
                  setPageSize(ps);
                  submit({ page: p, pageSize: ps });
                }}
              />
            ) : null}
          </EvidencePanel>
        </Col>
        <Col xs={24} lg={7}>
          <EvidencePanel heading="钻取路径">
            {lastResult?.drill_paths?.length ? (
              drillPanel(lastResult.drill_paths)
            ) : (
              <PageStateSurface
                variant="empty"
                description="执行查询后展示可选钻取值。"
              />
            )}
          </EvidencePanel>
        </Col>
      </Row>

      {lastResult?.result_meta ? (
        <div className={styles.resultMeta} data-testid="cube-result-meta">
          <Text type="secondary">
            追踪编号={lastResult.result_meta.trace_id} · 质量标记=
            {resultMetaQualityLabel(lastResult.result_meta.quality_flag)}
          </Text>
          <Text type="secondary">来源版本={lastResult.result_meta.source_version}</Text>
        </div>
      ) : null}
    </div>
  );
}
