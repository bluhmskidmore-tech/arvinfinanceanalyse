import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
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
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs, { type Dayjs } from "dayjs";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useApiClient } from "../../../api/client";
import type { CubeDrillPath, CubeQueryRequest, CubeQueryResult } from "../../../api/contracts";

const { Text } = Typography;

const FACT_OPTIONS = [
  { value: "bond_analytics", label: "债券分析" },
  { value: "pnl", label: "损益" },
  { value: "balance", label: "资产负债" },
  { value: "product_category", label: "产品类别" },
] as const;

const AGG_OPTIONS = ["sum", "avg", "count", "min", "max"] as const;

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
    return "—";
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
      const p = overrides?.page ?? page;
      const ps = overrides?.pageSize ?? pageSize;
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
    onError: (err: unknown) => {
      message.error(err instanceof Error ? err.message : "查询失败");
    },
  });

  const submit = useCallback(
    (overrides?: Partial<{ filterRows: FilterRow[]; page: number; pageSize: number }>) => {
      const req = buildRequest(overrides);
      if (!req) {
        message.warning("请填写报告日并至少配置一个有效度量。");
        return false;
      }
      executeMutation.mutate(req);
      return true;
    },
    [buildRequest, executeMutation],
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
          title: m.agg === "count" ? "count" : `${m.agg}(${m.field})`,
          dataIndex: m.agg === "count" ? "count" : m.field,
          key: `${m.agg}-${m.field}`,
          align: "right" as const,
          render: (v: unknown) => formatCellValue(v),
        }));
      }
      return keys.map((k) => ({
        title: k,
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
      title: key,
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
                style={{ cursor: "pointer" }}
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
    <div
      data-testid="cube-query-page"
      style={{ background: "#f5f7fa", minHeight: "100%", padding: 16 }}
    >
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        多维查询
      </Typography.Title>
      <Text type="secondary">对正式口径事实表进行维度聚合、筛选与钻取（basis=formal）。</Text>

      <Card title="查询配置" style={{ marginTop: 16 }} size="small">
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          <Row gutter={[16, 8]}>
            <Col xs={24} md={8}>
              <Text strong>事实表</Text>
              <Select
                aria-label="cube-fact-table"
                data-testid="cube-fact-select"
                style={{ width: "100%", marginTop: 8 }}
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
                style={{ width: "100%", marginTop: 8 }}
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
                style={{ marginTop: 28 }}
              >
                执行查询
              </Button>
            </Col>
          </Row>

          <div data-testid="cube-dimensions">
            <Text strong>维度（多选）</Text>
            <div style={{ marginTop: 8 }}>
              {dimensionsQuery.isLoading ? (
                <Text type="secondary">加载维度…</Text>
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
            <Space direction="vertical" style={{ width: "100%", marginTop: 8 }}>
              {measureRows.map((row) => (
                <Space key={row.key} wrap>
                  <Select
                    style={{ width: 120 }}
                    value={row.agg}
                    options={AGG_OPTIONS.map((a) => ({ value: a, label: a }))}
                    onChange={(agg) =>
                      setMeasureRows((rows) =>
                        rows.map((x) => (x.key === row.key ? { ...x, agg } : x)),
                      )
                    }
                  />
                  <Select
                    style={{ width: 200 }}
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
            <Space direction="vertical" style={{ width: "100%", marginTop: 8 }}>
              {filterRows.map((row) => (
                <Space key={row.key} wrap style={{ width: "100%" }}>
                  <Select
                    style={{ width: 200 }}
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
                    mode="tags"
                    style={{ minWidth: 280, flex: 1 }}
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
            <Space direction="vertical" style={{ width: "100%", marginTop: 8 }}>
              {orderRows.map((row) => (
                <Space key={row.key} wrap>
                  <Select
                    style={{ width: 220 }}
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
                    style={{ width: 120 }}
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
        </Space>
      </Card>

      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col xs={24} lg={17}>
          <Card title="查询结果" size="small">
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
                style={{ marginTop: 16 }}
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
          </Card>
        </Col>
        <Col xs={24} lg={7}>
          <Card title="钻取路径" size="small">
            {lastResult?.drill_paths?.length ? (
              drillPanel(lastResult.drill_paths)
            ) : (
              <Text type="secondary">执行查询后展示可选钻取值。</Text>
            )}
          </Card>
        </Col>
      </Row>

      {lastResult?.result_meta ? (
        <Text
          type="secondary"
          style={{ display: "block", marginTop: 12 }}
          data-testid="cube-result-meta"
        >
          trace_id={lastResult.result_meta.trace_id} · source_version=
          {lastResult.result_meta.source_version} · quality_flag={lastResult.result_meta.quality_flag}
        </Text>
      ) : null}
    </div>
  );
}
