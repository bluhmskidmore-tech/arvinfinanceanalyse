-- 只读诊断：日均 ADB「负债 · 其它」桶在 formal 里可能来自哪些行
-- 与后端 _liability_bond_display_category / _clean_cat(product_type) 口径对齐：
--   ZQTZ 发行/负债侧：sub_type、business_type_primary、bond_type 三者 trim 后全空 → 计入「其它」
--   TYW 负债侧：product_type trim 后为空 →计入「其它」
--
-- 用法（PowerShell 示例，请替换为你的 moss.duckdb 路径和日期）：
--   duckdb "F:\path\to\moss.duckdb" -c ".read f:/MOSS-V3/scripts/diagnose_adb_liabilities_other.sql"
--
-- ========== 请修改下面的区间，与页面选择一致 ==========
-- 开始日、结束日（含）

WITH params AS (
  SELECT
    date '2025-12-31' AS d_start,
    date '2025-12-31' AS d_end
),

-- ZQTZ：与 ADB 相同的「发行/负债」口径（简化版：与 core 里 issued 近似）
zqtz_liab AS (
  SELECT
    cast(f.report_date AS date) AS report_date,
    f.instrument_code,
    coalesce(f.sub_type, '') AS st,
    coalesce(f.business_type_primary, '') AS btp,
    coalesce(f.bond_type, '') AS bt,
    coalesce(f.asset_class, '') AS aclass,
    coalesce(f.position_scope, '') AS pscope,
    coalesce(f.is_issuance_like, false) AS issuance,
    f.market_value_amount
  FROM fact_formal_zqtz_balance_daily f
  CROSS JOIN params p
  WHERE f.currency_basis = 'CNY'
    AND cast(f.report_date AS date) BETWEEN p.d_start AND p.d_end
    AND (
      f.is_issuance_like = true
      OR lower(trim(coalesce(f.position_scope, ''))) = 'liability'
      OR coalesce(f.asset_class, '') LIKE '%发行%'
    )
),

zqtz_other AS (
  SELECT *
  FROM zqtz_liab
  WHERE
    nullif(trim(st), '') IS null
    AND nullif(trim(btp), '') IS null
    AND nullif(trim(bt), '') IS null
),

tyw_liab AS (
  SELECT
    cast(t.report_date AS date) AS report_date,
    t.position_id,
    coalesce(t.product_type, '') AS pt,
    coalesce(t.position_scope, '') AS pscope,
    t.principal_amount
  FROM fact_formal_tyw_balance_daily t
  CROSS JOIN params p
  WHERE t.currency_basis = 'CNY'
    AND cast(t.report_date AS date) BETWEEN p.d_start AND p.d_end
    AND lower(trim(coalesce(t.position_scope, ''))) = 'liability'
),

tyw_other AS (
  SELECT * FROM tyw_liab WHERE nullif(trim(pt), '') IS null
)

SELECT 'ZQTZ → 其它（三字段全空）' AS bucket, count(*) AS row_cnt,
       round(sum(market_value_amount), 2) AS amount_sum_native
FROM zqtz_other
UNION ALL
SELECT 'TYW → 其它（product_type 空）', count(*), round(sum(principal_amount), 2)
FROM tyw_other;

-- 明细抽样：看是哪些 instrument / 缺哪几列（各取前 30 行）
-- SELECT * FROM zqtz_other ORDER BY report_date, instrument_code LIMIT 30;
-- SELECT * FROM tyw_other ORDER BY report_date, position_id LIMIT 30;
