# Bonds API

本文件定义债券查询与详情相关的建议 REST 契约，供前端脚手架与后续后端联调使用。

## 通用约定

- Base URL: `/api`
- Content-Type: `application/json`
- 认证: `Authorization: Bearer <token>`
- 分页字段: `page`, `pageSize`, `total`, `hasNextPage`
- 读接口速率限制: `120 requests/minute/user`
- 标准错误体:

```json
{
  "message": "human readable error",
  "code": "BOND_RATE_LIMIT",
  "traceId": "tr_xxx"
}
```

## GET `/api/bonds`

返回债券列表，适合表格首屏和 watchlist 批量拉取。

### Query 参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `query` | `string` | 代码/简称/发行人模糊搜索 |
| `page` | `number` | 页码，默认 `1` |
| `pageSize` | `number` | 每页条数，默认 `20` |
| `sortBy` | `cleanPrice \| yieldToMaturity \| creditSpreadBp \| modifiedDuration \| convexity \| tradeVolume \| liquidityRating \| rating \| maturityDate \| issuerName` | 排序字段 |
| `sortOrder` | `asc \| desc` | 排序方向 |
| `ratings` | `string[]` | 多值评级过滤 |
| `issuerTypes` | `string[]` | 多值发行人类型过滤 |
| `markets` | `string[]` | 多值市场过滤 |
| `maturityDateFrom` | `string` | 到期日下界 |
| `maturityDateTo` | `string` | 到期日上界 |

### 成功响应 `200`

```json
{
  "items": [
    {
      "bondId": "BOND-240210",
      "bondCode": "240210",
      "market": "CIBM",
      "shortName": "24国开10",
      "issuerName": "国家开发银行",
      "issueDate": "2024-02-10",
      "maturityDate": "2034-02-10",
      "marketData": {
        "cleanPrice": 101.24,
        "yieldToMaturity": 2.12,
        "yieldChangeBp": -3,
        "priceChangePct": 0.35,
        "dataQuality": {
          "asOfDate": "2026-04-21",
          "source": "market-feed",
          "freshness": "live",
          "isStale": false
        }
      },
      "riskMetrics": {
        "rating": "AAA",
        "modifiedDuration": 6.4,
        "convexity": 0.88,
        "creditSpreadBp": 32,
        "liquidityRating": "L1",
        "riskScore": 24
      }
    }
  ],
  "total": 1,
  "page": 1,
  "pageSize": 20,
  "hasNextPage": false
}
```

## GET `/api/bonds/{bondId}`

返回完整债券详情，前端可直接渲染详情弹框。

### Path 参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `bondId` | `string` | 系统内部债券主键 |

### 成功响应 `200`

返回 `BondModel.ts` 中 `Bond` 接口对应结构，额外包含：

- `history.priceHistory`
- `history.yieldHistory`
- `history.ratingHistory`

## POST `/api/bonds/search`

用于高级筛选。与 `GET /api/bonds` 相比，支持范围查询与标签组合。

### 请求体

```json
{
  "query": "国开",
  "ratings": ["AAA"],
  "yieldRange": {
    "min": 2.0,
    "max": 2.6
  },
  "durationRange": {
    "min": 4.0,
    "max": 7.0
  },
  "tags": ["policy-bank", "liquid"],
  "page": 1,
  "pageSize": 50
}
```

### 成功响应 `200`

与 `GET /api/bonds` 相同，返回分页列表。

## 典型错误

- `400 BOND_SEARCH_INVALID`: 参数区间不合法
- `404 BOND_NOT_FOUND`: `bondId` 不存在
- `429 BOND_RATE_LIMIT`: 读请求超限
- `503 BOND_MARKET_FEED_UNAVAILABLE`: 行情源不可用，前端需显式展示 stale/fallback 状态
