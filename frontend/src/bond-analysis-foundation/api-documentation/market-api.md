# Market API

## GET `/api/market/yield-curve`

收益率曲线接口，服务于曲线图、对比分析、久期判断。

### Query 参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `curveId` | `string` | 可选，默认主曲线 |
| `asOfDate` | `string` | 指定交易日 |

### 成功响应 `200`

```json
{
  "curveId": "CNY_GOVT",
  "curveName": "中债国债收益率曲线",
  "asOfDate": "2026-04-21",
  "points": [
    { "tenor": "1Y", "yieldValue": 1.56, "changeBp": -2 },
    { "tenor": "10Y", "yieldValue": 2.12, "changeBp": -3 }
  ],
  "dataQuality": {
    "asOfDate": "2026-04-21",
    "source": "curve-engine",
    "freshness": "live",
    "isStale": false
  }
}
```

## GET `/api/market/indices`

返回市场指数、波动率指数、信用利差指数。

### Query 参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `asOfDate` | `string` | 指定日期 |
| `indexTypes` | `string[]` | 例如 `bond`, `volatility`, `credit_spread` |

### 成功响应 `200`

```json
{
  "asOfDate": "2026-04-21",
  "indices": [
    {
      "indexId": "CSI-BOND",
      "indexName": "中债综合指数",
      "indexType": "bond",
      "currentValue": 243.1,
      "changePct": 0.18,
      "asOfDate": "2026-04-21"
    }
  ]
}
```

## GET `/api/bonds/{bondId}/price-history`

返回价格走势图所需序列。

### Query 参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `from` | `string` | 起始日期 |
| `to` | `string` | 结束日期 |
| `interval` | `1D \| 1W \| 1M` | 采样间隔 |

### 成功响应 `200`

```json
[
  { "date": "2026-04-19", "value": 100.82 },
  { "date": "2026-04-20", "value": 101.01 },
  { "date": "2026-04-21", "value": 101.24 }
]
```

## GET `/api/bonds/{bondId}/yield-history`

返回收益率走势图所需序列，结构与价格历史一致。

## 典型错误

- `404 CURVE_NOT_FOUND`
- `404 BOND_NOT_FOUND`
- `429 MARKET_RATE_LIMIT`
- `503 MARKET_FEED_UNAVAILABLE`
