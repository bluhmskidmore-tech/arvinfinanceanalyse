# Obsidian 笔记与 MOSS 本体绑定约定 v1

## 绑定方式

笔记 YAML frontmatter 声明：

```yaml
---
moss_entities:
  - MTR-PNL-001
  - CONCEPT-formal_pnl
moss_binding_status: narrative
---
```

## 字段语义

- `moss_entities`：本体实体 ID 列表，多对多。ID 必须存在于 `docs/ontology/moss_ontology.v1.json`，`approved` 或 `gap` 均可绑定。
- `moss_binding_status`：绑定状态。
- `narrative`（默认）：纯业务解读，不主张任何口径。
- `candidate`：笔记在提议新概念或新口径，等待 owner 走指标字典晋升流程。

## 禁止事项

- 笔记正文不得定义可执行公式或替代口径。
- 含代码块的笔记会被索引器标记 `contains-code-block` warning，不阻断索引。
- 绑定不存在的实体 ID 会进入 `unknown_bindings` 报告并降级 `quality_flag`。
- Hermes 只注入不含阿拉伯数字的叙事摘要；含数值陈述的笔记仍保留在索引中，但摘要不进入 prompt。

## 降级行为

- vault 不可用、无绑定笔记、本体 loader 不可用时，MOSS 与 Hermes 行为退化为无知识摘要，等同于本约定不存在。
- 本体 loader 不可用时，索引仍保留笔记，但加 `ontology-index-unavailable` warning。

## 权威边界

Obsidian 永远在权威链下游：markdown 契约 -> 本体 seed -> 笔记叙事。冲突时以上游为准。
