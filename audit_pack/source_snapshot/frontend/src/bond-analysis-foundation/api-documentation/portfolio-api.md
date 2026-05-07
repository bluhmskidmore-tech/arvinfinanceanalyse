# Portfolio API

## 通用约定

- Base URL: `/api`
- 写接口速率限制: `30 requests/minute/user`
- 返回中的风险与收益指标必须显式带 `asOfDate` 或 `dataQuality.asOfDate`

## GET `/api/portfolio`

返回用户可访问的组合列表。

### 成功响应 `200`

```json
{
  "items": [
    {
      "portfolioId": "PF-001",
      "portfolioName": "核心利率组合",
      "createdAt": "2026-01-02T09:00:00Z",
      "totalMarketValue": 1280000000,
      "statistics": {
        "averageYield": 2.38,
        "weightedDuration": 5.8,
        "concentrationRatio": 0.34,
        "riskScore": 21
      },
      "holdings": []
    }
  ],
  "total": 1,
  "page": 1,
  "pageSize": 20
}
```

## GET `/api/portfolio/{portfolioId}`

返回组合详情与持仓。

### Path 参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `portfolioId` | `string` | 组合主键 |

### 成功响应 `200`

返回 `PortfolioModel.ts` 中 `Portfolio` 接口结构，`holdings[].bond` 建议直接内联 `Bond` 精简版，减少前端二次拼接。

## POST `/api/portfolio/create`

创建组合。

### 请求体

```json
{
  "portfolioName": "利差增强组合",
  "benchmark": "中债-信用债指数",
  "baseCurrency": "CNY",
  "managerName": "交易台二组",
  "holdingBondIds": ["BOND-240210", "BOND-230405"]
}
```

### 成功响应 `201`

返回创建后的 `Portfolio`。

## PUT `/api/portfolio/{portfolioId}`

更新组合元数据或重平衡持仓。

### 请求体

```json
{
  "portfolioName": "利差增强组合（新版）",
  "holdingBondIds": ["BOND-240210", "BOND-230405", "BOND-221018"]
}
```

### 成功响应 `200`

返回更新后的 `Portfolio`。

## GET `/api/portfolio/{portfolioId}/analytics`

返回组合分析视图专用聚合结果。

### Query 参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `asOfDate` | `string` | 指定分析日期 |

### 成功响应 `200`

```json
{
  "asOfDate": "2026-04-21",
  "curveExposure": [
    { "tenor": "5Y", "weight": 0.24 },
    { "tenor": "10Y", "weight": 0.42 }
  ],
  "ratingExposure": [
    { "bucket": "AAA", "weight": 0.76 }
  ],
  "issuerExposure": [
    { "issuerName": "国家开发银行", "weight": 0.18 }
  ],
  "stressTests": [
    {
      "scenarioId": "SCN-UP50",
      "scenarioName": "收益率平行上行 50bp",
      "estimatedPnl": -28400000
    }
  ],
  "dataQuality": {
    "asOfDate": "2026-04-21",
    "source": "portfolio-engine",
    "freshness": "delayed",
    "isStale": false
  }
}
```

## 典型错误

- `404 PORTFOLIO_NOT_FOUND`
- `409 PORTFOLIO_VERSION_CONFLICT`
- `422 PORTFOLIO_HOLDINGS_INVALID`
- `503 PORTFOLIO_ANALYTICS_UNAVAILABLE`
