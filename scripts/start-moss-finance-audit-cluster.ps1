param(
  [string]$TeamId = "moss-finance-audit-cluster",
  [string]$OutputRoot = "",
  [ValidateSet("Wsl", "Windows")]
  [string]$Backend = "Wsl",
  [string]$WslDistro = "HermesUbuntu",
  [ValidateSet("Panes", "Windows")]
  [string]$Layout = "Panes",
  [string]$Model = "",
  [string]$Provider = "",
  [string]$Toolsets = "",
  [string]$Skills = "",
  [string]$HermesCommand = "hermes",
  [string]$WslCommand = "wsl.exe",
  [string[]]$Roles = @(),
  [int]$MaxTurns = 120,
  [string]$Task = "用 Hermes 多角色员工集群对 MOSS V3 金融系统进行完整业务审计，优先处理固收口径、外币折人民币、应计利息、久期、凸性、DV01、PnL attribution、数据血缘、页面闭环和 owner 签字证据。",
  [switch]$Launch,
  [switch]$PrepareOnly,
  [switch]$SeedSessions,
  [switch]$Yolo
)

$ErrorActionPreference = "Stop"
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$DefaultFinanceAuditRoles = @(
  "lead",
  "product-manager",
  "metric-caliber-officer",
  "data-lineage-auditor",
  "fixed-income-analyst",
  "asset-liability-manager",
  "valuation-accounting-reconciler",
  "pnl-attribution-analyst",
  "risk-manager",
  "market-data-specialist",
  "backend-api-contract-engineer",
  "developer",
  "frontend-developer",
  "ui-ux-page-closer",
  "security-permission-auditor",
  "code-reviewer",
  "qa",
  "docs-delivery-manager"
)

$RoleTitles = @{
  "lead" = "总控负责人 Leader"
  "product-manager" = "业务产品经理"
  "metric-caliber-officer" = "指标口径官"
  "data-lineage-auditor" = "数据血缘审计员"
  "fixed-income-analyst" = "固收分析师"
  "valuation-accounting-reconciler" = "估值会计核对员"
  "pnl-attribution-analyst" = "PnL 归因分析师"
  "risk-manager" = "风险经理"
  "market-data-specialist" = "市场数据专家"
  "backend-api-contract-engineer" = "后端 API 契约工程师"
  "frontend-developer" = "前端开发师"
  "ui-ux-page-closer" = "页面收口师"
  "security-permission-auditor" = "安全权限审计员"
  "code-reviewer" = "代码审查员"
  "qa" = "测试/QA"
  "docs-delivery-manager" = "文档交付官"
  "developer" = "实现工程师"
  "asset-liability-manager" = "资产负债管理师"
}

function Write-Utf8File {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [Parameter(Mandatory = $true)]
    [string]$Value
  )

  Set-Content -LiteralPath $Path -Value $Value -Encoding UTF8
}

function Get-SafeTeamId {
  param([string]$RawTeamId)

  if ([string]::IsNullOrWhiteSpace($RawTeamId)) {
    return "moss-finance-audit-cluster"
  }

  $safe = $RawTeamId.Trim() -replace "[^A-Za-z0-9_.-]", "-"
  $safe = $safe.Trim("-")
  if ([string]::IsNullOrWhiteSpace($safe)) {
    return "moss-finance-audit-cluster"
  }
  return $safe
}

function Resolve-RoleList {
  param([string[]]$RequestedRoles)

  $resolved = New-Object System.Collections.Generic.List[string]
  if (-not $RequestedRoles -or $RequestedRoles.Count -eq 0) {
    return @($DefaultFinanceAuditRoles)
  }

  foreach ($item in $RequestedRoles) {
    foreach ($part in ($item -split ",")) {
      $slug = $part.Trim()
      if ([string]::IsNullOrWhiteSpace($slug)) {
        continue
      }
      if ($slug -eq "all") {
        return @($DefaultFinanceAuditRoles)
      }
      if (-not $resolved.Contains($slug)) {
        $resolved.Add($slug) | Out-Null
      }
    }
  }

  if ($resolved.Count -eq 0) {
    return @($DefaultFinanceAuditRoles)
  }
  return @($resolved)
}

function Get-RoleTitle {
  param([string]$Role)

  if ($RoleTitles.ContainsKey($Role)) {
    return $RoleTitles[$Role]
  }
  return $Role
}

function Get-InitialTaskForRole {
  param([string]$Role)

  switch ($Role) {
    "lead" {
      return "维护总控：把所有角色 outbox 合成 P0/P1/P2 清单，先收固收口径证据，再决定是否进入修复。禁止无证据扩大战线。"
    }
    "product-manager" {
      return "整理 owner 需要签字的业务问题：market_value clean/dirty、应计利息进入 dirty/carry/action attribution、day-count、YTM/久期/凸性复利规则、DV01 CNY/1bp 正式口径。"
    }
    "metric-caliber-officer" {
      return "核定指标口径：逐项比对 docs/page_contracts.md、docs/metric_dictionary.md、docs/calc_rules.md、golden sample 与本地证据。没有 owner 签字的指标标记 definition pending。"
    }
    "data-lineage-auditor" {
      return "核实外币债券是否已经折人民币：追 report_date、source_version、FX 规则、DuckDB 表字段、fallback/stale 状态。MCP 不可用时记录使用的本地 schema、文档、测试和 DuckDB 证据。"
    }
    "fixed-income-analyst" {
      return "优先审计固收 P0：债券币种、clean/dirty market_value、应计利息、久期、凸性、YTM 复利、DV01 CNY/1bp、曲线/利差口径。输出可签字问题单。"
    }
    "asset-liability-manager" {
      return "核对资产负债视角：债券资产、负债、现金流、净敞口、币种折算、报告日口径和页面主结论是否能支持 ALM 决策。"
    }
    "valuation-accounting-reconciler" {
      return "核对估值与会计：market_value、carry、dirty value、accrued_interest、514/516/517 科目、符号、单位和正式 PnL 来源是否一致。"
    }
    "pnl-attribution-analyst" {
      return "核对 PnL attribution：应计利息、carry、action attribution、curve/spread/FX/residual 是否重复、遗漏或符号反向。"
    }
    "risk-manager" {
      return "核对风险口径：DV01/KRD/久期/凸性/CS01 的单位、币种、方向、分母、排除项和披露是否支持正式业务结论。"
    }
    "market-data-specialist" {
      return "核对市场数据：收益率曲线、FX、价格、估值源、source_version、as_of_date、fallback/stale、日终/月末口径。"
    }
    "backend-api-contract-engineer" {
      return "核对后端契约：bond analytics/PnL/risk API 的 result_meta、单位、日期、source_lineage、definition pending 字段能否支撑前端闭环。"
    }
    "developer" {
      return "等待审计结论后接修复 lane：只做有证据的最小修复，优先补 targeted tests，不做无关重构。"
    }
    "frontend-developer" {
      return "追前端链路：API response -> adapter/transformer -> state/selector -> component -> chart/table，确认单位、精度、null/0、币种、日期没有被前端二次算错。"
    }
    "ui-ux-page-closer" {
      return "核对页面闭环：首屏必须暴露主结论、无数据、stale、fallback date、加载失败、definition pending、owner 签字缺口。"
    }
    "security-permission-auditor" {
      return "核对权限边界：只读审计、写入脚本、刷新任务、导出和 owner 证据生成不能绕过权限或留下不可追踪操作。"
    }
    "code-reviewer" {
      return "独立审查后续修复 diff：发现优先，按文件/行号报告 P0/P1/P2、回归风险、缺失测试和范围蔓延。"
    }
    "qa" {
      return "建立验证矩阵：固收核心测试、API 契约测试、前端 targeted tests、debt:audit、必要浏览器验证。失败要保留证据并回派。"
    }
    "docs-delivery-manager" {
      return "汇总交付物：owner 签字包、审计证据包、剩余 blocker、验证命令、未验证风险，保证可追溯。"
    }
    default {
      return "等待 Leader 分配具体审计或修复任务。接到任务后只处理自己的 lane，输出证据、验证和 blocker。"
    }
  }
}

function New-ClusterBoard {
  param(
    [string]$ResolvedTeamId,
    [string]$TeamDir,
    [string[]]$ResolvedRoles,
    [string]$BackendName,
    [string]$TaskText
  )

  $createdAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  $roleRows = ($ResolvedRoles | ForEach-Object {
    $title = Get-RoleTitle -Role $_
    "| $title | $_ | inbox/$_.md | outbox/$_.md | 待执行 | |"
  }) -join [Environment]::NewLine

  return @"
# MOSS V3 金融系统审计员工集群

Team: $ResolvedTeamId
Created: $createdAt
Workspace: $root
Team directory: $TeamDir
Backend: $BackendName

## 总目标

$TaskText

## 当前 P0

1. 固收口径优先：债券里的币种、应计利息、久期、凸性、YTM、DV01、clean/dirty market_value 任一口径错，金融结果就会错。
2. 外币债券是否已折人民币必须用证据核实，不能靠字段名猜。
3. market_value 是 clean 还是 dirty、应计利息是否进入 dirty/carry/action attribution、day-count 与复利规则、DV01 CNY/1bp 正式口径都需要业务 owner 签字。
4. MCP 证据工具不可用时，必须写明使用了哪些本地 schema、文档、测试和 DuckDB 实库证据，并标残余风险。

## 员工分工

| 员工 | 角色 slug | 任务箱 | 汇报箱 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- |
$roleRows

## 派发规则

派任务时只派给一个主责员工，必要时抄送相关员工。每个任务都要包含：

- 背景：页面、接口、表、指标或 owner 问题。
- 范围：允许看的文件/表/接口，明确不要碰的区域。
- 必交：结论、证据、P0/P1/P2、涉及文件/表/接口、验证命令、阻塞/需 owner 签字。
- 停止线：没有证据就报告 pending，不猜正式口径。

## 固收 P0 首轮任务

- Fixed Income Analyst：论证 clean/dirty、应计利息、久期、凸性、YTM、DV01 口径。
- Data Lineage Auditor：核实外币债券是否已经按 FX 规则折成人民币，并追 source_version/report_date。
- Metric Caliber Officer：把每个指标对齐文档、contract、golden sample 和 owner 签字状态。
- Valuation Accounting Reconciler：核对估值、会计、carry、dirty value、accrued_interest 是否一致。
- PnL Attribution Analyst：核对应计利息是否重复进入 carry/action attribution/PnL bridge。
- Risk Manager：核对 DV01/KRD/久期/凸性单位、方向和 CNY/1bp 披露。

## 标准汇报格式

### 结论
一句话说清楚：通过、发现问题、或证据不足。

### 证据
列本地文件、表、测试、DuckDB 查询、MCP 可用/不可用状态。

### 问题级别
P0/P1/P2，并说明为什么。

### 涉及对象
文件、接口、表、字段、页面、指标。

### 验证
实际跑过的命令或无法运行的原因。

### 阻塞
需要 owner 签字、缺 MCP、缺样本、缺权限、缺数据。

## 决策记录

- Pending.

## 最终综合

- Pending.
"@
}

function Set-ClusterInboxes {
  param(
    [string]$TeamDir,
    [string[]]$ResolvedRoles,
    [string]$TaskText
  )

  $inboxDir = Join-Path $TeamDir "inbox"
  $outboxDir = Join-Path $TeamDir "outbox"
  foreach ($role in $ResolvedRoles) {
    $title = Get-RoleTitle -Role $role
    $task = Get-InitialTaskForRole -Role $role
    $inbox = @"
# Inbox - $title

## 初始任务

$task

## 总任务

$TaskText

## 必须遵守

- 先读 AGENTS.md、docs/agent_codebase_map.md 和相关子目录说明。
- 不猜指标口径；缺 owner 签字就标 definition pending。
- 审计优先本地证据：schema、docs、tests、DuckDB、已有审计包；MCP 不可用要写清楚。
- 不做无关重构，不碰数据库 schema、权限框架、调度、全局 SDK 包装层。
- 汇报写到 outbox/$role.md。
"@
    Write-Utf8File -Path (Join-Path $inboxDir "$role.md") -Value $inbox

    $outbox = @"
# Outbox - $title

## 结论

Pending.

## 证据

Pending.

## 问题级别

Pending.

## 涉及文件/表/接口

Pending.

## 验证命令

Pending.

## 阻塞/需 owner 签字

Pending.

## 给 Leader 的下一步建议

Pending.
"@
    Write-Utf8File -Path (Join-Path $outboxDir "$role.md") -Value $outbox
  }
}

function Update-ClusterManifest {
  param(
    [string]$TeamDir,
    [string[]]$ResolvedRoles
  )

  $manifestPath = Join-Path $TeamDir "manifest.json"
  if (-not (Test-Path -LiteralPath $manifestPath)) {
    return
  }

  $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
  $manifest | Add-Member -NotePropertyName "cluster_profile" -NotePropertyValue "moss_finance_audit" -Force
  $manifest | Add-Member -NotePropertyName "audit_focus" -NotePropertyValue @(
    "fixed_income_p0",
    "fx_to_cny_evidence",
    "clean_dirty_market_value",
    "accrued_interest_attribution",
    "duration_convexity_ytm",
    "dv01_cny_per_bp",
    "owner_signoff"
  ) -Force
  $manifest | Add-Member -NotePropertyName "dispatch_manual" -NotePropertyValue (Join-Path $root "docs\hermes-finance-audit-cluster.md") -Force
  $manifest.selected_roles = @($ResolvedRoles)
  Write-Utf8File -Path $manifestPath -Value ($manifest | ConvertTo-Json -Depth 10)
}

function Start-ClusterWindows {
  param(
    [string]$TeamDir,
    [string[]]$ResolvedRoles,
    [string]$WindowLayout
  )

  $wt = Get-Command wt -ErrorAction SilentlyContinue
  if (-not $wt) {
    throw "Windows Terminal (wt.exe) was not found. Run individual launch scripts under $TeamDir\launch."
  }

  if ($ResolvedRoles.Count -eq 0) {
    throw "No roles selected to launch."
  }

  if ($WindowLayout -eq "Windows") {
    foreach ($role in $ResolvedRoles) {
      $launcherPath = Join-Path $TeamDir "launch\$role.ps1"
      Start-Process -FilePath $wt.Source -ArgumentList @(
        "new-tab",
        "--title",
        "MOSS $role",
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $launcherPath
      )
    }
    return
  }

  $firstRole = $ResolvedRoles[0]
  $args = @(
    "new-tab",
    "--title",
    "MOSS $firstRole",
    "powershell",
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    (Join-Path $TeamDir "launch\$firstRole.ps1")
  )

  foreach ($role in ($ResolvedRoles | Where-Object { $_ -ne $firstRole })) {
    $args += @(
      ";",
      "split-pane",
      "--title",
      "MOSS $role",
      "powershell",
      "-NoProfile",
      "-ExecutionPolicy",
      "Bypass",
      "-File",
      (Join-Path $TeamDir "launch\$role.ps1")
    )
  }

  Start-Process -FilePath $wt.Source -ArgumentList $args
}

$resolvedRoles = @(Resolve-RoleList -RequestedRoles $Roles)
$resolvedTeamId = Get-SafeTeamId -RawTeamId $TeamId
$resolvedOutputRoot = if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
  Join-Path $root ".omx\hermes-teams"
} else {
  $OutputRoot
}
$teamDir = Join-Path $resolvedOutputRoot $resolvedTeamId
$baseScript = Join-Path $root "scripts\start-hermes-agent-team.ps1"

if (-not (Test-Path -LiteralPath $baseScript)) {
  throw "Base Hermes team launcher not found: $baseScript"
}

$baseArgs = @(
  "-NoProfile",
  "-ExecutionPolicy",
  "Bypass",
  "-File",
  $baseScript,
  "-Task",
  $Task,
  "-TeamId",
  $resolvedTeamId,
  "-Backend",
  $Backend,
  "-WslDistro",
  $WslDistro,
  "-Layout",
  $Layout,
  "-Roles",
  ($resolvedRoles -join ",")
)
$baseArgs += @("-MaxTurns", [string]$MaxTurns, "-PrepareOnly")

if (-not [string]::IsNullOrWhiteSpace($OutputRoot)) {
  $baseArgs += @("-OutputRoot", $OutputRoot)
}
if (-not [string]::IsNullOrWhiteSpace($Model)) {
  $baseArgs += @("-Model", $Model)
}
if (-not [string]::IsNullOrWhiteSpace($Provider)) {
  $baseArgs += @("-Provider", $Provider)
}
if (-not [string]::IsNullOrWhiteSpace($Toolsets)) {
  $baseArgs += @("-Toolsets", $Toolsets)
}
if (-not [string]::IsNullOrWhiteSpace($Skills)) {
  $baseArgs += @("-Skills", $Skills)
}
if (-not [string]::IsNullOrWhiteSpace($HermesCommand)) {
  $baseArgs += @("-HermesCommand", $HermesCommand)
}
if (-not [string]::IsNullOrWhiteSpace($WslCommand)) {
  $baseArgs += @("-WslCommand", $WslCommand)
}
if ($SeedSessions) {
  $baseArgs += "-SeedSessions"
}
if ($Yolo) {
  $baseArgs += "-Yolo"
}

& powershell @baseArgs
if ($LASTEXITCODE -ne 0) {
  throw "Base Hermes team preparation failed with exit code $LASTEXITCODE."
}

if (-not (Test-Path -LiteralPath $teamDir)) {
  throw "Hermes team directory was not generated: $teamDir"
}

$board = New-ClusterBoard `
  -ResolvedTeamId $resolvedTeamId `
  -TeamDir $teamDir `
  -ResolvedRoles $resolvedRoles `
  -BackendName $Backend `
  -TaskText $Task
Write-Utf8File -Path (Join-Path $teamDir "TEAM_BOARD.md") -Value $board
Set-ClusterInboxes -TeamDir $teamDir -ResolvedRoles $resolvedRoles -TaskText $Task
Update-ClusterManifest -TeamDir $teamDir -ResolvedRoles $resolvedRoles

Write-Host "MOSS finance audit Hermes cluster prepared: $teamDir" -ForegroundColor Cyan
Write-Host "看板: $(Join-Path $teamDir 'TEAM_BOARD.md')" -ForegroundColor DarkGray
Write-Host "控制台: $(Join-Path $teamDir 'dashboard.html')" -ForegroundColor DarkGray
Write-Host "派发服务: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-hermes-team-dispatch.ps1 -TeamId $resolvedTeamId" -ForegroundColor DarkGray

if ($Launch) {
  Start-ClusterWindows -TeamDir $teamDir -ResolvedRoles $resolvedRoles -WindowLayout $Layout
  Write-Host "Hermes finance audit cluster windows launched." -ForegroundColor Cyan
} elseif ($PrepareOnly -or -not $Launch) {
  Write-Host "已生成集群。需要开员工窗口时，加 -Launch；需要先种会话时，加 -SeedSessions。" -ForegroundColor Yellow
}
