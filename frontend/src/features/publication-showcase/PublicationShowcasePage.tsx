import { Link, useSearchParams } from "react-router-dom";

import { LightIcon, type LightIconName } from "../../components/LightIcon";

import "./PublicationShowcasePage.css";

type ShowcaseView = "overview" | "investment" | "operations" | "agent";
type Tone = "accent" | "positive" | "warning" | "negative" | "neutral";

type NavItem = {
  key: ShowcaseView;
  label: string;
  caption: string;
  icon: LightIconName;
};

const NAV_ITEMS: NavItem[] = [
  { key: "overview", label: "系统总览", caption: "MOSS 是什么", icon: "appstore" },
  { key: "investment", label: "投资判断", caption: "市场与持仓", icon: "line-chart" },
  { key: "operations", label: "经营损益", caption: "口径与归因", icon: "bar-chart" },
  { key: "agent", label: "受控 AI 分析", caption: "证据与边界", icon: "file-search" },
];

const VIEW_COPY: Record<ShowcaseView, { eyebrow: string; title: string; subtitle: string }> = {
  overview: {
    eyebrow: "SYSTEM OVERVIEW",
    title: "MOSS 金融决策分析平台",
    subtitle: "把分散数据、专业计算和分析解释放进同一条可复核的业务工作链。",
  },
  investment: {
    eyebrow: "INVESTMENT DECISION SUPPORT",
    title: "市场变化如何传导到当前持仓",
    subtitle: "先由规则和金融计算得到可核对的结果，再形成投资复核材料。",
  },
  operations: {
    eyebrow: "BUSINESS & PNL ANALYSIS",
    title: "从分类损益到经营结果",
    subtitle: "统一正式口径、管理口径和归因过程，减少重复拼表与口径争议。",
  },
  agent: {
    eyebrow: "GOVERNED AI ANALYSIS",
    title: "AI 作为受控分析助手",
    subtitle: "模型负责理解问题与组织解释；确定性计算、结果边界和最终判断仍由系统规则与人控制。",
  },
};

const VIEW_CONTEXT: Record<
  ShowcaseView,
  Array<{ label: string; value: string; tone?: Tone }>
> = {
  overview: [
    { label: "展示范围", value: "跨域分析工作链" },
    { label: "数据属性", value: "仿真 · 不连接真实数据", tone: "warning" },
    { label: "能力目录", value: "WORKFLOW-CATALOG-1.0" },
    { label: "结果属性", value: "系统结构说明" },
  ],
  investment: [
    { label: "快照编号", value: "S-2026Q2" },
    { label: "计算口径", value: "同一持仓 · 同一报告日" },
    { label: "风险规则", value: "FI-RISK-2.3" },
    { label: "结果属性", value: "分析情景", tone: "warning" },
  ],
  operations: [
    { label: "快照编号", value: "S-2026Q2" },
    { label: "口径分层", value: "财务口径 / 管理口径" },
    { label: "桥接规则", value: "PNL-BRIDGE-1.8" },
    { label: "核对状态", value: "仿真总额已核平", tone: "positive" },
  ],
  agent: [
    { label: "证据范围", value: "只读查询与受控计算" },
    { label: "工作流目录", value: "CATALOG-1.0" },
    { label: "工具范围", value: "evidence / query / research" },
    { label: "结果属性", value: "非正式分析材料", tone: "warning" },
  ],
};

function ToneTag({ children, tone = "neutral" }: { children: React.ReactNode; tone?: Tone }) {
  return (
    <span className="publication-tone-tag" data-tone={tone}>
      {children}
    </span>
  );
}

function SectionTitle({
  eyebrow,
  title,
  aside,
}: {
  eyebrow: string;
  title: string;
  aside?: React.ReactNode;
}) {
  return (
    <header className="publication-section-title">
      <div>
        <span>{eyebrow}</span>
        <h2>{title}</h2>
      </div>
      {aside ? <div className="publication-section-title__aside">{aside}</div> : null}
    </header>
  );
}

function MetricCard({
  label,
  value,
  unit,
  detail,
  tone = "neutral",
}: {
  label: string;
  value: string;
  unit?: string;
  detail: string;
  tone?: Tone;
}) {
  return (
    <article className="publication-metric" data-tone={tone}>
      <span className="publication-metric__label">{label}</span>
      <strong className="publication-metric__value">
        {value}
        {unit ? <small>{unit}</small> : null}
      </strong>
      <span className="publication-metric__detail">{detail}</span>
    </article>
  );
}

function OverviewView() {
  const flow = [
    {
      index: "01",
      icon: "database" as const,
      title: "数据聚合",
      body: "汇集持仓、市场、损益与资金数据，并保留日期和来源。",
      foot: "先解决分散与重复取数",
    },
    {
      index: "02",
      icon: "settings" as const,
      title: "确定性计算",
      body: "由金融规则计算久期、DV01、损益桥和分类汇总。",
      foot: "不让大模型直接猜数",
    },
    {
      index: "03",
      icon: "file-search" as const,
      title: "规则路由与 AI 解释",
      body: "按问题调用对应工作流，把结果组织成可读的分析材料。",
      foot: "事实、推断和限制分开",
    },
    {
      index: "04",
      icon: "user" as const,
      title: "人工复核与决定",
      body: "授权人员核对证据、约束与场景后，再决定是否采取行动。",
      foot: "系统不代替投资决策",
    },
  ];

  return (
    <div className="publication-view publication-overview" data-testid="publication-overview-view">
      <section className="publication-overview__lead publication-panel">
        <div className="publication-overview__statement">
          <span className="publication-kicker">一句话看懂 MOSS</span>
          <h2>
            持仓、市场、损益和资金数据，已在
            <em>同一工作台</em>
            就绪。
          </h2>
          <p>
            它解决的不是“再做一个聊天框”，而是把原来分散在 Excel、报告和不同系统中的数据，
            先按金融规则算清楚，再变成可追溯、能快速复核的投资与经营分析材料。
          </p>
          <div className="publication-overview__audience">
            <span><strong>使用者</strong> 投资经理 · 金融市场部 · 计划财务</span>
            <span><strong>主要用途</strong> 投资复盘 · 大类资产观察 · 分类损益分析</span>
          </div>
        </div>
        <div className="publication-overview__answer-grid">
          <div>
            <span>当前展示任务</span>
            <strong>市场—持仓—损益联动复盘</strong>
          </div>
          <div>
            <span>输入状态</span>
            <strong>持仓 / 市场 / 损益 / 资金 · 已就绪</strong>
          </div>
          <div>
            <span>输出状态</span>
            <strong>分析材料已生成 · 等待人工复核</strong>
          </div>
        </div>
      </section>

      <section className="publication-panel publication-flow-panel">
        <SectionTitle
          eyebrow="CONTROLLED WORKFLOW"
          title="一条从数据到决策的受控分析链"
          aside={<ToneTag tone="accent">系统计算与模型解释分工</ToneTag>}
        />
        <div className="publication-flow">
          {flow.map((step, index) => (
            <article className="publication-flow__step" key={step.index}>
              <div className="publication-flow__topline">
                <span>{step.index}</span>
                <LightIcon name={step.icon} />
              </div>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
              <small>{step.foot}</small>
              {index < flow.length - 1 ? (
                <LightIcon className="publication-flow__arrow" name="arrow-right" />
              ) : null}
            </article>
          ))}
        </div>
      </section>

      <section className="publication-overview__bottom-grid">
        <article className="publication-panel publication-compact-card">
          <SectionTitle eyebrow="PAIN POINT" title="原来最费时间的地方" />
          <ul className="publication-list">
            <li>数据分散，日期、单位与口径不一致</li>
            <li>复杂计算依赖个人 Excel，慢且难复核</li>
            <li>市场判断与自身持仓、经营结果相互割裂</li>
          </ul>
        </article>
        <article className="publication-panel publication-compact-card">
          <SectionTitle eyebrow="WHAT WAS BUILT" title="系统实际开发的能力" />
          <div className="publication-chip-grid">
            <ToneTag>统一数据入口</ToneTag>
            <ToneTag>金融指标计算</ToneTag>
            <ToneTag>损益与情景分析</ToneTag>
            <ToneTag>业务工作流路由</ToneTag>
            <ToneTag>受控 AI 解释</ToneTag>
            <ToneTag>来源与质量标记</ToneTag>
          </div>
        </article>
        <article className="publication-panel publication-compact-card publication-boundary-card">
          <SectionTitle eyebrow="BOUNDARY" title="系统不替人做什么" />
          <p>
            不自动交易，不把模型文本当正式结果，也不替代授权人员对风险、额度和经营约束的判断。
          </p>
          <ToneTag tone="warning">最终行动由人决定</ToneTag>
        </article>
      </section>
    </div>
  );
}

function InvestmentView() {
  const scenarios = [
    { name: "基准情景", change: "收益率不变", pnl: "+480", tone: "neutral" as Tone, note: "仅计持有收益估算" },
    { name: "利率下行", change: "曲线平行 -10bp", pnl: "+8,760", tone: "positive" as Tone, note: "久期敞口受益" },
    { name: "利率上行", change: "曲线平行 +10bp", pnl: "-7,810", tone: "negative" as Tone, note: "凸性影响已计入" },
    { name: "信用走阔", change: "信用利差 +20bp", pnl: "-3,420", tone: "warning" as Tone, note: "不含流动性折价" },
  ];

  return (
    <div className="publication-view publication-investment" data-testid="publication-investment-view">
      <section className="publication-metric-grid publication-metric-grid--four">
        <MetricCard label="10年国债收益率" value="2.18" unit="%" detail="仿真市场快照 · 较前日 -4bp" tone="positive" />
        <MetricCard label="组合修正久期" value="4.20" unit="年" detail="确定性计算 · 含全部债券持仓" />
        <MetricCard label="组合 DV01" value="820" unit="万元/bp" detail="确定性计算 · 用于利率情景估算" />
        <MetricCard label="Crisis Score" value="67" unit="/100" detail="规则评分 · 压力偏高" tone="warning" />
      </section>

      <section className="publication-investment__main-grid">
        <article className="publication-panel publication-market-map">
          <SectionTitle
            eyebrow="MARKET → POSITION"
            title="市场信号与当前持仓放在同一张图上"
            aside={<ToneTag tone="positive">利率下行 · 组合受益</ToneTag>}
          />
          <div className="publication-market-map__body">
            <div className="publication-curve-card">
              <div className="publication-curve-card__legend">
                <span><i data-line="current" />当前曲线</span>
                <span><i data-line="prior" />上期曲线</span>
              </div>
              <svg aria-label="仿真收益率曲线" role="img" viewBox="0 0 600 190">
                <g className="publication-chart-grid">
                  <line x1="34" x2="576" y1="36" y2="36" />
                  <line x1="34" x2="576" y1="90" y2="90" />
                  <line x1="34" x2="576" y1="144" y2="144" />
                </g>
                <path className="publication-chart-line publication-chart-line--prior" d="M48 132 C130 102 160 112 226 86 S370 66 438 58 S532 54 566 43" />
                <path className="publication-chart-line publication-chart-line--current" d="M48 142 C132 116 166 120 226 98 S370 78 438 73 S530 67 566 57" />
                {[48, 150, 260, 370, 470, 566].map((x) => <circle className="publication-chart-dot" cx={x} cy={x === 48 ? 142 : x === 150 ? 117 : x === 260 ? 92 : x === 370 ? 78 : x === 470 ? 70 : 57} key={x} r="3.5" />)}
                <g className="publication-chart-axis">
                  <text x="43" y="174">1Y</text><text x="143" y="174">3Y</text><text x="252" y="174">5Y</text><text x="360" y="174">7Y</text><text x="458" y="174">10Y</text><text x="550" y="174">30Y</text>
                </g>
              </svg>
            </div>
            <div className="publication-exposure-card">
              <span className="publication-kicker">久期敞口分布</span>
              {[
                ["1年以内", "16%", 16],
                ["1—3年", "22%", 22],
                ["3—5年", "28%", 28],
                ["5—10年", "25%", 25],
                ["10年以上", "9%", 9],
              ].map(([label, value, width]) => (
                <div className="publication-exposure-row" key={String(label)}>
                  <span>{label}</span>
                  <div><i style={{ width: `${Number(width) * 3}%` }} /></div>
                  <strong>{value}</strong>
                </div>
              ))}
              <p>5年以上久期敞口占 34%，需要与利率反转风险一并复核。</p>
            </div>
          </div>
        </article>

        <aside className="publication-panel publication-decision-note">
          <SectionTitle eyebrow="ANALYSIS NOTE" title="系统形成的复核材料" />
          <div className="publication-decision-note__callout">
            <span>当前判断</span>
            <strong>利率下行对组合有利，但中长久期集中度提高了反向波动敏感性。</strong>
          </div>
          <ol>
            <li><span>01</span><div><strong>先核对额度</strong><p>5年以上久期敞口是否接近内部预算。</p></div></li>
            <li><span>02</span><div><strong>再看资金约束</strong><p>负债稳定性是否支持继续承担久期风险。</p></div></li>
            <li><span>03</span><div><strong>最后比较情景</strong><p>把利率反转与信用走阔放在同一口径复核。</p></div></li>
          </ol>
          <div className="publication-decision-note__boundary">
            <LightIcon name="safety-certificate" />
            <span><strong>供授权人员复核</strong>系统未生成交易指令。</span>
          </div>
        </aside>
      </section>

      <section className="publication-panel publication-scenario-panel">
        <SectionTitle
          eyebrow="SCENARIO ANALYSIS"
          title="同一持仓快照下的压力情景"
          aside={<span className="publication-unit">估算损益 · 万元</span>}
        />
        <div className="publication-scenario-table" role="table" aria-label="投资压力情景">
          <div className="publication-table-row publication-table-row--head" role="row">
            <span>情景</span><span>冲击假设</span><span>组合估算损益</span><span>解释</span><span>结果属性</span>
          </div>
          {scenarios.map((row) => (
            <div className="publication-table-row" role="row" key={row.name}>
              <strong>{row.name}</strong><span>{row.change}</span><strong data-tone={row.tone}>{row.pnl}</strong><span>{row.note}</span><ToneTag tone={row.tone}>分析情景</ToneTag>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function OperationsView() {
  const bridge = [
    { label: "持有收益", value: "+8.20", width: 88, tone: "positive" as Tone },
    { label: "骑乘收益", value: "+1.70", width: 38, tone: "positive" as Tone },
    { label: "曲线变动", value: "+2.10", width: 44, tone: "positive" as Tone },
    { label: "信用利差", value: "-0.90", width: 26, tone: "negative" as Tone },
    { label: "交易及其他", value: "+1.30", width: 32, tone: "accent" as Tone },
  ];

  return (
    <div className="publication-view publication-operations" data-testid="publication-operations-view">
      <section className="publication-metric-grid publication-metric-grid--four">
        <MetricCard label="正式分类损益" value="12.40" unit="亿元" detail="财务口径 · 分类合计已核平" />
        <MetricCard label="分类汇总差额" value="0.00" unit="亿元" detail="总额 12.40 = 分类合计 12.40" tone="positive" />
        <MetricCard label="管理口径净收入" value="8.90" unit="亿元" detail="扣除 FTP / 资金及资本占用" />
        <MetricCard label="待解释残差" value="0.00" unit="亿元" detail="桥接项目全部落位" tone="positive" />
      </section>

      <section className="publication-operations__main-grid">
        <article className="publication-panel publication-bridge-card">
          <SectionTitle
            eyebrow="PNL ATTRIBUTION"
            title="12.40 亿元损益从哪里来"
            aside={<ToneTag tone="positive">正式总额已核平</ToneTag>}
          />
          <div className="publication-bridge-card__total">
            <span>本期正式损益</span><strong>12.40<small>亿元</small></strong>
          </div>
          <div className="publication-bridge-bars">
            {bridge.map((item) => (
              <div className="publication-bridge-row" key={item.label}>
                <span>{item.label}</span>
                <div><i data-tone={item.tone} style={{ width: `${item.width}%` }} /></div>
                <strong data-tone={item.tone}>{item.value}</strong>
              </div>
            ))}
          </div>
          <p className="publication-bridge-card__note">
            归因结果用于解释正式总额，不与管理口径直接相加；口径转换单独列示。
          </p>
        </article>

        <article className="publication-panel publication-basis-card">
          <SectionTitle eyebrow="BASIS BRIDGE" title="正式口径怎样转为管理口径" />
          <div className="publication-basis-flow">
            <div><span>正式分类损益</span><strong>12.40</strong><small>财务确认口径</small></div>
            <LightIcon name="arrow-down" />
            <div data-deduction="true"><span>FTP / 资金成本</span><strong>-2.60</strong><small>内部资金转移定价</small></div>
            <div data-deduction="true"><span>资本与预期损失占用</span><strong>-0.90</strong><small>管理分析口径</small></div>
            <LightIcon name="arrow-down" />
            <div data-result="true"><span>管理口径净收入</span><strong>8.90</strong><small>用于经营比较</small></div>
          </div>
        </article>
      </section>

      <section className="publication-panel publication-product-table-card">
        <SectionTitle
          eyebrow="PRODUCT VIEW"
          title="按业务类别定位损益差异"
          aside={<span className="publication-unit">单位：亿元</span>}
        />
        <div className="publication-product-grid" role="table" aria-label="分类损益与管理净收入">
          <div className="publication-product-row publication-product-row--head" role="row">
            <span>业务类别</span><span>正式损益</span><span>FTP / 资金及资本占用</span><span>管理净收入</span><span>经营观察</span>
          </div>
          {[
            ["债券投资", "7.20", "-2.00", "5.20", "收益主体，久期贡献较高"],
            ["基金及资管", "2.10", "-0.70", "1.40", "费后收益保持稳定"],
            ["同业业务", "1.60", "-0.40", "1.20", "资金成本敏感"],
            ["衍生品及对冲", "1.50", "-0.40", "1.10", "主要承担风险对冲"],
          ].map((row) => (
            <div className="publication-product-row" role="row" key={row[0]}>
              <strong>{row[0]}</strong><span>{row[1]}</span><span>{row[2]}</span><strong>{row[3]}</strong><span>{row[4]}</span>
            </div>
          ))}
        </div>
        <div className="publication-product-summary">
          <LightIcon name="bulb" />
          <p><strong>经营支撑：</strong>系统把“赚了多少、由什么业务贡献、扣除资金和资本成本后还剩多少”放在同一口径下，帮助管理层快速定位分类损益差异及其原因。</p>
        </div>
      </section>
    </div>
  );
}

function AgentView() {
  return (
    <div className="publication-view publication-agent" data-testid="publication-agent-view">
      <section className="publication-agent__query publication-panel">
        <span className="publication-agent__avatar"><LightIcon name="user" /></span>
        <div>
          <span>分析问题</span>
          <strong>“结合近期债券市场波动和当前持仓，哪些风险会影响本期投资损益？”</strong>
        </div>
        <ToneTag tone="accent">已识别为复合分析任务</ToneTag>
      </section>

      <section className="publication-agent__route publication-panel">
        <SectionTitle
          eyebrow="RULE-BASED ROUTING"
          title="系统先拆任务，再调用对应数据与计算"
          aside={<span className="publication-unit">不是让模型自由猜测计算路径</span>}
        />
        <div className="publication-agent__route-flow">
          {[
            ["组合复盘", "portfolio_review", "持仓 · 久期 · DV01", "database"],
            ["风险备忘", "risk_memo", "利率 · 信用 · 压力评分", "safety-certificate"],
            ["损益复盘", "pnl_review", "总额 · 桥接 · 分类损益", "bar-chart"],
          ].map(([label, code, detail, icon], index) => (
            <article key={code}>
              <span>{index + 1}</span>
              <LightIcon name={icon as LightIconName} />
              <div><strong>{label}</strong><code>{code}</code><small>{detail}</small></div>
            </article>
          ))}
        </div>
      </section>

      <section className="publication-agent__workspace">
        <article className="publication-panel publication-evidence-stack">
          <SectionTitle eyebrow="CONTROLLED EVIDENCE" title="本次分析实际引用了什么" />
          {[
            ["市场快照", "仿真快照 S-2026Q2", "日期一致", "positive"],
            ["组合持仓", "脱敏组合 P-001", "完整", "positive"],
            ["久期 / DV01", "规则版本 FI-RISK-2.3", "已计算", "accent"],
            ["分类损益桥", "规则版本 PNL-BRIDGE-1.8", "已核平", "positive"],
          ].map(([name, source, status, tone]) => (
            <div className="publication-evidence-row" key={name}>
              <LightIcon name="check-circle" />
              <div><strong>{name}</strong><span>{source}</span></div>
              <ToneTag tone={tone as Tone}>{status}</ToneTag>
            </div>
          ))}
          <div className="publication-evidence-meta">
            <span>数据属性</span><strong>仿真数据</strong>
            <span>来源标记</span><strong>已保留</strong>
            <span>计算主体</span><strong>规则与金融函数</strong>
          </div>
        </article>

        <article className="publication-panel publication-agent-answer">
          <SectionTitle
            eyebrow="STRUCTURED ANALYSIS"
            title="AI 组织后的分析材料"
            aside={<ToneTag tone="warning">非正式结果</ToneTag>}
          />
          <div className="publication-agent-answer__summary">
            <span>结论摘要</span>
            <p>近期利率下行对当前组合估值有利，但组合对中长端利率反转更敏感；信用利差若同步走阔，可能抵消部分利率收益。</p>
          </div>
          <div className="publication-agent-answer__grid">
            <div><span>主要证据</span><ul><li>组合 DV01 为 820 万元/bp</li><li>5年以上久期敞口占 34%</li><li>信用走阔 20bp 情景损益 -3,420 万元</li></ul></div>
            <div><span>限制与冲突</span><ul><li>情景未计入极端流动性折价</li><li>Crisis Score 属规则评分</li><li>市场路径仍存在不确定性</li></ul></div>
          </div>
          <div className="publication-agent-answer__next">
            <LightIcon name="unordered-list" />
            <div><span>建议复核顺序</span><strong>久期额度 → 负债稳定性 → 信用集中度 → 压力情景</strong></div>
          </div>
        </article>

        <aside className="publication-panel publication-governance-card">
          <SectionTitle eyebrow="CONTROL BOUNDARY" title="模型能做与不能做" />
          <div className="publication-governance-card__status">
            <LightIcon name="safety-certificate" />
            <div><span>当前结果属性</span><strong>受控分析材料</strong><small>formal_use_allowed = false</small></div>
          </div>
          <div className="publication-governance-card__list">
            <div data-state="allowed"><span>✓</span><p><strong>可以</strong>理解问题、选择受控工作流、组织解释</p></div>
            <div data-state="limited"><span>—</span><p><strong>受规则约束</strong>金融计算、数据范围、来源和结果标签</p></div>
            <div data-state="blocked"><span>×</span><p><strong>不可以</strong>自动交易、记账或替代业务审批</p></div>
          </div>
          <div className="publication-governance-card__human">
            <span>下一步</span>
            <strong>由授权人员复核后，决定是否采取行动</strong>
            <small>现有用户确认不等同于独立审批签字</small>
          </div>
        </aside>
      </section>
    </div>
  );
}

function resolveView(value: string | null): ShowcaseView {
  return NAV_ITEMS.some((item) => item.key === value) ? (value as ShowcaseView) : "overview";
}

export default function PublicationShowcasePage() {
  const [searchParams] = useSearchParams();
  const currentView = resolveView(searchParams.get("view"));
  const copy = VIEW_COPY[currentView];
  const contextItems = VIEW_CONTEXT[currentView];

  return (
    <div
      className="publication-showcase"
      data-moss-theme-scope="dashboard-home"
      data-testid="publication-showcase-page"
    >
      <aside className="publication-showcase__rail">
        <div className="publication-brand">
          <span className="publication-brand__mark">M</span>
          <div><strong>MOSS</strong><small>金融决策分析平台</small></div>
        </div>
        <div className="publication-rail-intro">
          <span>论文投稿展示</span>
          <p>用四个场景说明系统用途、计算分工与应用边界。</p>
        </div>
        <nav aria-label="投稿展示页面" className="publication-nav">
          {NAV_ITEMS.map((item, index) => (
            <Link
              aria-current={currentView === item.key ? "page" : undefined}
              className="publication-nav__item"
              data-active={currentView === item.key ? "true" : "false"}
              key={item.key}
              to={`/publication-showcase?view=${item.key}`}
            >
              <span className="publication-nav__index">0{index + 1}</span>
              <LightIcon name={item.icon} />
              <span><strong>{item.label}</strong><small>{item.caption}</small></span>
            </Link>
          ))}
        </nav>
        <div className="publication-rail-footer">
          <div><span data-status="online" />展示环境</div>
          <strong>DEV · MOCK ONLY</strong>
          <small>不连接真实业务数据</small>
        </div>
      </aside>

      <main className="publication-showcase__main">
        <header className="publication-showcase__header">
          <div>
            <span className="publication-header__eyebrow">{copy.eyebrow}</span>
            <h1>{copy.title}</h1>
            <p>{copy.subtitle}</p>
          </div>
          <div className="publication-header__meta">
            <ToneTag tone="accent">投稿展示模式</ToneTag>
            <span>仿真快照 S-2026Q2</span>
          </div>
        </header>

        <div className="publication-disclaimer" role="note">
          <LightIcon name="info-circle" />
          <strong>仿真数据</strong>
          <span>仅用于展示系统结构与工作流程</span>
          <i />
          <span>不构成投资、经营或业务审批结论</span>
        </div>

        <section className="publication-context-strip" aria-label="展示口径与证据状态">
          {contextItems.map((item) => (
            <div key={item.label}>
              <span>{item.label}</span>
              <strong data-tone={item.tone ?? "neutral"}>{item.value}</strong>
            </div>
          ))}
        </section>

        {currentView === "overview" ? <OverviewView /> : null}
        {currentView === "investment" ? <InvestmentView /> : null}
        {currentView === "operations" ? <OperationsView /> : null}
        {currentView === "agent" ? <AgentView /> : null}

        <footer className="publication-page-footer">
          <span>MOSS Agent Analytics OS · 固定收益分析与决策支持</span>
          <span>展示数据均为虚构示例，不对应任何机构或账户</span>
        </footer>
      </main>
    </div>
  );
}
