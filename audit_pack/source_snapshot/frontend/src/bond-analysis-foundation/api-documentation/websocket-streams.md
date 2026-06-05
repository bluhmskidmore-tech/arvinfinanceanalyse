# WebSocket Streams

建议前端使用 WebSocket 拉取高频市场数据；若基础设施更适合 SSE，可复用相同消息体。

## 连接地址

- `wss://api.example.com/live/bond-prices`
- `wss://api.example.com/live/yield-curve`

## 建连头

- `Authorization: Bearer <token>`
- `X-Trace-Id: <uuid>`

## 订阅消息

```json
{
  "action": "subscribe",
  "channel": "bond-prices",
  "portfolioId": "PF-001",
  "watchlistId": "WL-core"
}
```

## 债券价格推送体

```json
{
  "channel": "bond-prices",
  "event": "snapshot",
  "asOfDate": "2026-04-21",
  "quotes": [
    {
      "bondCode": "240210",
      "lastPrice": 101.24,
      "yieldToMaturity": 2.12,
      "changePct": 0.35,
      "tradeVolume": 85000000,
      "tradeAmount": 86000000,
      "quoteTime": "2026-04-21T09:31:00Z"
    }
  ]
}
```

## 收益率曲线推送体

```json
{
  "channel": "yield-curve",
  "event": "update",
  "curveId": "CNY_GOVT",
  "asOfDate": "2026-04-21",
  "points": [
    { "tenor": "1Y", "yieldValue": 1.56, "changeBp": -2 },
    { "tenor": "10Y", "yieldValue": 2.12, "changeBp": -3 }
  ]
}
```

## 心跳与断线重连

- 服务端每 `15s` 发送一次 `ping`
- 客户端 `5s` 内回复 `pong`
- 连续丢失 `3` 个心跳后视为断线
- 客户端退避重连建议: `1s -> 2s -> 5s -> 10s`

## 并发限制

- 每用户最多 `5` 条活跃连接
- 同一用户同一频道重复订阅时，服务端应返回最近一条连接并拒绝新增连接
