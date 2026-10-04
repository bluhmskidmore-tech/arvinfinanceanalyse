---
name: moss-management-book
description: "【MOSS管理层决策册】用于生成或修订 1280×720 幻灯片式管理层 HTML 报告（宏观利率策略册、金融市场经营分析册、监管专册等 output/pdf 下的决策材料）。生成此类报告时必须使用本技能，禁止复制上一份报告的内嵌 CSS 演化。"
---

# MOSS 管理层决策册

生成 1280×720 幻灯片式管理层 HTML 报告的唯一入口。模板资产在
`docs/report-templates/management-book/`，报告是模板的实例，不是模板本身。

## 铁律

1. **禁止以旧报告为底稿。** 不复制任何既有产出 HTML 的 `<style>` 块。样式一律来自
   `template.css` + `brand.css`，页面结构一律来自 `components.html` 的骨架。
2. **文字先过 `WRITING.md`。** 标题 ≤18 字单结论、免责声明只在页脚、一句话最多 2 个数字、
   内部代号首次出现给中文说明、每页容量超限就拆页。
   **AI 生成的分析文字必须执行 WRITING.md 第 9 节"AI 文风净化"并完成三步自查：
   正文零反问设问、零空转填充词（值得注意的是/综上所述/总体来看等）、零机械排比。**
3. **数字必须当期核对。** `components.html` 里的数字全部是排版占位，逐个替换；
   来源与报告日写入 `deck` 或页脚，不同报告日的数据不混排在同一指标组里。
4. **语义色不挪用。** 绿=正常/有利，金=关注/待定，红=警示/不利，蓝=口径/说明。
   章节区分靠 `chapter-chip` 文案，不靠换色。

## 工作流

1. 读 `docs/report-templates/management-book/` 下四个文件：`template.css`、`brand.css`、
   `components.html`、`WRITING.md`。
2. 按册结构选择页型骨架（封面/摘要/决策/图表/表格/监管），复制 `<section>` 并填充当期内容。
3. 产出单文件 HTML：把两个 CSS 内联进 `<head><style>`；文件命名沿用
   `主题_版本类型_截至YYYYMMDD_VYYYYMMDD.N.html`，输出到 `output/pdf/`。
4. 用 Playwright（`frontend/node_modules` 已装）以 1280×720 视口逐页截图抽查：
   封面、信息密度最高的决策页、至少一个图表页。核对无溢出、无字号小于 12.5px 的正文、
   深色页部门标与行徽显示正确。
5. 报告如需新页型或新组件，先扩充模板资产（并同步容量约束），再回到报告实例，
   不要在报告 HTML 里写一次性样式。

## 修订模板

- 版式/颜色/字号问题 → 改 `template.css`（顶部有四条硬约束，勿破坏）。
- 文字表述问题 → 改 `WRITING.md`。
- 页面结构/容量问题 → 改 `components.html`。
- 修订后用浏览器渲染 `components.html` 抽查六个骨架页，再应用到下一份报告。
