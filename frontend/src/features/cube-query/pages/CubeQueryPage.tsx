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
  Tag,
  Typography,
} from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { useApiClient } from "../../../api/client";
import type { CubeDrillPath, CubeQueryRequest, CubeQueryResult } from "../../../api/contracts";
import { isForbiddenCubeError } from "../../../api/cubeClient";
import { DataTable, type DataTableColumn } from "../../../components/layout";
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

const AGG_LABELS: Record<string, string> = {
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

/*
 * 403 是权限边界不是链路故障：默认 viewer 身份拿不到 cube 读权限时，整页维度目录都拿不到，
 * 此前一律写成「稍后重试或切换事实表」，把无权说成了临时故障（2026-09-02 走查）。
 */
const CUBE_FORBIDDEN_TITLE = "当前角色无权访问自助查询";
const CUBE_FORBIDDEN_DESCRIPTION =
  "后端按角色拒绝了 cube 读请求（403）。需要数据中心开通 cube 读权限；页面不会用前端数据补数，重试不会改变结果。";

function describeCubeFailure(
  error: unknown,
  fallback: { title: string; description: string },
): { title: string; description: string; forbidden: boolean } {
  if (isForbiddenCubeError(error)) {
    return { title: CUBE_FORBIDDEN_TITLE, description: CUBE_FORBIDDEN_DESCRIPTION, forbidden: true };
  }
  return { ...fallback, forbidden: false };
}

const EMPTY_STRINGS: string[] = [];

/**
 * 数值列固定两位小数（min=max）：此前 min 2/max 4 会让同一列出现
 * 1,234.50 与 1,234.5678 混排，列内小数位漂移（DESIGN.md §3 对比性数字纪律）。
 */
const numberFmt = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** 与 formatCellValue 同一数值判据：number 或可解析为数值的字符串（后端 Decimal 序列化形态）。 */
function isNumericCellValue(value: unknown): boolean {
  if (typeof value === "number") {
    return Number.isFinite(value);
  }
  if (typeof value === "string" && value.trim() !== "" && /^-?\d/.test(value.trim())) {
    return !Number.isNaN(Number(value));
  }
  return false;
}

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
  return AGG_LABELS[value] ?? value;
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
  filterDimensionList,
  measureFields,
  allowedAggregations,
}: {
  reportDateValid: boolean;
  measureRows: MeasureRow[];
  selectedDimensions: string[];
  filterRows: FilterRow[];
  orderRows: OrderRow[];
  dimensionList: string[];
  filterDimensionList: string[];
  measureFields: string[];
  allowedAggregations: string[];
}): string[] {
  const issues = new Set<string>();
  if (!reportDateValid) {
    issues.add("请先填写有效的报告日");
  }

  const aggAllowed = new Set<string>(allowedAggregations);
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
    if (!filterDimensionList.includes(row.dimension)) {
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
  const activeRequest = useRef<{ request: CubeQueryRequest; key: string } | null>(null);
  const [validationIssues, setValidationIssues] = useState<string[]>([]);
  const [productView, setProductView] = useState("monthly");
  const [categoryId, setCategoryId] = useState<string>();
  const analyticalOnly = factTable === "balance" || factTable === "product_category";

  const dimensionsQuery = useQuery({
    queryKey: [client.mode, "cube-dimensions", factTable],
    queryFn: () => client.getCubeDimensions(factTable),
    enabled: Boolean(factTable),
  });

  const dimensionsFailure = describeCubeFailure(dimensionsQuery.error, {
    title: "维度加载失败",
    description: "维度清单请求失败，请稍后重试或切换事实表。",
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
  const filterDimensionList = useMemo(
    () => dimensionList.filter((dimension) =>
      factTable === "balance" ? dimension !== "currency_basis"
      : factTable === "product_category" ? dimension !== "view" && dimension !== "category_id"
      : true,
    ),
    [dimensionList, factTable],
  );
  const allowedAggregations = dimsPayload?.measures ?? EMPTY_STRINGS;

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
        r.dimension && !filterDimensionList.includes(r.dimension)
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
  }, [factTable, dimensionList, filterDimensionList, measureFields]);

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
      if (factTable === "balance") filters.currency_basis = ["CNY"];
      if (factTable === "product_category") {
        filters.view = [productView];
        filters.category_id = categoryId ? [categoryId] : [];
      }
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
        basis: analyticalOnly ? "analytical" : "formal",
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
      analyticalOnly,
      productView,
      categoryId,
    ],
  );

  const executeMutation = useMutation({
    mutationFn: (req: CubeQueryRequest) => client.executeCubeQuery(req),
    onSuccess: (data, req) => {
      if (activeRequest.current?.request === req) setLastResult(data);
    },
    onMutate: () => setLastResult(null),
  });
  const requestKey = JSON.stringify([client.mode, buildRequest()]);
  const resetMutation = executeMutation.reset;
  useLayoutEffect(() => {
    if (activeRequest.current && activeRequest.current.key !== requestKey) {
      activeRequest.current = null;
      setLastResult(null);
      resetMutation();
    }
  }, [requestKey, resetMutation]);
  useEffect(() => () => { activeRequest.current = null; }, []);
  const executeFailure = describeCubeFailure(executeMutation.error, {
    title: "查询执行失败",
    description:
      executeMutation.error instanceof Error && executeMutation.error.message
        ? executeMutation.error.message
        : "查询失败，请稍后重试。",
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
        filterDimensionList,
        measureFields,
        allowedAggregations,
      });
      if (factTable === "product_category" && !categoryId) {
        issues.push("请选择一个产品类别；跨类别汇总尚未开放");
      }
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
      activeRequest.current = { request: req, key: JSON.stringify([client.mode, req]) };
      executeMutation.mutate(req);
      return true;
    },
    [
      buildRequest,
      client.mode,
      executeMutation,
      reportDate,
      measureRows,
      selectedDimensions,
      filterRows,
      orderRows,
      dimensionList,
      filterDimensionList,
      measureFields,
      allowedAggregations,
      factTable,
      categoryId,
    ],
  );

  const handleExecute = () => {
    setPage(1);
    submit({ page: 1, pageSize });
  };

  const tableColumns: readonly DataTableColumn<Record<string, unknown>>[] = useMemo(() => {
    if (!lastResult?.rows?.length) {
      const keys = [
        ...(lastResult?.dimensions ?? selectedDimensions),
        ...(lastResult?.measures ?? []),
      ];
      if (keys.length === 0 && measureRows.length) {
        return measureRows.map((m) => {
          const dataIndex = m.agg === "count" ? "count" : m.field;
          return {
            title: m.agg === "count" ? "计数" : `${aggLabel(m.agg)}(${m.field})`,
            key: `${m.agg}-${m.field}`,
            align: "numeric" as const,
            render: (row: Record<string, unknown>) => formatCellValue(row[dataIndex]),
          };
        });
      }
      return keys.map((k) => {
        const numeric = measureFields.includes(String(k)) || String(k) === "count";
        return {
          title: String(k) === "count" ? "计数" : k,
          key: k,
          align: numeric ? ("numeric" as const) : ("text" as const),
          render: (row: Record<string, unknown>) => formatCellValue(row[k]),
        };
      });
    }
    const rows = lastResult.rows;
    const measureKeys = new Set(lastResult.measures ?? []);
    return Object.keys(rows[0]!).map((key) => {
      // 列级对齐判据：度量/计数列恒为数值列；其余列扫全部行样本，任意一行是
      // 数值（含字符串化 Decimal）即右对齐。此前只看首行，首行 null 或后端
      // Decimal 字符串会让整列数值左对齐。
      const numeric =
        measureKeys.has(key) ||
        key === "count" ||
        rows.some((row) => isNumericCellValue(row[key]));
      return {
        title: key === "count" ? "计数" : key,
        key,
        align: numeric ? ("numeric" as const) : ("text" as const),
        render: (row: Record<string, unknown>) => formatCellValue(row[key]),
      };
    });
  }, [lastResult, selectedDimensions, measureRows, measureFields]);

  const onDrillValue = (dimension: string, value: string) => {
    if ((factTable === "balance" && dimension === "currency_basis")
      || (factTable === "product_category" && (dimension === "view" || dimension === "category_id"))) return;
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
    <div className={styles.page} data-moss-theme-scope="cube-query" data-testid="cube-query-page">
      <PageHeader
        eyebrow="报表与数据"
        title="多维查询"
        description="按明确口径筛选与钻取；余额和产品类别结果仅供分析。"
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

          {analyticalOnly ? (
            <PageStateSurface
              variant="definition-pending"
              testId="cube-analytical-only"
              title="当前结果仅供分析，不能正式使用"
              description={factTable === "balance"
                ? "金额固定采用折人民币口径；原币记录不参与汇总。"
                : "每次读取一个期间、一个已配置类别的现成收入；父子类别不叠加。"}
            />
          ) : null}
          {factTable === "balance" ? (
            <Space>
              <Text strong>金额口径</Text>
              <Select aria-label="cube-currency-basis" value="CNY" disabled options={[{ value: "CNY", label: "折人民币（CNY）" }]} />
            </Space>
          ) : null}
          {factTable === "product_category" ? (
            <Space wrap>
              <Text strong>期间</Text>
              <Select aria-label="cube-product-view" className={styles.selectWide} value={productView}
                options={(dimsPayload?.required_filters?.view ?? []).map((value) => ({ value, label: value }))}
                onChange={setProductView} />
              <Text strong>产品类别</Text>
              <Select aria-label="cube-product-category" className={styles.selectWide} value={categoryId}
                placeholder="选择单个类别" showSearch
                options={(dimsPayload?.required_filters?.category_id ?? []).map((value) => ({ value, label: value }))}
                onChange={setCategoryId} />
            </Space>
          ) : null}

          <div data-testid="cube-dimensions">
            <Text strong>维度（多选）</Text>
            <div className={styles.sectionBody}>
              {dimensionsQuery.isLoading ? (
                <PageStateSurface variant="loading" title="加载维度…" />
              ) : dimensionsQuery.isError ? (
                <PageStateSurface
                  variant="error"
                  testId="cube-dimensions-error"
                  title={dimensionsFailure.title}
                  description={dimensionsFailure.description}
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
                    options={allowedAggregations.map((a) => ({ value: a, label: aggLabel(a) }))}
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
                    options={filterDimensionList.map((d) => ({ value: d, label: d }))}
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
                title={executeFailure.title}
                description={executeFailure.description}
                actions={
                  executeFailure.forbidden ? undefined : (
                    <Button size="small" onClick={() => submit()}>
                      重试
                    </Button>
                  )
                }
              />
            ) : null}
            <DataTable<Record<string, unknown>>
              testId="cube-results-table"
              rowKey={(row) => JSON.stringify(row)}
              status={executeMutation.isPending ? "loading" : "ready"}
              columns={tableColumns}
              rows={(lastResult?.rows ?? []) as Record<string, unknown>[]}
              skeletonRows={pageSize > 8 ? 8 : pageSize}
              emptyMessage={lastResult ? "暂无数据" : "点击「执行查询」加载"}
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
          {lastResult.result_meta.formal_use_allowed === false ? <Text type="secondary">仅供分析，不能正式使用</Text> : null}
          {lastResult.result_meta.filters_applied ? (
            <Text type="secondary">实际筛选={JSON.stringify(lastResult.result_meta.filters_applied)}</Text>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
