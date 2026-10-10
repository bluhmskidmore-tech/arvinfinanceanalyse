"""团队绩效考核底稿（2025 静态工作簿）只读服务。

底稿数据从前端 `teamPerformancePageModel.ts` 的
`ASSESSMENT_CENTERS_2025` / `CENTER_PNL_MAPPINGS_2025` 常量原样迁移（数值一字不差），
使汇总分（workbook_score / score_rate / total_workbook_score）在后端计算下发，
前端不再持有底稿常量、也不再本地加总。

口径边界：这是 Excel 考核方案底稿的静态镜像，不是正式绩效读模型；
envelope 以 `basis=analytical`、`formal_use_allowed=false` 下发，
payload 内附 `caliber_label` / `caliber_note` 供页面直接展示口径说明。

汇总规则与迁移前的前端算法保持逐位一致：
- 部室顺序 = 底稿指标中 center_id 首次出现顺序；
- weight_total / workbook_score 按底稿行序做浮点累加（score 为 None 记 0）；
- score_rate = workbook_score / weight_total（weight_total<=0 时为 None）；
- total_workbook_score 按部室顺序累加各部室 workbook_score。
"""
from __future__ import annotations

import uuid

from backend.app.schemas.team_performance import (
    AssessmentCenterPnlMapping,
    AssessmentCenterSummary,
    AssessmentIndicatorItem,
    AssessmentWorkbookPayload,
)
from backend.app.services.formal_result_runtime import (
    build_analytical_result_meta,
    build_formal_result_envelope,
)

RESULT_KIND = "team_performance.assessment_workbook"
SOURCE_VERSION = "sv_assessment_workbook_2025_static"
RULE_VERSION = "rv_team_performance_workbook_v1"
CACHE_VERSION = "cv_team_performance_workbook_v1"

ASSESSMENT_YEAR = 2025
AS_OF_DATE = "2025-12-31"
CALIBER_LABEL = "静态底稿·非正式口径（后端下发）"
CALIBER_NOTE = (
    "2025 部室考核底稿与汇总分由后端静态底稿服务下发"
    "（result_kind=team_performance.assessment_workbook，basis=analytical），"
    "数据为 Excel 考核方案底稿已有得分的原样迁移，不重算评分规则，"
    "未接入正式绩效考核读模型，不作正式绩效口径。"
)
SOURCE_LABEL = "2025 年金融市场部绩效考核方案 Excel 底稿（静态迁移）"

# 原前端 ASSESSMENT_CENTERS_2025，字段改 snake_case，数值与文本一字不差。
ASSESSMENT_INDICATORS_2025: tuple[dict[str, object], ...] = (
    {
        "center_id": "product-market",
        "center_name": "产品与市场室",
        "indicator_category": "效益类",
        "metric": "金融投资营业收入",
        "target": "2025年结构化融资实现收入3500万元（ftp价格按照1.75%）",
        "weight": 10,
        "scoring_text": "按照完成额进行线性打分，完成额/3500*10分，上限为12分",
        "actual": "3861",
        "progress": "110.31%",
        "score": 11.0314285714,
        "source_row": 3,
    },
    {
        "center_id": "product-market",
        "center_name": "产品与市场室",
        "indicator_category": "效益类",
        "metric": "产业基金投资收益",
        "target": "推动产业基金收益调整，全年实现估值损益变动4.3亿",
        "weight": 10,
        "scoring_text": "根据产业基金收益情况线性打分",
        "actual": "5.3亿",
        "progress": "100%",
        "score": 10,
        "source_row": 4,
    },
    {
        "center_id": "product-market",
        "center_name": "产品与市场室",
        "indicator_category": "规模类",
        "metric": "金融债发行规模",
        "target": "根据全行资产负债规划，完成全年永续债及金融债发行计划",
        "weight": 15,
        "scoring_text": "根据发行计划完成情况进行打分",
        "actual": "完成",
        "progress": "100%",
        "score": 15,
        "source_row": 5,
    },
    {
        "center_id": "self-investment",
        "center_name": "自营投资室",
        "indicator_category": "效益类",
        "metric": "营业净收入",
        "target": "2025年营业净收入16.8亿元",
        "weight": 30,
        "scoring_text": "按照完成额进行线性（其中利息收入及非息收入统一核算）打分，完成额/15.45*30分，上限33分",
        "actual": "14.77",
        "progress": "95.60%",
        "score": 28.6796116505,
        "source_row": 10,
    },
    {
        "center_id": "self-investment",
        "center_name": "自营投资室",
        "indicator_category": "效益类",
        "metric": "中间业务收入",
        "target": "2025年托管业务联动实现中间业务收入1500万元，2025年利率债承销量不低于80亿元",
        "weight": 5,
        "scoring_text": "按照完成额进行线性打分，(托管中收/1500+利率债承销/80)/2*5分，上限5.5分",
        "actual": "托管3810/1500，利率债承分销7858万元",
        "progress": "完成",
        "score": 5.5,
        "source_row": 11,
    },
    {
        "center_id": "self-investment",
        "center_name": "自营投资室",
        "indicator_category": "规模类",
        "metric": "同业活期存款及托管业务规模",
        "target": "低息同业活期日均新增60亿元，托管业务规模400亿元",
        "weight": 5,
        "scoring_text": "挂钩部门同业活期及托管业务规模指标（同业活期及托管业务各占50%权重），上限5.5分",
        "actual": "低息同业活期日均新增93.3亿元；托管业务规模480.6亿元",
        "progress": "低息同业活期：155.5%；托管规模：120.15%",
        "score": 5,
        "source_row": 12,
    },
    {
        "center_id": "self-investment",
        "center_name": "自营投资室",
        "indicator_category": "客群类",
        "metric": "投资业务客群",
        "target": "投资业务客群较去年增长5%",
        "weight": 5,
        "scoring_text": "根据投资的企业及同业客群增长情况线性打分，上限5分",
        "actual": "2025年较2024年增加67家，增幅34.36%",
        "progress": "完成",
        "score": 5,
        "source_row": 13,
    },
    {
        "center_id": "interbank-finance",
        "center_name": "金融同业部",
        "indicator_category": "效益类",
        "metric": "营业净收入",
        "target": "全年实现拆放同业营业净收入1.05亿元（ftp价格按照1.75%）",
        "weight": 15,
        "scoring_text": "按照完成额进行线性打分，完成额/1.05*15，上限17分",
        "actual": "1.24",
        "progress": "118.10%",
        "score": 17,
        "source_row": 18,
    },
    {
        "center_id": "interbank-finance",
        "center_name": "金融同业部",
        "indicator_category": "效益类",
        "metric": "同业负债成本压降",
        "target": "人民币同业负债成本不超过1.83%",
        "weight": 10,
        "scoring_text": "按照完成情况进行打分，每超1BP，扣1分，上限10分",
        "actual": "1.74%",
        "progress": "完成",
        "score": 10,
        "source_row": 19,
    },
    {
        "center_id": "interbank-finance",
        "center_name": "金融同业部",
        "indicator_category": "效益类",
        "metric": "同业银团贷款中间业务收入",
        "target": "全年同业银团贷款中间业务收入1200万元",
        "weight": 10,
        "scoring_text": "按照完成额进行线性打分，上限10分",
        "actual": "1222.58",
        "progress": "101.88%",
        "score": 10,
        "source_row": 20,
    },
    {
        "center_id": "interbank-finance",
        "center_name": "金融同业部",
        "indicator_category": "规模类",
        "metric": "同业活期存款及托管业务规模",
        "target": "低息同业活期日均新增60亿元，托管业务规模400亿元",
        "weight": 5,
        "scoring_text": "挂钩部门同业活期及托管业务规模指标（同业活期及托管业务各占50%权重），上限10分",
        "actual": "低息同业活期日均新增93.3亿元；托管业务规模480.6亿元",
        "progress": "低息同业活期：155.5%；托管规模：120.15%",
        "score": 6.89125,
        "source_row": 21,
    },
    {
        "center_id": "interbank-finance",
        "center_name": "金融同业部",
        "indicator_category": "客群类",
        "metric": "同业往来业务客群",
        "target": "同业往来客群较去年增长10户",
        "weight": 5,
        "scoring_text": "根据同业客群数量增长情况线性打分，上限10分",
        "actual": "2025年较2024年增加67家，增幅34.36%",
        "progress": "完成",
        "score": 10,
        "source_row": 22,
    },
    {
        "center_id": "money-trading",
        "center_name": "货币交易室",
        "indicator_category": "效益类",
        "metric": "经营效益",
        "target": "全年正逆回购价差不低于6BP",
        "weight": 15,
        "scoring_text": "根据完成情况进行打分，每低于1BP扣1分",
        "actual": "差额0.1BP",
        "progress": "待核准",
        "score": 9,
        "source_row": 27,
    },
    {
        "center_id": "money-trading",
        "center_name": "货币交易室",
        "indicator_category": "效益类",
        "metric": "人民币同业负债成本",
        "target": "人民币同业负债成本不超过1.83%",
        "weight": 15,
        "scoring_text": "根据完成情况进行打分，每超1BP扣1分",
        "actual": "1.74%",
        "progress": "完成",
        "score": 15,
        "source_row": 28,
    },
    {
        "center_id": "money-trading",
        "center_name": "货币交易室",
        "indicator_category": "规模类",
        "metric": "人民币超额准备金年日均余额",
        "target": "年日均不超过40亿元",
        "weight": 10,
        "scoring_text": "超过1亿元扣1分，每低5亿元，加1分，上限12分",
        "actual": "36.35",
        "progress": "100%",
        "score": 10,
        "source_row": 29,
    },
    {
        "center_id": "money-trading",
        "center_name": "货币交易室",
        "indicator_category": "客群类",
        "metric": "货币交易客群",
        "target": "货币对话交易客群数量较去年同期增长10%",
        "weight": 5,
        "scoring_text": "根据货币对话交易客群增长情况线性打分",
        "actual": "2025年较2024年增加46家，增幅50%",
        "progress": "完成",
        "score": 5,
        "source_row": 30,
    },
    {
        "center_id": "bond-trading",
        "center_name": "债券交易室",
        "indicator_category": "效益及客群类",
        "metric": "营业净收入",
        "target": "2025年营业收入12.05亿元",
        "weight": 35,
        "scoring_text": "按照完成额进行线性打分，完成额/12.05*35分，上限39分",
        "actual": "16.89",
        "progress": "140.17%",
        "score": 39,
        "source_row": 35,
    },
    {
        "center_id": "bond-trading",
        "center_name": "债券交易室",
        "indicator_category": "效益及客群类",
        "metric": "中间业务收入",
        "target": "债券借贷净收入850万元，利率债承销收入8424万元",
        "weight": 5,
        "scoring_text": "根据中收情况线性打分（借贷净收入完成额/850*50%+承销收入/6740*50%）*5分",
        "actual": "完成",
        "progress": "100%",
        "score": 5,
        "source_row": 36,
    },
    {
        "center_id": "bond-trading",
        "center_name": "债券交易室",
        "indicator_category": "效益及客群类",
        "metric": "交易客群",
        "target": "债券借贷类低风险业务授信客群较去年同期增长5%",
        "weight": 5,
        "scoring_text": "根据客群增长情况线性打分",
        "actual": "2025年较2024年增加11家，增幅5.58%",
        "progress": "完成",
        "score": 5,
        "source_row": 37,
    },
    {
        "center_id": "fx-derivatives",
        "center_name": "外汇及衍生品交易室",
        "indicator_category": "效益及客群类",
        "metric": "营业净收入",
        "target": "美元资产负债营业净收入1.2亿元",
        "weight": 30,
        "scoring_text": "按照完成额进行线性打分，完成额/1.2*30分，上限33分",
        "actual": "1.69",
        "progress": "140.83%",
        "score": 33,
        "source_row": 42,
    },
    {
        "center_id": "fx-derivatives",
        "center_name": "外汇及衍生品交易室",
        "indicator_category": "效益及客群类",
        "metric": "外汇交易客群",
        "target": "外汇交易客群数量较去年增长10%",
        "weight": 10,
        "scoring_text": "根据外汇交易客群增长情况线性打分",
        "actual": "2025年较2024年增加8家，增幅21.06%",
        "progress": "完成",
        "score": 10,
        "source_row": 43,
    },
    {
        "center_id": "fx-derivatives",
        "center_name": "外汇及衍生品交易室",
        "indicator_category": "效益及客群类",
        "metric": "外汇市场影响力",
        "target": "交易中心银行间外汇市场100强",
        "weight": 5,
        "scoring_text": "未达目标不得分",
        "actual": "完成",
        "progress": "完成",
        "score": 5,
        "source_row": 44,
    },
    {
        "center_id": "customer-business",
        "center_name": "代客业务室",
        "indicator_category": "效益类",
        "metric": "营业净收入",
        "target": "全年实现远期结售汇及外汇买卖营收1000万元人民币",
        "weight": 10,
        "scoring_text": "根据代客衍生业务收入情况线性打分，完成额/1000*10，上限10分",
        "actual": "1201",
        "progress": "120.1%",
        "score": 10,
        "source_row": 49,
    },
    {
        "center_id": "customer-business",
        "center_name": "代客业务室",
        "indicator_category": "效益类",
        "metric": "代客外汇业务量",
        "target": "代客外汇买卖交易量较上一年度增长100%；代客外汇远期业务量较上一年度增长100%",
        "weight": 20,
        "scoring_text": "根据代客外汇买卖业务量情况线性打分，每一项各占10分，每项上限11分",
        "actual": "买卖2.43亿美元；远期2.49亿美元",
        "progress": "完成",
        "score": 22,
        "source_row": 50,
    },
    {
        "center_id": "customer-business",
        "center_name": "代客业务室",
        "indicator_category": "产品类",
        "metric": "代客业务产品",
        "target": "代客业务新增研发3个产品",
        "weight": 10,
        "scoring_text": "根据产品开发情况打分，少开发一款产品扣2分。",
        "actual": "新增研发4个产品",
        "progress": "完成",
        "score": 10,
        "source_row": 51,
    },
    {
        "center_id": "customer-business",
        "center_name": "代客业务室",
        "indicator_category": "客群类",
        "metric": "代客业务客群规模",
        "target": "即期结售汇业务业务量在5万美元以上的客户数量达到2500户，远期结售汇业务业务量在100万美元以上的新增客户50%",
        "weight": 5,
        "scoring_text": "根据上述代客业务客群增长情况线性打分，上限7分",
        "actual": "即期2700户；远期新增客户82%",
        "progress": "108% / 164%",
        "score": 6.52,
        "source_row": 52,
    },
    {
        "center_id": "customer-business",
        "center_name": "代客业务室",
        "indicator_category": "市场风险指标控制",
        "metric": "结构性存款低收益触发占比",
        "target": "结构性存款全年到期产品中，触发低收益的业务占比小于5%",
        "weight": 5,
        "scoring_text": "根据触发低收益占比打分，每超1%扣1分",
        "actual": "3.88%",
        "progress": "完成",
        "score": 5,
        "source_row": 53,
    },
    {
        "center_id": "customer-business",
        "center_name": "代客业务室",
        "indicator_category": "效益类",
        "metric": "利率债承销手续费收入",
        "target": "全年实现增值税后收入8424万元",
        "weight": 20,
        "scoring_text": "按照完成额进行线性打分，完成额/6740*20分，上限23分",
        "actual": "7858",
        "progress": "93.28%",
        "score": 18.6562203229,
        "source_row": 57,
        "block_label": "利率债承分销室",
    },
    {
        "center_id": "customer-business",
        "center_name": "代客业务室",
        "indicator_category": "规模类",
        "metric": "信用债交易流转",
        "target": "全年实现省内信用债卖出交易量35亿元",
        "weight": 10,
        "scoring_text": "按照完成额进行线性打分",
        "actual": "实际卖出66.58亿",
        "progress": "完成",
        "score": 10,
        "source_row": 58,
        "block_label": "利率债承分销室",
    },
    {
        "center_id": "customer-business",
        "center_name": "代客业务室",
        "indicator_category": "规模类",
        "metric": "同业活期存款及托管业务规模",
        "target": "低息同业活期日均新增60亿元，托管业务规模400亿元",
        "weight": 5,
        "scoring_text": "挂钩部门同业活期及托管业务规模指标（同业活期及托管业务各占50%权重），上限5分",
        "actual": "低息同业活期日均新增93.3亿元；托管业务规模480.6亿元",
        "progress": "完成",
        "score": 5,
        "source_row": 59,
        "block_label": "利率债承分销室",
    },
    {
        "center_id": "customer-business",
        "center_name": "代客业务室",
        "indicator_category": "客群类",
        "metric": "信用债交易客群",
        "target": "信用债二级市场交易对手客群新增10%",
        "weight": 10,
        "scoring_text": "根据信用债交易对手客群增长情况线性打分",
        "actual": "2025年较2024年增加11家，增幅38%",
        "progress": "完成",
        "score": 10,
        "source_row": 60,
        "block_label": "利率债承分销室",
    },
    {
        "center_id": "jinan-branch",
        "center_name": "济南分部",
        "indicator_category": "效益类",
        "metric": "经营效益",
        "target": "挂钩金融同业部营业净收入及中间业务收入指标",
        "weight": 20,
        "scoring_text": "按照完成额进行线性打分（金融同业部营业净收入得分60%+金融同业部中间业务收入得分*40%）",
        "actual": "20",
        "progress": "挂钩引用",
        "score": 20,
        "source_row": 65,
    },
    {
        "center_id": "jinan-branch",
        "center_name": "济南分部",
        "indicator_category": "规模类",
        "metric": "同业活期",
        "target": "全年同业活期存款日均新增60亿元",
        "weight": 10,
        "scoring_text": "挂钩部门同业活期存款完成情况",
        "actual": "10",
        "progress": "低息同业活期日均新增93.3亿元",
        "score": 10,
        "source_row": 66,
    },
    {
        "center_id": "jinan-branch",
        "center_name": "济南分部",
        "indicator_category": "客群类",
        "metric": "同业授信客户数",
        "target": "同业授信客户数较去年增长5户",
        "weight": 10,
        "scoring_text": "根据同业授信客户数量增长情况线性打分，新增同业授信客户数/5*10，上限12分",
        "actual": "12",
        "progress": "截至2025年末同业授信客户数251户，较2024年末增加12户",
        "score": 12,
        "source_row": 67,
    },
)

# 原前端 CENTER_PNL_MAPPINGS_2025，字段改 snake_case，内容一字不差。
CENTER_PNL_MAPPINGS_2025: tuple[dict[str, object], ...] = (
    {
        "center_id": "product-market",
        "endpoint": "product-category-ytd",
        "row_id": "intermediate_business_income",
        "pnl_field": "business_net_income",
        "confidence": "medium",
        "note": "中间业务收入与产品与市场室协同收益相关，仍需与金融债发行指标区分。",
    },
    {
        "center_id": "product-market",
        "endpoint": "by-business-ytd",
        "row_id": "asset_zqtz_detail_structured_finance_broker",
        "confidence": "high",
        "note": "结构化产业基金（产业基金部分）作为金融投资营业收入证据。",
    },
    {
        "center_id": "self-investment",
        "endpoint": "by-business-ytd",
        "row_id": "asset_zqtz_public_fund",
        "confidence": "high",
    },
    {
        "center_id": "self-investment",
        "endpoint": "by-business-ytd",
        "row_id": "asset_zqtz_local_government_bond",
        "confidence": "high",
    },
    {
        "center_id": "self-investment",
        "endpoint": "by-business-ytd",
        "row_id": "asset_zqtz_commercial_financial_bond",
        "confidence": "high",
    },
    {
        "center_id": "self-investment",
        "endpoint": "by-business-ytd",
        "row_id": "asset_zqtz_nonfinancial_enterprise_bond",
        "confidence": "high",
    },
    {
        "center_id": "self-investment",
        "endpoint": "by-business-ytd",
        "row_id": "asset_zqtz_abs",
        "confidence": "high",
    },
    {
        "center_id": "self-investment",
        "endpoint": "by-business-ytd",
        "row_id": "asset_zqtz_non_bottom_investment",
        "confidence": "medium",
    },
    {
        "center_id": "self-investment",
        "endpoint": "by-business-ytd",
        "row_id": "asset_zqtz_railway_bond",
        "confidence": "high",
    },
    {
        "center_id": "self-investment",
        "endpoint": "by-business-ytd",
        "row_id": "asset_zqtz_other_debt_financing",
        "confidence": "medium",
    },
    {
        "center_id": "self-investment",
        "endpoint": "by-business-ytd",
        "row_id": "asset_zqtz_central_bank_bill",
        "confidence": "medium",
    },
    {
        "center_id": "interbank-finance",
        "endpoint": "product-category-ytd",
        "row_id": "interbank_lending_assets",
        "pnl_field": "business_net_income",
        "scale_field": "cny_scale",
        "confidence": "high",
    },
    {
        "center_id": "interbank-finance",
        "endpoint": "product-category-ytd",
        "row_id": "interbank_deposits",
        "pnl_field": "business_net_income",
        "scale_field": "cny_scale",
        "confidence": "medium",
    },
    {
        "center_id": "interbank-finance",
        "endpoint": "product-category-ytd",
        "row_id": "interbank_borrowings",
        "pnl_field": "business_net_income",
        "scale_field": "cny_scale",
        "confidence": "medium",
    },
    {
        "center_id": "interbank-finance",
        "endpoint": "product-category-ytd",
        "row_id": "repo_liabilities",
        "pnl_field": "business_net_income",
        "scale_field": "cny_scale",
        "confidence": "medium",
    },
    {
        "center_id": "interbank-finance",
        "endpoint": "product-category-ytd",
        "row_id": "interbank_cds",
        "pnl_field": "business_net_income",
        "scale_field": "cny_scale",
        "confidence": "medium",
    },
    {
        "center_id": "interbank-finance",
        "endpoint": "product-category-ytd",
        "row_id": "credit_linked_notes",
        "pnl_field": "business_net_income",
        "scale_field": "cny_scale",
        "confidence": "medium",
    },
    {
        "center_id": "money-trading",
        "endpoint": "product-category-ytd",
        "row_id": "repo_assets",
        "pnl_field": "business_net_income",
        "scale_field": "cny_scale",
        "confidence": "high",
    },
    {
        "center_id": "money-trading",
        "endpoint": "product-category-ytd",
        "row_id": "repo_liabilities",
        "pnl_field": "business_net_income",
        "scale_field": "cny_scale",
        "confidence": "high",
    },
    {
        "center_id": "bond-trading",
        "endpoint": "by-business-ytd",
        "row_id": "asset_zqtz_policy_financial_bond",
        "confidence": "high",
    },
    {
        "center_id": "bond-trading",
        "endpoint": "by-business-ytd",
        "row_id": "asset_zqtz_local_government_bond",
        "confidence": "high",
    },
    {
        "center_id": "bond-trading",
        "endpoint": "by-business-ytd",
        "row_id": "asset_zqtz_interbank_cd",
        "confidence": "high",
    },
    {
        "center_id": "bond-trading",
        "endpoint": "by-business-ytd",
        "row_id": "asset_zqtz_treasury_bond",
        "confidence": "high",
    },
    {
        "center_id": "fx-derivatives",
        "endpoint": "product-category-ytd",
        "row_id": "interbank_lending_assets",
        "pnl_field": "foreign_net",
        "scale_field": "foreign_scale",
        "confidence": "medium",
    },
    {
        "center_id": "fx-derivatives",
        "endpoint": "product-category-ytd",
        "row_id": "bond_investment",
        "pnl_field": "foreign_net",
        "scale_field": "foreign_scale",
        "confidence": "medium",
    },
    {
        "center_id": "fx-derivatives",
        "endpoint": "product-category-ytd",
        "row_id": "repo_liabilities",
        "pnl_field": "foreign_net",
        "scale_field": "foreign_scale",
        "confidence": "medium",
    },
    {
        "center_id": "fx-derivatives",
        "endpoint": "product-category-ytd",
        "row_id": "derivatives",
        "pnl_field": "business_net_income",
        "confidence": "high",
        "note": "汇兑损益及衍生条目按业务净收入展示。",
    },
    {
        "center_id": "customer-business",
        "endpoint": "product-category-ytd",
        "row_id": "intermediate_business_income",
        "pnl_field": "business_net_income",
        "confidence": "high",
    },
    {
        "center_id": "customer-business",
        "endpoint": "by-business-ytd",
        "row_id": "asset_zqtz_nonfinancial_enterprise_bond",
        "confidence": "medium",
        "note": "信用债交易流转以非金融企业债券 YTD 损益作辅助证据。",
    },
    {
        "center_id": "jinan-branch",
        "endpoint": "product-category-ytd",
        "row_id": "interbank_lending_assets",
        "pnl_field": "business_net_income",
        "scale_field": "cny_scale",
        "confidence": "linked",
        "note": "济南分部挂钩金融同业部证据，仅作引用不并入加总。",
    },
    {
        "center_id": "jinan-branch",
        "endpoint": "product-category-ytd",
        "row_id": "intermediate_business_income",
        "pnl_field": "business_net_income",
        "confidence": "linked",
        "note": "济南分部挂钩金融同业部中间业务收入证据，仅作引用。",
    },
)


def _build_center_summaries(
    indicators: list[AssessmentIndicatorItem],
) -> list[AssessmentCenterSummary]:
    center_order: list[str] = []
    for indicator in indicators:
        if indicator.center_id not in center_order:
            center_order.append(indicator.center_id)

    summaries: list[AssessmentCenterSummary] = []
    for center_id in center_order:
        center_indicators = [item for item in indicators if item.center_id == center_id]
        weight_total = 0.0
        workbook_score = 0.0
        has_pending_score = False
        for item in center_indicators:
            weight_total += item.weight
            workbook_score += item.score if item.score is not None else 0.0
            if item.score is None:
                has_pending_score = True
        summaries.append(
            AssessmentCenterSummary(
                center_id=center_id,
                center_name=center_indicators[0].center_name,
                weight_total=weight_total,
                workbook_score=workbook_score,
                has_pending_score=has_pending_score,
                score_rate=workbook_score / weight_total if weight_total > 0 else None,
                indicators=center_indicators,
            )
        )
    return summaries


def build_assessment_workbook_payload() -> AssessmentWorkbookPayload:
    indicators = [AssessmentIndicatorItem(**item) for item in ASSESSMENT_INDICATORS_2025]
    mappings = [AssessmentCenterPnlMapping(**item) for item in CENTER_PNL_MAPPINGS_2025]
    centers = _build_center_summaries(indicators)
    total_workbook_score = 0.0
    for center in centers:
        total_workbook_score += center.workbook_score
    return AssessmentWorkbookPayload(
        assessment_year=ASSESSMENT_YEAR,
        caliber_label=CALIBER_LABEL,
        caliber_note=CALIBER_NOTE,
        source_label=SOURCE_LABEL,
        centers=centers,
        mappings=mappings,
        total_workbook_score=total_workbook_score,
        total_center_count=len(centers),
    )


def assessment_workbook_envelope() -> dict[str, object]:
    """静态底稿 envelope：basis=analytical、formal_use_allowed=false。"""
    payload = build_assessment_workbook_payload()
    meta = build_analytical_result_meta(
        trace_id=uuid.uuid4().hex,
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=SOURCE_VERSION,
        rule_version=RULE_VERSION,
        quality_flag="ok",
        as_of_date=AS_OF_DATE,
        date_basis="assessment_year_2025_static_workbook",
        filters_applied={"assessment_year": ASSESSMENT_YEAR},
        tables_used=[],
        evidence_rows=len(ASSESSMENT_INDICATORS_2025),
    )
    return build_formal_result_envelope(
        result_meta=meta,
        result_payload=payload.model_dump(mode="json"),
    )
