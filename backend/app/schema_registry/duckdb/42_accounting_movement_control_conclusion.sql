-- MOSS:STMT
-- 跨月勾稽结论（continuous / broken / no_prior_month）。
--
-- 行内恒等式 balance_change := current - previous 在代数上恒闭合，对"本月期初
-- 是否等于上月期末"零覆盖；跨月断点是唯一能证伪该口径的信号。断点此前只写进
-- governance manifest 的 lineage，读模型与页面完全看不见，用户无法把"真的对不
-- 平"（mismatch）和"根本没有对手方"（gl_only）区分开。本列把已经算出的结论落到行上。
--
-- NULL 表示该行写于本列落地之前（未记录），与 'no_prior_month'（有判定、但没有
-- 可比上月）语义不同，读取端不得把两者合并。
alter table fact_accounting_asset_movement_monthly
add column if not exists chain_status varchar
-- MOSS:STMT
-- 头寸侧实际命中的折算口径：总账用 CNX 标记本外币折人民币，ZQTZ 正式头寸表用
-- CNY 表示同一口径（native 才是原币），所以取值通常是 'CNY'，将来 ZQTZ 真的产出
-- 同名 'CNX' 行时会自动切过去。'unavailable' 表示该报告日两个候选口径都没有资产
-- 头寸行——此时 zqtz_amount / reconciliation_diff 是"无对手方"的产物而不是真实差额，
-- 读取端必须按不适用呈现，不能印 0 或按差额解读。
alter table fact_accounting_asset_movement_monthly
add column if not exists position_source_basis varchar
