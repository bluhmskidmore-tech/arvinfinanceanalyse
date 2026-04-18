# Analytical Read Truthfulness Policy

## 目标

统一 analytical / preview / vendor read surfaces 的错误语义，避免把真实后端故障伪装成“正常空结果”。

本文件只约束 **read surface truthfulness**，不扩张任何当前未纳入 cutover 的功能范围。

## 适用范围

适用于以下类型的读面：

- `preview.*`
- `news.*`
- `macro.*`
- `fx.analytical.*`
- 其他 analytical / vendor / preview 型结果面

不用于改变 formal compute 主链的既有契约。

## 规则

### 1. 允许返回空态的情况

以下情况允许返回 `200` + 空 payload：

- DuckDB 文件不存在
- 相关表尚未物化/尚未创建
- catalog / 配置缺失导致当前 surface 没有可展示数据
- 数据真实为空

这类情况必须被解释为：

- “当前没有可读数据”
- 而不是“后端执行失败”

### 2. 必须失败关闭的情况

以下情况不得再返回“健康空结果”：

- DuckDB 文件已存在，但文件损坏/不是有效 DuckDB
- 读库连接失败
- 查询执行失败
- 其他明确的 backend read failure

这类情况必须：

- 抛出 typed read error
- 由 API route 映射为 `503`

### 3. `quality_flag` 规则

当请求已经落到“真实 backend read failure”时：

- 不允许继续返回 `quality_flag="ok"`
- 不允许把失败伪装成 warning-empty，除非该 surface 有明确例外文档批准

### 4. 文案要求

错误 detail 应为可读、稳定、简短的 backend read failure 文案，例如：

- `Source preview foundation read failed.`
- `Choice news read failed.`
- `Macro vendor read failed.`

后续如需统一错误码，可在此策略之上继续收敛。

## 当前已按本政策治理的 surface

- `source_preview`
- `choice-news`
- `macro-foundation`
- `choice-series latest`
- `fx formal status`
- `fx analytical`

## 当前未覆盖的后续面

仍需逐步检查并按本政策统一：

- 其他 macro/vendor analytical surfaces
- 其他 preview / vendor / compatibility read surfaces

## 决策原则

优先 truthful contract，而不是“为了页面好看返回空数据”。

如果用户无法区分：

- “现在没有数据”
- “系统读失败了”

那么这个 read surface 就仍然不可信。
