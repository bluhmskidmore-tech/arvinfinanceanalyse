# Trading API

## GET `/api/orders`

订单列表，适用于订单历史与状态轮询。

### Query 参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `page` | `number` | 页码 |
| `pageSize` | `number` | 每页条数 |
| `bondCode` | `string` | 按债券过滤 |
| `side` | `BUY \| SELL` | 按方向过滤 |
| `status` | `string[]` | 多值状态过滤 |

### 成功响应 `200`

```json
{
  "items": [
    {
      "orderId": "ORD-1001",
      "bondCode": "240210",
      "side": "BUY",
      "quantity": 1000000,
      "price": 101.25,
      "feeAmount": 1250,
      "orderType": "LIMIT",
      "status": "PENDING",
      "createdAt": "2026-04-21T09:30:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "pageSize": 20
}
```

## POST `/api/orders`

创建订单。

### 请求体

```json
{
  "bondCode": "240210",
  "side": "BUY",
  "quantity": 1000000,
  "price": 101.25,
  "feeAmount": 1250,
  "orderType": "LIMIT",
  "traderId": "TRADER-01"
}
```

### 成功响应 `201`

返回 `OrderModel.ts` 中的 `Order` 结构。

## GET `/api/orders/{orderId}`

返回订单详情与成交分笔。

### 成功响应 `200`

```json
{
  "orderId": "ORD-1001",
  "bondCode": "240210",
  "side": "BUY",
  "quantity": 1000000,
  "price": 101.25,
  "status": "PARTIALLY_FILLED",
  "createdAt": "2026-04-21T09:30:00Z",
  "executions": [
    {
      "executionId": "EXE-1",
      "executedQuantity": 400000,
      "executedPrice": 101.24,
      "executedAt": "2026-04-21T09:31:18Z"
    }
  ]
}
```

## DELETE `/api/orders/{orderId}`

取消订单。

### 成功响应 `200`

返回最新订单状态，`status` 变更为 `CANCELLED`。

## 典型错误

- `400 ORDER_VALIDATION_FAILED`
- `403 ORDER_PERMISSION_DENIED`
- `404 ORDER_NOT_FOUND`
- `409 ORDER_ALREADY_FINAL`
- `429 ORDER_RATE_LIMIT`
