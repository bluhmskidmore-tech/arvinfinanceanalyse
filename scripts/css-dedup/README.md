# css-dedup — 重复选择器零视觉合并工具集

把一个 CSS（module）文件里同一媒体上下文中重复声明的选择器块合并为「每上下文最多 1 块」，
并以机器证据证明渲染结果与合并前逐像素一致。已完成两轮实战：
`portfolioHome.module.css`（145 组/356 块）与 `riskOverview.module.css`（28 组/59 块）。

## 核心算法约定（勿凭直觉改）

- 合并方向永远是「向同上下文最后一次出现处合」；逐属性后者赢；被覆盖的死声明删除。
- 媒体查询不增加特异性；跨上下文绝不合并；`@keyframes` 子块不参与。
- 交错冲突（移动某声明会越过「同特异性、可命中同一元素、属性重叠」的其他规则）时，
  该属性留在原位残留块并加注释；共现判定证据 = 页面 TSX className 提取 ∪ 双数据态 DOM
  （自身类组合用 TSX∪DOM 裁决；祖先关系才允许 DOM 闭包证据行使否决权）。
- 含 `!important` 的块与 `:global(...)` 组一律不动；`finalMarker` 标记的文末权威段逐字节不动。
- 动态类（辅助函数返回 / `styles[...]` 方括号访问）必须列入 config 的 `wildcards`，
  视为可与任意元素组合（保守方向：宁可多报冲突）。

## 工作流（每个目标文件一轮）

1. 写 `configs/<page>.json`（字段见 `configs/template.example.json`）。
2. 备份目标文件到 workDir；`node analyze.js <config> stats` 看重复分布；
   `node analyze.js <config> pseudo` 审计 `!important` / `:global` / 上下文。
3. 用 `selftest.css` 确认冲突检测器可触发：
   `node analyze.js configs/selftest.json planall`（应报 1 组 1 冲突）。
4. `node tsx-evidence.js <config>` 提取 TSX 证据；
   `node snapshot-pw.js <config> mbase`（mock 基线，8 宽度）+ 再拍一次对比确认数据态稳定；
   `SNAP_URL=<realUrl> node snapshot-pw.js <config> ev2-real` 补真实态证据。
5. `node transform.js <config>` 生成合并候选到 workDir（含四重不变量自检：
   重解析零警告 / 声明多重集守恒 / 未触组一致 / 权威段逐字节一致），人工审查 report。
6. `node equivalence.js <config> <备份> <候选>` 级联等价终裁：全部元素原型 × 8 断点 ×
   动效状态 × 伪元素维度逐属性比较胜者声明，必须 0 差异。
7. 落盘（复制候选 + touch 触发编辑器重载 + 哈希核对）；复拍快照
   `node snapshot-pw.js <config> cur` 后用 `node geodiff.js` 与 mbase 逐宽度对比；
   跑页面对应 vitest 套件；提交。
8. 注释收尾：transform report 中的 ORPHAN-COMMENT 标记逐个人工裁决；
   `node cssom-identity.js <config> git:HEAD:<path> <workingFile>` 证明注释类修复零语义影响。

## 已知边界

- 证据盲区：既不在两种采样数据态 DOM、又不在 TSX 词法组合中的类组合（wildcards 缓解）。
- 非 module 的全局 CSS 需先确认目标文件在 bundle 中连续、且类名未在其他文件交错定义。
- 快照门禁必须用确定性 mock 数据源；真实后端数据会漂移，只作证据与人工核查。
- 编辑器对该类大文件偶发 `ftruncate` 错误（原样重试即可）与外部写入后的缓冲不同步
  （落盘后 touch + 哈希核对，再让编辑工具介入）。
