-- MOSS:STMT
-- 市场门控实时标签锚点表（治理发现 G-1 High：状态标签系统性不可复现，官方回测
-- 逐日敞口 100% 依赖重放，广度/涨停供数修订后标签漂移 12/38 信号日）。
-- 每交易日一行：门控状态、敞口、四条件明细与来源版本，在 gate 求值当日写入
-- （source='realtime'），此后冻结——后续重放与本表不一致即为标签漂移证据。
--
-- 读取契约：backend/app/core_finance/gate_exposure_series.py 的
-- PERSISTED_EXPOSURE_TABLES 白名单预留了 livermore_monitor_append /
-- livermore_gate_history / livermore_gate_supplement 三个表名，经同一通用加载器
-- 按 trade_date（日期列）/ exposure（敞口列）/ state（状态列）读取。三者语义完全
-- 重叠（同一"每日 gate 状态+敞口"点位的三个备选落点，无任何存量数据），故只落地
-- 本表作为唯一权威锚点，避免同一点位出现多源分歧。
--
-- 回填边界：历史日期的实时标签已不可复现，本表不做历史回填（避免用当前供数
-- 重放伪造"当时状态"）；从落地日起随每日刷新链向前积累，缺行日期由读取端
-- 回放（source='replayed'）兜底。
-- 写路径仅 backend/app/tasks/livermore_gate_history_materialize.py，由
-- backend/app/tasks/livermore_gate_supplement.py 在补充表写入后同锁调用
--（API/services 只读）。
create table if not exists livermore_gate_history (
  trade_date varchar not null,
  state varchar not null,
  exposure double not null,
  passed_conditions integer,
  available_conditions integer,
  required_conditions integer,
  conditions_json varchar,
  source varchar not null,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar,
  persisted_at varchar,
  primary key (trade_date)
)
