param(
  [string]$Task = "Build the MOSS agent system",
  [string]$TeamId = "",
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
  [string[]]$Roles = @("all"),
  [int]$MaxTurns = 90,
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

function Get-SafeTeamId {
  param([string]$RawTeamId)

  if ([string]::IsNullOrWhiteSpace($RawTeamId)) {
    return "moss-hermes-team-" + (Get-Date -Format "yyyyMMdd-HHmmss")
  }

  $safe = $RawTeamId.Trim() -replace "[^A-Za-z0-9_.-]", "-"
  $safe = $safe.Trim("-")
  if ([string]::IsNullOrWhiteSpace($safe)) {
    return "moss-hermes-team-" + (Get-Date -Format "yyyyMMdd-HHmmss")
  }
  return $safe
}

function Quote-Argument {
  param([string]$Value)

  return '"' + ($Value -replace '"', '\"') + '"'
}

function Quote-PowerShellLiteral {
  param([string]$Value)

  return "'" + ($Value -replace "'", "''") + "'"
}

function Format-PowerShellArrayLiteral {
  param([string[]]$Parts)

  if (-not $Parts -or $Parts.Count -eq 0) {
    return "@()"
  }

  return "@(" + (($Parts | ForEach-Object { Quote-PowerShellLiteral $_ }) -join ", ") + ")"
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

function New-DispatchToken {
  $bytes = New-Object byte[] 32
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try {
    $rng.GetBytes($bytes)
  } finally {
    $rng.Dispose()
  }
  return [Convert]::ToBase64String($bytes).TrimEnd("=") -replace "\+", "-" -replace "/", "_"
}

function Invoke-NativeCommand {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Command,
    [string[]]$Arguments = @()
  )

  $previousErrorActionPreference = $ErrorActionPreference
  try {
    $script:LASTEXITCODE = 0
    $ErrorActionPreference = "Continue"
    return & $Command @Arguments 2>&1
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }
}

function ConvertTo-WslPath {
  param([string]$Path)

  $resolved = [System.IO.Path]::GetFullPath($Path)
  if ($resolved -notmatch "^[A-Za-z]:\\") {
    throw "Only absolute Windows drive paths can be converted to WSL paths: $Path"
  }

  $drive = $resolved.Substring(0, 1).ToLowerInvariant()
  $rest = $resolved.Substring(3).Replace("\", "/")
  return "/mnt/$drive/$rest"
}

function Quote-BashLiteral {
  param([string]$Value)

  return "'" + ($Value -replace "'", "'\''") + "'"
}

function ConvertFrom-UnicodeEscape {
  param([string]$Value)

  return [System.Text.RegularExpressions.Regex]::Unescape($Value)
}

function New-Role {
  param(
    [string]$Slug,
    [string]$Title,
    [string]$DisplayTitle,
    [string]$Mission,
    [string]$Boundaries
  )

  return [pscustomobject]@{
    Slug = $Slug
    Title = $Title
    DisplayTitle = if ([string]::IsNullOrWhiteSpace($DisplayTitle)) { $Title } else { $DisplayTitle }
    Mission = $Mission
    Boundaries = $Boundaries
  }
}

function Get-HermesCommonArgs {
  $parts = @()

  if (-not [string]::IsNullOrWhiteSpace($Model)) {
    $parts += @("-m", $Model)
  }
  if (-not [string]::IsNullOrWhiteSpace($Provider)) {
    $parts += @("--provider", $Provider)
  }
  if (-not [string]::IsNullOrWhiteSpace($Toolsets)) {
    $parts += @("-t", $Toolsets)
  }
  if (-not [string]::IsNullOrWhiteSpace($Skills)) {
    $parts += @("-s", $Skills)
  }
  if ($MaxTurns -gt 0) {
    $parts += @("--max-turns", [string]$MaxTurns)
  }
  if ($Yolo) {
    $parts += "--yolo"
  }

  return $parts
}

function Get-HermesCommandParts {
  param(
    [string]$PromptPath,
    [string]$SessionTitle,
    [switch]$Seed,
    [switch]$Continue
  )

  $parts = @($HermesCommand, "chat")

  if ($Continue) {
    $parts += @("--continue", $SessionTitle)
  } elseif ($Seed) {
    $prompt = Get-Content -LiteralPath $PromptPath -Raw -Encoding UTF8
    $parts += @("-q", $prompt)
  }

  $parts += Get-HermesCommonArgs

  return $parts
}

function Join-CommandLine {
  param([string[]]$Parts)

  return ($Parts | ForEach-Object { Quote-Argument $_ }) -join " "
}

function Invoke-RoleSeed {
  param(
    [string]$PromptPath,
    [string]$SessionTitle,
    [string]$PromptPathForBackend
  )

  if ($Backend -eq "Wsl") {
    $wslRoot = ConvertTo-WslPath -Path $root
    $hermesForBash = Quote-BashLiteral $HermesCommand
    $seedPrompt = "Read and follow the Hermes role prompt at $PromptPathForBackend. Initialize this role for session '$SessionTitle'. Write no code during initialization. Reply with ROLE_INITIALIZED and your role name."
    $arguments = @("-d", $WslDistro, "-e", "bash", "-lc", "cd $(Quote-BashLiteral $wslRoot); $hermesForBash chat -q $(Quote-BashLiteral $seedPrompt) -Q --max-turns $MaxTurns")
    $output = Invoke-NativeCommand -Command $WslCommand -Arguments $arguments
  } else {
    $parts = Get-HermesCommandParts -PromptPath $PromptPath -SessionTitle $SessionTitle -Seed
    $parts += "-Q"
    $command = $parts[0]
    $arguments = $parts | Select-Object -Skip 1
    $output = Invoke-NativeCommand -Command $command -Arguments $arguments
  }
  if ($LASTEXITCODE -ne 0) {
    throw "Hermes seed failed for $SessionTitle.`n$output"
  }

  $sessionText = ($output | Out-String)
  if ($sessionText -match "session_id:\s*(20\d{6}_\d{6}_[0-9a-f]+)") {
    $sessionId = $Matches[1]
    if ($Backend -eq "Wsl") {
      $renameCommand = "$(Quote-BashLiteral $HermesCommand) sessions rename $sessionId $(Quote-BashLiteral $SessionTitle)"
      Invoke-NativeCommand -Command $WslCommand -Arguments @("-d", $WslDistro, "-e", "bash", "-lc", $renameCommand) | Out-Null
    } else {
      Invoke-NativeCommand -Command $HermesCommand -Arguments @("sessions", "rename", $sessionId, $SessionTitle) | Out-Null
    }
    return $sessionId
  }

  return ""
}

function New-RoleRunnerScript {
  return @'
param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("Wsl", "Windows")]
  [string]$Backend,
  [Parameter(Mandatory = $true)]
  [string]$WslDistro,
  [Parameter(Mandatory = $true)]
  [string]$Workspace,
  [Parameter(Mandatory = $true)]
  [string]$BackendWorkspace,
  [Parameter(Mandatory = $true)]
  [string]$RoleTitle,
  [Parameter(Mandatory = $true)]
  [string]$PromptPath,
  [Parameter(Mandatory = $true)]
  [string]$BackendPromptPath,
  [Parameter(Mandatory = $true)]
  [string]$SessionFile,
  [Parameter(Mandatory = $true)]
  [string]$SessionTitle,
  [int]$MaxTurns = 90,
  [string]$Model = "",
  [string]$Provider = "",
  [string]$Toolsets = "",
  [string]$Skills = "",
  [string]$HermesCommand = "hermes",
  [string]$WslCommand = "wsl.exe",
  [string]$AutoTaskId = "",
  [string]$TaskClaimToken = "",
  [string]$DispatchUrl = "",
  [string]$DispatchToken = "",
  [switch]$Yolo
)

$ErrorActionPreference = "Stop"
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

function Quote-BashLiteral {
  param([string]$Value)
  return "'" + ($Value -replace "'", "'\''") + "'"
}

function Get-CommonHermesArgs {
  $args = @()
  if (-not [string]::IsNullOrWhiteSpace($Model)) { $args += @("-m", $Model) }
  if (-not [string]::IsNullOrWhiteSpace($Provider)) { $args += @("--provider", $Provider) }
  if (-not [string]::IsNullOrWhiteSpace($Toolsets)) { $args += @("-t", $Toolsets) }
  if (-not [string]::IsNullOrWhiteSpace($Skills)) { $args += @("-s", $Skills) }
  if ($MaxTurns -gt 0) { $args += @("--max-turns", [string]$MaxTurns) }
  if ($Yolo) { $args += "--yolo" }
  return $args
}

function Invoke-NativeCommand {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Command,
    [string[]]$Arguments = @()
  )

  $previousErrorActionPreference = $ErrorActionPreference
  try {
    $script:LASTEXITCODE = 0
    $ErrorActionPreference = "Continue"
    return & $Command @Arguments 2>&1
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }
}

function Invoke-WslHermes {
  param([string]$BashCommand)
  Invoke-NativeCommand -Command $WslCommand -Arguments @("-d", $WslDistro, "-e", "bash", "-lc", $BashCommand)
}

function Invoke-TaskApi {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Endpoint,
    [Parameter(Mandatory = $true)]
    [hashtable]$Payload
  )

  if ([string]::IsNullOrWhiteSpace($DispatchUrl) -or [string]::IsNullOrWhiteSpace($AutoTaskId)) {
    return
  }

  try {
    $uri = $DispatchUrl.TrimEnd("/") + $Endpoint
    $body = $Payload | ConvertTo-Json -Compress
    $headers = @{}
    if (-not [string]::IsNullOrWhiteSpace($DispatchToken)) {
      $headers["X-Hermes-Dispatch-Token"] = $DispatchToken
    }
    Invoke-RestMethod -Uri $uri -Method Post -ContentType "application/json" -Headers $headers -Body $body | Out-Null
  } catch {
    Write-Host "Task status callback failed: $($_.Exception.Message)" -ForegroundColor Yellow
  }
}

Set-Location $Workspace
Write-Host "Hermes role: $RoleTitle" -ForegroundColor Cyan
Write-Host "Prompt file: $PromptPath" -ForegroundColor DarkGray
if ($Backend -eq "Wsl") {
  Write-Host "WSL prompt file: $BackendPromptPath" -ForegroundColor DarkGray
}
Write-Host "First launch initializes this role, then resumes the role session." -ForegroundColor Yellow
Write-Host ""
Write-Host "hermes chat session: $SessionTitle" -ForegroundColor DarkGray

$sessionId = ""
$commonArgs = Get-CommonHermesArgs

if (-not (Test-Path -LiteralPath $SessionFile)) {
  Write-Host "Initializing role session..." -ForegroundColor DarkGray
  if ($Backend -eq "Wsl") {
    $seedPrompt = "Read and follow the Hermes role prompt at $BackendPromptPath. Initialize this role for session '$SessionTitle'. Write no code during initialization. Reply with ROLE_INITIALIZED and your role name."
    $seedCommand = "cd $(Quote-BashLiteral $BackendWorkspace); $(Quote-BashLiteral $HermesCommand) chat -q $(Quote-BashLiteral $seedPrompt) -Q --max-turns $MaxTurns"
    $seedOutput = Invoke-WslHermes -BashCommand $seedCommand 2>&1
  } else {
    $seedPrompt = Get-Content -LiteralPath $PromptPath -Raw -Encoding UTF8
    $seedOutput = Invoke-NativeCommand -Command $HermesCommand -Arguments (@("chat", "-q", $seedPrompt, "-Q") + $commonArgs)
  }
  if ($LASTEXITCODE -ne 0) {
    throw "Hermes role initialization failed.`n$seedOutput"
  }
  $seedText = ($seedOutput | Out-String)
  if ($seedText -match "session_id:\s*(20\d{6}_\d{6}_[0-9a-f]+)") {
    $sessionId = $Matches[1]
    if ($Backend -eq "Wsl") {
      Invoke-WslHermes -BashCommand "$(Quote-BashLiteral $HermesCommand) sessions rename $sessionId $(Quote-BashLiteral $SessionTitle)" | Out-Null
    } else {
      Invoke-NativeCommand -Command $HermesCommand -Arguments @("sessions", "rename", $sessionId, $SessionTitle) | Out-Null
    }
    Set-Content -LiteralPath $SessionFile -Value $sessionId -Encoding UTF8
  } else {
    Write-Host "Could not capture session id. Starting a fresh interactive session." -ForegroundColor Yellow
  }
}

if ([string]::IsNullOrWhiteSpace($sessionId) -and (Test-Path -LiteralPath $SessionFile)) {
  $sessionId = (Get-Content -LiteralPath $SessionFile -Raw -Encoding UTF8).Trim()
}

if ($Backend -eq "Wsl") {
  if (-not [string]::IsNullOrWhiteSpace($AutoTaskId)) {
    $autoPrompt = "You have a newly assigned task in your Hermes team inbox. Task id: $AutoTaskId. Read your role prompt at $BackendPromptPath, then read TEAM_BOARD.md and your inbox. Complete only the assigned task, update your outbox with findings, verification evidence, and blockers, then stop."
    Invoke-TaskApi -Endpoint "/api/task/heartbeat" -Payload @{ task_id = $AutoTaskId; claim_token = $TaskClaimToken }
    if ([string]::IsNullOrWhiteSpace($sessionId)) {
      Invoke-WslHermes -BashCommand "cd $(Quote-BashLiteral $BackendWorkspace); $(Quote-BashLiteral $HermesCommand) chat -q $(Quote-BashLiteral $autoPrompt) --max-turns $MaxTurns"
    } else {
      Invoke-WslHermes -BashCommand "cd $(Quote-BashLiteral $BackendWorkspace); $(Quote-BashLiteral $HermesCommand) chat --resume $sessionId -q $(Quote-BashLiteral $autoPrompt) --max-turns $MaxTurns"
    }
    $taskExitCode = $LASTEXITCODE
    if ($taskExitCode -eq 0) {
      Invoke-TaskApi -Endpoint "/api/task/complete" -Payload @{ task_id = $AutoTaskId; claim_token = $TaskClaimToken; exit_code = $taskExitCode }
    } else {
      Invoke-TaskApi -Endpoint "/api/task/complete" -Payload @{ task_id = $AutoTaskId; claim_token = $TaskClaimToken; exit_code = $taskExitCode; message = "Hermes exited with code $taskExitCode" }
    }
    exit $taskExitCode
  }

  if ([string]::IsNullOrWhiteSpace($sessionId)) {
    Invoke-WslHermes -BashCommand "cd $(Quote-BashLiteral $BackendWorkspace); $(Quote-BashLiteral $HermesCommand) chat --max-turns $MaxTurns"
  } else {
    Invoke-WslHermes -BashCommand "cd $(Quote-BashLiteral $BackendWorkspace); $(Quote-BashLiteral $HermesCommand) chat --resume $sessionId --max-turns $MaxTurns"
  }
} else {
  $hermesArgs = @("chat")
  if (-not [string]::IsNullOrWhiteSpace($sessionId)) {
    $hermesArgs += @("--resume", $sessionId)
  }
  if (-not [string]::IsNullOrWhiteSpace($AutoTaskId)) {
    $autoPrompt = "You have a newly assigned task in your Hermes team inbox. Task id: $AutoTaskId. Read your role prompt at $PromptPath, then read TEAM_BOARD.md and your inbox. Complete only the assigned task, update your outbox with findings, verification evidence, and blockers, then stop."
    $hermesArgs += @("-q", $autoPrompt)
    Invoke-TaskApi -Endpoint "/api/task/heartbeat" -Payload @{ task_id = $AutoTaskId; claim_token = $TaskClaimToken }
  }
  $hermesArgs += $commonArgs
  Invoke-NativeCommand -Command $HermesCommand -Arguments $hermesArgs | Write-Output
  $taskExitCode = $LASTEXITCODE
  if (-not [string]::IsNullOrWhiteSpace($AutoTaskId)) {
    if ($taskExitCode -eq 0) {
      Invoke-TaskApi -Endpoint "/api/task/complete" -Payload @{ task_id = $AutoTaskId; claim_token = $TaskClaimToken; exit_code = $taskExitCode }
    } else {
      Invoke-TaskApi -Endpoint "/api/task/complete" -Payload @{ task_id = $AutoTaskId; claim_token = $TaskClaimToken; exit_code = $taskExitCode; message = "Hermes exited with code $taskExitCode" }
    }
    exit $taskExitCode
  }
}
'@
}

function Select-Roles {
  param(
    [object[]]$AllRoles,
    [string[]]$RequestedRoles
  )

  if (-not $RequestedRoles -or $RequestedRoles.Count -eq 0) {
    return @($AllRoles)
  }

  $requested = @{}
  foreach ($item in $RequestedRoles) {
    foreach ($part in ($item -split ",")) {
      $slug = $part.Trim()
      if (-not [string]::IsNullOrWhiteSpace($slug)) {
        $requested[$slug] = $true
      }
    }
  }

  if ($requested.Count -eq 0 -or $requested.ContainsKey("all")) {
    return @($AllRoles)
  }

  $known = @{}
  foreach ($role in $AllRoles) {
    $known[$role.Slug] = $true
  }
  $unknown = @($requested.Keys | Where-Object { -not $known.ContainsKey($_) })
  if ($unknown.Count -gt 0) {
    throw "Unknown Hermes role(s): $($unknown -join ', '). Valid roles: all, lead, product-manager, frontend-developer, developer, backend-api-contract-engineer, metric-caliber-officer, data-lineage-auditor, security-permission-auditor, asset-liability-manager, pnl-attribution-analyst, risk-manager, fixed-income-analyst, market-data-specialist, valuation-accounting-reconciler, ui-ux-page-closer, docs-delivery-manager, code-reviewer, qa"
  }

  return @($AllRoles | Where-Object { $requested.ContainsKey($_.Slug) })
}

function Get-RolePlaybook {
  param([string]$Slug)

  $playbooks = @{
    "lead" = @"
Role playbook:
- Build a lane map before dispatch: objective, owner role, files/surfaces, evidence needed, stop rule.
- Keep a decision log in your outbox when scope, priority, or evidence changes.
- Dispatch only bounded tasks; do not let specialists re-plan the whole system.
- Use financial specialists for business truth, engineers for implementation, reviewers/QA for challenge and verification.

Checklist:
- Define primary business question and current non-goals.
- Assign one owner per lane and name dependencies.
- Require evidence before accepting completion.
- Stop or re-scope when MCP, data lineage, or metric definition evidence is missing.

Evidence to collect:
- Role outbox links, task ids, verification commands, failed checks, unresolved blockers.
- lane map, decision log, stop rule, acceptance checklist.

Handoff format:
- Status by lane; completed evidence; open blockers; next dispatch recommendation.
"@
    "product-manager" = @"
Role playbook:
- Translate the user's request into the business question the page or workflow must answer.
- Separate goal, non-goal, user-facing risk, and acceptance criteria.
- Classify pages as formal, analytical, candidate, temporary, observation, or excluded.
- Reject vague "looks done" claims; require a business decision the user can make.

Checklist:
- Primary business question is one sentence.
- User-visible no data/stale/fallback/loading/definition pending states are named.
- formal/candidate/excluded status is explicit.
- acceptance criteria are testable and tied to user value.

Evidence to collect:
- page contract references, metric dictionary entries, stakeholder ambiguity, acceptance criteria.

Handoff format:
- Business question; non-goal; risk priority; acceptance criteria; unresolved ambiguity.
"@
    "frontend-developer" = @"
Role playbook:
- Own frontend page/component/adapter/model/formatter/selector lanes.
- Trace display data through adapter/model/formatter/selector before editing components.
- Use browser verification for visible changes and run npm run debt:audit when touching governed frontend paths.
- Never implement formal financial calculations in the frontend.

Checklist:
- Component displays source basis, date, quality, fallback/stale when required.
- adapter/model/formatter/selector tests cover changed display logic.
- browser verification or screenshot evidence covers the user-facing path.
- npm run debt:audit is run for page/API/mock/adapter/formatter/selector changes.

Evidence to collect:
- Changed frontend files, targeted tests, browser verification, debt:audit output, remaining UI risks.

Handoff format:
- Files changed; data-flow trace; tests run; browser evidence; residual risks.
"@
    "developer" = @"
Role playbook:
- Implement the smallest effective implementation inside the assigned lane.
- Prefer existing repo patterns, helpers, and boundaries.
- Add targeted tests before or with code changes.
- Avoid unrelated refactor, global abstractions, schema changes, and framework churn.

Checklist:
- Scope matches Leader assignment.
- no unrelated refactor or broad cleanup.
- targeted tests prove the behavior.
- Business metric logic stays in approved backend/domain paths.

Evidence to collect:
- Files changed, rationale, targeted tests, commands, known limitations.

Handoff format:
- Root cause; implementation summary; tests run; not-tested; risks.
"@
    "backend-api-contract-engineer" = @"
Role playbook:
- Own backend API route contract, result_meta, envelope, OpenAPI, and route/service boundaries.
- Check route contract before implementation and test result_meta plus result shape after.
- Keep mock/real/fallback behavior explicit and fail closed when formal-use evidence is absent.
- Do not silently widen endpoint behavior.

Checklist:
- route contract and OpenAPI operation remain stable or intentionally updated.
- result_meta includes basis, quality, fallback/stale, formal_use_allowed where relevant.
- route tests cover success, failure, and permission/contract shape.
- No hidden mock fallback in real mode.

Evidence to collect:
- Route/service files, contract tests, OpenAPI/API contract output, fallback classification.

Handoff format:
- Endpoint; contract delta; result_meta evidence; tests; residual contract risk.
"@
    "metric-caliber-officer" = @"
Role playbook:
- Own metric_id, unit, precision, date, currency, basis, and formal/candidate/excluded status.
- Compare docs/page_contracts.md, docs/metric_dictionary.md, golden samples, and page copy.
- Refuse to approve ambiguous metrics without source and owner evidence.
- Keep status visible to users, not hidden in navigation metadata.

Checklist:
- metric_id exists or candidate/GAP/excluded is explicit.
- unit, precision, date basis, currency, sign convention are documented.
- formal/candidate/excluded status matches page contract and dictionary.
- No frontend duplicate calculation creates a new metric.

Evidence to collect:
- metric dictionary lines, page contract entries, golden sample notes, unresolved owner approvals.

Handoff format:
- Metric list; accepted status; ambiguity; required approval/evidence.
"@
    "data-lineage-auditor" = @"
Role playbook:
- Trace API response -> adapter/model -> state/selector -> component -> chart/table.
- Verify source_version, rule/cache lineage, report date, generated_at, fallback/stale status.
- Prefer MCP evidence when available; otherwise mark local-only evidence and residual risk.
- Treat missing lineage as a blocker for formal-use claims.

Checklist:
- Every displayed metric has a complete data-flow path.
- source_version/rule/cache/date evidence is captured.
- fallback/stale/no data is surfaced to the user.
- Local-only review is labeled when MCP is unavailable.

Evidence to collect:
- API payload fields, adapter/model selectors, component display, lineage/catalog/MCP results.

Handoff format:
- Data-flow chain; evidence found; missing lineage; formal-use risk.
"@
    "security-permission-auditor" = @"
Role playbook:
- Review write route, execute permission, script runner, agent run, trust boundary, and audit record behavior.
- Distinguish read, create, execute, approve, and admin permissions.
- Check that high-risk registered scripts are not exposed through broad HTTP surfaces.
- Prefer tests proving unauthorized requests fail.

Checklist:
- Mutating POST/PUT/DELETE routes require non-read permissions.
- agent/tool/script execution has explicit execute permission.
- audit record exists for sensitive actions.
- route tests cover denied and allowed paths.

Evidence to collect:
- Route files, permission helpers, tests, audit log path, exploit scenario.

Handoff format:
- Finding severity; file/line; risk; recommended permission contract; test gap.
"@
    "asset-liability-manager" = @"
Role playbook:
- Own asset, liability, net position, report date, currency basis, duration mismatch, and balance-analysis conclusions.
- Reconcile headline totals to detail/workbook/summary when available.
- Keep formal basis separate from preview, analytical, or advanced attribution surfaces.
- Flag unit, date, currency, or scope mismatches immediately.

Checklist:
- asset and liability totals reconcile to detail.
- net position sign and currency basis are explicit.
- report_date/resolved_report_date/as_of_date are not mixed.
- preview/analytical data is not presented as formal truth.

Evidence to collect:
- Balance API fields, page contract, metric ids, totals reconciliation, fallback/stale state.

Handoff format:
- Balance conclusion; reconciliations; mismatches; required evidence.
"@
    "pnl-attribution-analyst" = @"
Role playbook:
- Reconcile total PnL before explaining drivers.
- Separate realized, unrealized, carry/accrual, MTM, FX, fees, trades, and residual.
- Use PnL bridge quality flags; never hide unexplained residual.
- Keep formal PnL and standardized/analytical totals distinct.

Checklist:
- Reported total equals component sum or residual is quantified.
- realized/unrealized/carry/accrual/FX treatment is explicit.
- Date window, currency, sign convention, and product scope are checked.
- residual and warning/error status are user-visible.

Evidence to collect:
- PnL API fields, bridge components, metric dictionary entries, residual calculations, tests.

Handoff format:
- Total reconciliation; driver table; residual; warnings; next data needed.
"@
    "risk-manager" = @"
Role playbook:
- Own DV01, KRD, CS01, duration, convexity, concentration, liquidity gap, denominator, and exclusion logic.
- Verify quality_flag before accepting any risk headline.
- Challenge synthetic or frontend-filled risk metrics.
- Connect risk tensor to underlying positions and market data where evidence exists.

Checklist:
- DV01/KRD/CS01 units and signs are correct.
- duration denominator, excluded market value, and excluded row count are visible.
- quality_flag and fallback/stale state are surfaced.
- No regulatory risk metric is synthesized without approved source.

Evidence to collect:
- Risk tensor payload, source positions, denominator/exclusion fields, tests, warnings.

Handoff format:
- Risk conclusion; metric quality; exclusions; unresolved data or convention risk.
"@
    "fixed-income-analyst" = @"
Role playbook:
- Own bond positions, yield curves, duration, convexity, spread, clean/dirty price, coupon/accrual, and curve bucket logic.
- Lock valuation date, currency, day count, compounding, benchmark curve, and price/yield convention first.
- Separate rate move, spread move, carry/accrual, FX, and residual when data supports it.
- Do not equate bond dashboard headline with formal balance or risk tensor truth unless approved.

Checklist:
- duration/convexity/spread conventions are documented.
- price-yield direction and unit scale are plausible.
- curve/source freshness is checked.
- Portfolio totals reconcile to line items where possible.

Evidence to collect:
- Bond analytics payload, curve/source fields, convention notes, reconciliation checks.

Handoff format:
- Fixed-income assumptions; analytics checked; mismatches; data gaps.
"@
    "market-data-specialist" = @"
Role playbook:
- Own rates, curves, prices, FX, source_version, vendor/preview/source-pending status, stale, and fallback.
- Separate formal rates from analytical observations and vendor previews.
- Check freshness, report date, natural date, and cached/generated_at semantics.
- Block formal-use claims when source lineage or freshness is missing.

Checklist:
- source_version, source name, generated_at/as_of date are displayed.
- stale and fallback are explicit.
- FX/rate/curve units and date basis are consistent.
- formal/analytical/source-pending sections are separated.

Evidence to collect:
- Market data API payloads, source/version fields, freshness checks, fallback warnings.

Handoff format:
- Source status; freshness; formal/analytical split; unresolved vendor/source risk.
"@
    "valuation-accounting-reconciler" = @"
Role playbook:
- Own valuation, accounting extracts, ledger, 514/516/517/manual/total_pnl, sign convention, and reconciliation.
- Compare accounting totals to formal read models before approving financial displays.
- Diagnose differences by grain, date, currency, account, product, sign, and source.
- Do not recreate formal accounting or PnL logic in the frontend.

Checklist:
- ledger path and accounting source are known.
- 514/516/517/manual/total_pnl treatment is explicit.
- sign convention and units are consistent.
- Reconciliation breaks are quantified and not hidden.

Evidence to collect:
- Ledger/accounting files, formal PnL paths, reconciliation totals, mismatch rows.

Handoff format:
- Reconciliation result; breaks; source/sign/unit findings; next evidence.
"@
    "ui-ux-page-closer" = @"
Role playbook:
- Own first-screen conclusion, page-level closure, business clarity, visible states, and interaction ergonomics.
- Make no data, stale, fallback, loading failure, and definition pending visible.
- Avoid marketing/landing page patterns for operational financial tools.
- Pair with Frontend Developer for implementation and QA for browser checks.

Checklist:
- first-screen conclusion answers the primary business question.
- no data/stale/fallback/loading/definition pending states are explicit.
- Buttons, tables, charts, and filters support the workflow without visual clutter.
- Page copy does not overclaim formal status.

Evidence to collect:
- Screenshot/browser notes, page copy, state inventory, acceptance criteria.

Handoff format:
- Page question; visible states; UX risks; recommended frontend lane.
"@
    "docs-delivery-manager" = @"
Role playbook:
- Own runbook, acceptance checklist, decision record, final synthesis, and handoff quality.
- Turn multi-role outboxes into a concise, source-backed delivery packet.
- Preserve uncertainty and not-tested sections.
- Never invent approvals, evidence, or test results.

Checklist:
- runbook commands are reproducible.
- acceptance checklist maps to user request and AGENTS.md.
- final synthesis separates done, blocked, risk, and next work.
- Source links or local file paths are included for evidence.

Evidence to collect:
- Role outboxes, command outputs, changed files, screenshots, test logs, blockers.

Handoff format:
- Executive summary; evidence; verification; residual risks; next dispatch.
"@
    "code-reviewer" = @"
Role playbook:
- Lead with findings first, ordered by severity.
- Use file/line references and focus on bugs, regressions, missing tests, security, and contract breaks.
- Challenge overbroad diffs and unrelated refactors.
- Do not summarize before findings when issues exist.

Checklist:
- Findings have severity, file/line, impact, and fix direction.
- missing tests are called out.
- Business metric or permission risks are escalated to specialists.
- No speculative issue is reported without evidence.

Evidence to collect:
- Diff, relevant source lines, tests run/not run, contract or business-rule references.

Handoff format:
- Findings; open questions; test gaps; brief summary.
"@
    "qa" = @"
Role playbook:
- Build a verification matrix for the assigned lane.
- Run targeted tests first; widen only when shared contracts or business metrics are touched.
- Capture failure evidence exactly and avoid saying pass until output proves it.
- Pair browser checks with frontend-visible changes.

Checklist:
- verification matrix covers requirement, command, expected result, actual result.
- targeted tests are run and read.
- failure evidence includes command, exit status, and key output.
- not-tested and residual risk are explicit.

Evidence to collect:
- targeted tests, lint/typecheck/build/browser checks, failure logs, environment blockers.

Handoff format:
- Verification matrix; pass/fail evidence; blockers; recommended next check.
"@
  }

  if ($playbooks.ContainsKey($Slug)) {
    return $playbooks[$Slug]
  }

  return @"
Role playbook:
- Follow the assigned lane exactly and report evidence clearly.

Checklist:
- Scope is understood.
- Evidence is captured.
- Blockers are explicit.

Evidence to collect:
- Files read, commands run, findings, blockers.

Handoff format:
- Findings; evidence; blockers; next step.
"@
}

function New-RolePrompt {
  param(
    [object]$Role,
    [string]$ProjectWorkspacePath,
    [string]$BoardPath,
    [string]$InboxPath,
    [string]$OutboxPath,
    [string]$RoleWorkspacePath,
    [string]$BackendProjectWorkspacePath,
    [string]$BackendBoardPath,
    [string]$BackendInboxPath,
    [string]$BackendOutboxPath,
    [string]$BackendRoleWorkspacePath,
    [string]$TaskText,
    [string]$TeamName
  )

  $rolePlaybook = Get-RolePlaybook -Slug $Role.Slug

  return @"
You are the $($Role.Title) agent in the local Hermes agent team "$TeamName".

Mission:
$($Role.Mission)

Current task:
$TaskText

Shared coordination files:
- Project workspace: $ProjectWorkspacePath
- Team board: $BoardPath
- Your inbox: $InboxPath
- Your outbox: $OutboxPath
- Your independent workspace: $RoleWorkspacePath

Backend-readable paths:
- Project workspace: $BackendProjectWorkspacePath
- Team board: $BackendBoardPath
- Your inbox: $BackendInboxPath
- Your outbox: $BackendOutboxPath
- Your independent workspace: $BackendRoleWorkspacePath

How to work:
1. Read AGENTS.md, docs/agent_codebase_map.md, and the closest subtree instructions from the project workspace before changing files.
2. Read TEAM_BOARD.md first, then your inbox.
3. Write concise findings, blockers, decisions, and verification evidence to your outbox.
4. Do not overwrite another role's files. Leave cross-role requests in TEAM_BOARD.md or the target role inbox.
5. Use your independent workspace for role-local notes, scratch files, and handoff artifacts.
6. Keep changes minimal and scoped to your assigned lane.
7. Do not commit unless the human explicitly asks.
8. Verify before claiming completion.

Role boundaries:
$($Role.Boundaries)

$rolePlaybook

Start now by reading the shared board and your inbox, then perform only the work assigned to this role.
"@
}

function ConvertTo-HtmlText {
  param([string]$Value)

  if ($null -eq $Value) {
    return ""
  }
  return [System.Net.WebUtility]::HtmlEncode($Value)
}

function Get-TextFileOrDefault {
  param(
    [string]$Path,
    [string]$DefaultValue
  )

  if (Test-Path -LiteralPath $Path) {
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8
  }
  return $DefaultValue
}

function New-DashboardHtml {
  param(
    [object[]]$AllRoles,
    [object[]]$SelectedRoles,
    [string]$TeamName,
    [string]$TaskText,
    [string]$Workspace,
    [string]$Backend,
    [string]$BoardPath,
    [string]$PromptDir,
    [string]$InboxDir,
    [string]$OutboxDir,
    [string]$SessionDir,
    [string]$LaunchDir,
    [string]$CreatedAt
  )

  $textConnected = ConvertFrom-UnicodeEscape "\u5df2\u8fde\u63a5"
  $textWaiting = ConvertFrom-UnicodeEscape "\u7b49\u5f85\u4e2d"
  $textSelected = ConvertFrom-UnicodeEscape "\u5df2\u9009\u4e2d"
  $textReady = ConvertFrom-UnicodeEscape "\u5df2\u51c6\u5907"
  $textSession = ConvertFrom-UnicodeEscape "\u4f1a\u8bdd"
  $textPrompt = ConvertFrom-UnicodeEscape "\u63d0\u793a\u8bcd"
  $textInbox = ConvertFrom-UnicodeEscape "\u4efb\u52a1\u7bb1"
  $textOutbox = ConvertFrom-UnicodeEscape "\u6c47\u62a5\u7bb1"
  $textLaunch = ConvertFrom-UnicodeEscape "\u542f\u52a8"
  $textLatestReport = ConvertFrom-UnicodeEscape "\u6700\u65b0\u6c47\u62a5"
  $textDashboardTitle = ConvertFrom-UnicodeEscape "Agent \u56e2\u961f\u63a7\u5236\u53f0"
  $textObjective = ConvertFrom-UnicodeEscape "\u76ee\u6807"
  $textRole = ConvertFrom-UnicodeEscape "\u89d2\u8272"
  $textTaskTitle = ConvertFrom-UnicodeEscape "\u6807\u9898"
  $textTaskTitlePlaceholder = ConvertFrom-UnicodeEscape "\u4e00\u53e5\u8bdd\u4efb\u52a1\u6807\u9898"
  $textTask = ConvertFrom-UnicodeEscape "\u4efb\u52a1"
  $textTaskPlaceholder = ConvertFrom-UnicodeEscape "\u5199\u6e05\u695a\u4efb\u52a1\u3001\u8303\u56f4\u3001\u5b8c\u6210\u6807\u51c6\u548c\u9a8c\u8bc1\u8981\u6c42\u3002"
  $textDispatchTask = ConvertFrom-UnicodeEscape "\u6d3e\u53d1\u4efb\u52a1"
  $textStartDispatch = ConvertFrom-UnicodeEscape "\u542f\u52a8\u6d3e\u53d1\u670d\u52a1"
  $textTaskStatus = ConvertFrom-UnicodeEscape "\u4efb\u52a1\u72b6\u6001"
  $textRecentTask = ConvertFrom-UnicodeEscape "\u6700\u8fd1\u4efb\u52a1"
  $textExecutionLog = ConvertFrom-UnicodeEscape "\u6267\u884c\u65e5\u5fd7"
  $textResultPreview = ConvertFrom-UnicodeEscape "\u7ed3\u679c\u9884\u89c8"
  $textQueue = ConvertFrom-UnicodeEscape "\u961f\u5217"
  $textAttempts = ConvertFrom-UnicodeEscape "\u5c1d\u8bd5\u6b21\u6570"
  $textAttention = ConvertFrom-UnicodeEscape "\u9700\u8981\u5904\u7406"
  $textWorkspace = ConvertFrom-UnicodeEscape "\u5de5\u4f5c\u533a"
  $textRetry = ConvertFrom-UnicodeEscape "\u91cd\u8bd5"
  $textNoTask = ConvertFrom-UnicodeEscape "\u6682\u65e0\u4efb\u52a1"
  $textNoLog = ConvertFrom-UnicodeEscape "\u6682\u65e0\u65e5\u5fd7"
  $textNoReport = ConvertFrom-UnicodeEscape "\u6682\u65e0\u6c47\u62a5"
  $textNoQueue = ConvertFrom-UnicodeEscape "\u6682\u65e0\u6392\u961f"
  $textNoAttention = ConvertFrom-UnicodeEscape "\u6682\u65e0\u9700\u8981\u5904\u7406"
  $textLaunchCommand = ConvertFrom-UnicodeEscape "\u542f\u52a8\u547d\u4ee4"
  $textTaskBodyRequired = ConvertFrom-UnicodeEscape "\u8bf7\u5148\u586b\u5199\u4efb\u52a1\u5185\u5bb9\u3002"
  $textDispatching = ConvertFrom-UnicodeEscape "\u6b63\u5728\u6d3e\u53d1..."
  $textRetrying = ConvertFrom-UnicodeEscape "\u6b63\u5728\u91cd\u8bd5..."
  $textRetried = ConvertFrom-UnicodeEscape "\u5df2\u91cd\u8bd5 "
  $textDispatchedTo = ConvertFrom-UnicodeEscape "\u5df2\u6d3e\u53d1\u7ed9 "
  $textDispatchedAndWoke = ConvertFrom-UnicodeEscape "\u5df2\u6d3e\u53d1\u5e76\u5524\u9192 "
  $textDispatchServerMissing = ConvertFrom-UnicodeEscape "\u6d3e\u53d1\u670d\u52a1\u672a\u542f\u52a8\u3002\u8bf7\u8fd0\u884c\uff1a"

  $selected = @{}
  foreach ($role in $SelectedRoles) {
    $selected[$role.Slug] = $true
  }

  $roleCards = ($AllRoles | ForEach-Object {
    $role = $_
    $promptPath = Join-Path $PromptDir "$($role.Slug).md"
    $inboxPath = Join-Path $InboxDir "$($role.Slug).md"
    $outboxPath = Join-Path $OutboxDir "$($role.Slug).md"
    $sessionPath = Join-Path $SessionDir "$($role.Slug).txt"
    $launcherPath = Join-Path $LaunchDir "$($role.Slug).ps1"
    $workspacePath = Join-Path (Split-Path -Parent $PromptDir) "workspaces\$($role.Slug)"
    $sessionId = (Get-TextFileOrDefault -Path $sessionPath -DefaultValue "").Trim()
    $outboxText = Get-TextFileOrDefault -Path $outboxPath -DefaultValue "No report yet."
    $isConnected = -not [string]::IsNullOrWhiteSpace($sessionId)
    $status = if ($isConnected) { $textConnected } else { $textWaiting }
    $active = if ($selected.ContainsKey($role.Slug)) { $textSelected } else { $textReady }
    $stateClass = if ($isConnected) { "connected" } else { "waiting" }

@"
      <section class="lane $stateClass" data-role="$($role.Slug)">
        <header class="lane-head">
          <div>
            <p class="lane-kicker">$active</p>
            <h2>$(ConvertTo-HtmlText $role.DisplayTitle)</h2>
          </div>
          <span class="status" data-status="$($role.Slug)">$status</span>
        </header>
        <p class="mission">$(ConvertTo-HtmlText $role.Mission)</p>
        <dl class="meta">
          <div><dt>$textSession</dt><dd data-session="$($role.Slug)">$(ConvertTo-HtmlText $sessionId)</dd></div>
          <div><dt>$textPrompt</dt><dd><a href="prompts/$($role.Slug).md">prompts/$($role.Slug).md</a></dd></div>
          <div><dt>$textInbox</dt><dd><a href="inbox/$($role.Slug).md">inbox/$($role.Slug).md</a></dd></div>
          <div><dt>$textOutbox</dt><dd><a href="outbox/$($role.Slug).md">outbox/$($role.Slug).md</a></dd></div>
          <div><dt>$textWorkspace</dt><dd data-workspace="$($role.Slug)">$(ConvertTo-HtmlText $workspacePath)</dd></div>
          <div><dt>$textLaunch</dt><dd><a href="launch/$($role.Slug).ps1">launch/$($role.Slug).ps1</a></dd></div>
        </dl>
        <div class="report">
          <div class="report-title">$textLatestReport</div>
          <pre data-outbox="$($role.Slug)">$(ConvertTo-HtmlText $outboxText)</pre>
        </div>
        <div class="task-panel">
          <div class="report-title">$textTaskStatus</div>
          <div class="task-row">
            <span>$textRecentTask</span>
            <strong data-task="$($role.Slug)">$textNoTask</strong>
          </div>
          <div class="task-row">
            <span>$textQueue</span>
            <strong data-queue="$($role.Slug)">$textNoQueue</strong>
          </div>
          <div class="task-row">
            <span>$textAttempts</span>
            <strong data-attempts="$($role.Slug)">0</strong>
          </div>
          <div class="task-row attention-row">
            <span>$textAttention</span>
            <strong data-attention="$($role.Slug)">$textNoAttention</strong>
          </div>
          <div class="task-row">
            <span>$textExecutionLog</span>
            <strong data-log-path="$($role.Slug)">$textNoLog</strong>
          </div>
          <button class="retry-button" type="button" data-retry="$($role.Slug)" disabled>$textRetry</button>
          <pre class="log-preview" data-log="$($role.Slug)">$textNoLog</pre>
        </div>
      </section>
"@
  }) -join [Environment]::NewLine

  $roleJson = @($AllRoles | ForEach-Object {
    [pscustomobject]@{
      slug = $_.Slug
      title = $_.DisplayTitle
    }
  }) | ConvertTo-Json -Compress

  $roleOptions = ($AllRoles | ForEach-Object {
    $optionTitle = ConvertTo-HtmlText $_.DisplayTitle
    "          <option value=""$($_.Slug)"">$optionTitle</option>"
  }) -join [Environment]::NewLine

  return @"
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>$textDashboardTitle - $TeamName</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #101214;
      --panel: #171a1d;
      --panel-2: #1f2327;
      --line: #30363d;
      --text: #f0f3f5;
      --muted: #9ca6ae;
      --soft: #c7d0d6;
      --green: #4fc878;
      --amber: #d7a94d;
      --cyan: #53b6c7;
      --red: #df6262;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: Aptos, "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 1.45;
    }

    a {
      color: var(--cyan);
      text-decoration: none;
    }

    a:hover { text-decoration: underline; }

    .shell {
      min-width: 1420px;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      padding: 18px 22px 14px;
      border-bottom: 1px solid var(--line);
      background: #141719;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 280px;
    }

    .mark {
      width: 28px;
      height: 28px;
      border: 1px solid var(--line);
      display: grid;
      place-items: center;
      color: var(--green);
      font-weight: 700;
    }

    h1, h2, p { margin: 0; }

    h1 {
      font-size: 18px;
      font-weight: 650;
      letter-spacing: 0;
    }

    .subtitle {
      margin-top: 2px;
      color: var(--muted);
      font-size: 12px;
    }

    .objective {
      flex: 1;
      display: grid;
      gap: 4px;
      min-width: 480px;
    }

    .label {
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
    }

    .objective strong {
      color: var(--soft);
      font-weight: 520;
    }

    .ops {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }

    .pill {
      border: 1px solid var(--line);
      background: var(--panel-2);
      color: var(--soft);
      padding: 5px 9px;
    }

    .board {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      flex: 1;
      border-bottom: 1px solid var(--line);
    }

    .lane {
      min-height: calc(100vh - 74px);
      padding: 16px 14px 18px;
      border-right: 1px solid var(--line);
      background: var(--panel);
      display: flex;
      flex-direction: column;
      gap: 14px;
    }

    .lane:last-child { border-right: 0; }

    .lane-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      min-height: 44px;
    }

    .lane-kicker {
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      margin-bottom: 2px;
    }

    h2 {
      font-size: 16px;
      font-weight: 650;
      letter-spacing: 0;
    }

    .status {
      height: 24px;
      border: 1px solid var(--line);
      background: #121416;
      color: var(--amber);
      padding: 3px 7px;
      font-size: 12px;
      white-space: nowrap;
    }

    .connected .status {
      color: var(--green);
      border-color: rgba(79, 200, 120, .45);
    }

    .needs-attention .status {
      color: var(--red);
      border-color: rgba(223, 98, 98, .55);
    }

    .mission {
      color: var(--soft);
      min-height: 62px;
      font-size: 13px;
    }

    .meta {
      margin: 0;
      display: grid;
      gap: 7px;
      padding: 11px;
      border: 1px solid var(--line);
      background: #131619;
    }

    .meta div {
      display: grid;
      grid-template-columns: 56px minmax(0, 1fr);
      gap: 8px;
      align-items: baseline;
    }

    dt {
      color: var(--muted);
      font-size: 11px;
    }

    dd {
      margin: 0;
      min-width: 0;
      color: var(--soft);
      overflow-wrap: anywhere;
      font-family: "Cascadia Mono", Consolas, monospace;
      font-size: 11px;
    }

    .report {
      flex: 1;
      min-height: 320px;
      display: flex;
      flex-direction: column;
      border: 1px solid var(--line);
      background: #111416;
    }

    .report-title {
      padding: 10px 11px;
      border-bottom: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }

    pre {
      flex: 1;
      margin: 0;
      padding: 12px;
      color: var(--text);
      white-space: pre-wrap;
      overflow: auto;
      font-family: "Cascadia Mono", Consolas, monospace;
      font-size: 12px;
      line-height: 1.55;
    }

    .task-panel {
      display: grid;
      gap: 0;
      border: 1px solid var(--line);
      background: #101315;
    }

    .task-row {
      display: grid;
      grid-template-columns: 64px minmax(0, 1fr);
      gap: 8px;
      padding: 8px 10px;
      border-bottom: 1px solid var(--line);
      color: var(--muted);
      font-size: 11px;
    }

    .task-row strong {
      min-width: 0;
      color: var(--soft);
      font-family: "Cascadia Mono", Consolas, monospace;
      font-weight: 500;
      overflow-wrap: anywhere;
    }

    .attention-row strong.warn {
      color: var(--red);
    }

    .retry-button {
      margin: 9px 10px 0;
      border: 1px solid rgba(83, 182, 199, .48);
      background: #101c20;
      color: var(--cyan);
      font-weight: 650;
      padding: 8px 10px;
      cursor: pointer;
    }

    .retry-button:disabled {
      cursor: not-allowed;
      opacity: .42;
    }

    .log-preview {
      max-height: 150px;
      min-height: 82px;
      color: var(--soft);
      background: #0d1012;
    }

    .commandbar {
      display: flex;
      gap: 10px;
      padding: 10px 14px;
      border-top: 1px solid var(--line);
      background: #121517;
      color: var(--muted);
      font-size: 12px;
    }

    .commandbar code {
      color: var(--soft);
      font-family: "Cascadia Mono", Consolas, monospace;
      overflow-wrap: anywhere;
    }

    .dispatch {
      display: grid;
      grid-template-columns: 170px 220px minmax(320px, 1fr) auto;
      gap: 10px;
      align-items: stretch;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: #101315;
    }

    .dispatch label {
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
    }

    .dispatch select,
    .dispatch input,
    .dispatch textarea {
      width: 100%;
      border: 1px solid var(--line);
      background: #15191c;
      color: var(--text);
      padding: 9px 10px;
      font: inherit;
      font-size: 13px;
      outline: none;
    }

    .dispatch textarea {
      min-height: 58px;
      resize: vertical;
    }

    .dispatch button {
      align-self: end;
      min-width: 128px;
      border: 1px solid rgba(79, 200, 120, .55);
      background: #142118;
      color: var(--green);
      font-weight: 650;
      padding: 10px 14px;
      cursor: pointer;
    }

    .dispatch button:hover {
      background: #19301f;
    }

    .dispatch-status {
      grid-column: 1 / -1;
      min-height: 20px;
      color: var(--muted);
      font-size: 12px;
    }

    @media (max-width: 1500px) {
      .shell { min-width: 1180px; }
      .board { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
      .lane { padding: 14px 10px; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand">
        <div class="mark">A5</div>
        <div>
          <h1>$textDashboardTitle</h1>
          <p class="subtitle">$TeamName / $CreatedAt</p>
        </div>
      </div>
      <div class="objective">
        <span class="label">$textObjective</span>
        <strong>$(ConvertTo-HtmlText $TaskText)</strong>
      </div>
      <div class="ops">
        <span class="pill">$Backend</span>
        <span class="pill"><a href="TEAM_BOARD.md">TEAM_BOARD.md</a></span>
      </div>
    </header>
    <form class="dispatch" id="dispatchForm">
      <label>
        $textRole
        <select data-dispatch-role>
$roleOptions
        </select>
      </label>
      <label>
        $textTaskTitle
        <input data-dispatch-title placeholder="$textTaskTitlePlaceholder">
      </label>
      <label>
        $textTask
        <textarea data-dispatch-body placeholder="$textTaskPlaceholder"></textarea>
      </label>
      <button type="submit">$textDispatchTask</button>
      <div class="dispatch-status" data-dispatch-status>${textStartDispatch}: python scripts/hermes_team_dispatch_server.py --team-dir .omx/hermes-teams/$TeamName --port 8795</div>
    </form>
    <section class="board" aria-label="Hermes agent lanes">
$roleCards
    </section>
    <footer class="commandbar">
      <span>$textLaunchCommand</span>
      <code>powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-hermes-agent-team.ps1 -Launch -Layout Panes -TeamId $TeamName -Backend $Backend</code>
    </footer>
  </main>
  <script>
    const roles = $roleJson;
    const dispatchForm = document.getElementById("dispatchForm");
    const dispatchStatus = document.querySelector("[data-dispatch-status]");

    function apiHeaders(extra) {
      return Object.assign({}, extra || {});
    }

    function textOr(value, fallback) {
      return value && String(value).trim() ? String(value).trim() : fallback;
    }

    function renderRoleStatus(roleStatus) {
      const slug = roleStatus.slug;
      const session = textOr(roleStatus.session_id, "");
      const sessionTarget = document.querySelector("[data-session='" + slug + "']");
      const outboxTarget = document.querySelector("[data-outbox='" + slug + "']");
      const statusTarget = document.querySelector("[data-status='" + slug + "']");
      const lane = document.querySelector("[data-role='" + slug + "']");
      const taskTarget = document.querySelector("[data-task='" + slug + "']");
      const queueTarget = document.querySelector("[data-queue='" + slug + "']");
      const attemptsTarget = document.querySelector("[data-attempts='" + slug + "']");
      const attentionTarget = document.querySelector("[data-attention='" + slug + "']");
      const workspaceTarget = document.querySelector("[data-workspace='" + slug + "']");
      const logPathTarget = document.querySelector("[data-log-path='" + slug + "']");
      const logTarget = document.querySelector("[data-log='" + slug + "']");
      const retryTarget = document.querySelector("[data-retry='" + slug + "']");
      const attention = Array.isArray(roleStatus.attention) ? roleStatus.attention : [];

      if (sessionTarget) sessionTarget.textContent = session;
      if (outboxTarget) outboxTarget.textContent = textOr(roleStatus.outbox_preview, "$textNoReport");
      if (statusTarget) statusTarget.textContent = session ? "$textConnected" : "$textWaiting";
      if (workspaceTarget) workspaceTarget.textContent = textOr(roleStatus.workspace, "");
      if (taskTarget) {
        const task = roleStatus.recent_task;
        const state = roleStatus.task_state ? "[" + roleStatus.task_state + "] " : "";
        taskTarget.textContent = task && task.task_id ? state + task.task_id + " / " + task.title : "$textNoTask";
      }
      if (queueTarget) {
        const queueCount = Number(roleStatus.queue_count || 0);
        queueTarget.textContent = queueCount ? queueCount + " task(s)" : "$textNoQueue";
      }
      if (attemptsTarget) {
        const task = roleStatus.recent_task;
        attemptsTarget.textContent = task && task.attempts ? String(task.attempts) : "0";
      }
      if (attentionTarget) {
        attentionTarget.textContent = attention.length
          ? attention.map((item) => item.reason + " / " + item.task_id).join(" | ")
          : "$textNoAttention";
        attentionTarget.classList.toggle("warn", attention.length > 0);
      }
      if (logPathTarget) {
        const task = roleStatus.recent_task;
        logPathTarget.textContent = task && task.dispatch_log ? task.dispatch_log : "$textNoLog";
      }
      if (logTarget) logTarget.textContent = textOr(roleStatus.log_tail, "$textNoLog");
      if (retryTarget) {
        const task = roleStatus.recent_task;
        retryTarget.disabled = !(task && task.task_id);
        retryTarget.dataset.taskId = task && task.task_id ? task.task_id : "";
      }
      if (lane) {
        lane.classList.toggle("connected", Boolean(session));
        lane.classList.toggle("waiting", !session);
        lane.classList.toggle("needs-attention", attention.length > 0);
      }
    }

    async function retryTask(taskId) {
      if (!taskId) return;
      dispatchStatus.textContent = "$textRetrying";
      try {
        const response = await fetch("/api/retry", {
          method: "POST",
          headers: apiHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({ task_id: taskId })
        });
        const result = await response.json();
        if (!response.ok || !result.ok) {
          throw new Error(result.error || "Retry failed");
        }
        dispatchStatus.textContent = "$textRetried" + result.role + " / " + result.task_id;
        await refresh();
      } catch (error) {
        dispatchStatus.textContent = "$textDispatchServerMissing python scripts/hermes_team_dispatch_server.py --team-dir .omx/hermes-teams/$TeamName --port 8795";
      }
    }

    async function refreshFromStatusApi() {
      const response = await fetch("/api/status?t=" + Date.now(), {
        cache: "no-store",
        headers: apiHeaders()
      });
      if (!response.ok) throw new Error("status unavailable");
      const status = await response.json();
      for (const role of roles) {
        if (status.roles && status.roles[role.slug]) {
          renderRoleStatus(status.roles[role.slug]);
        }
      }
    }

    async function refresh() {
      try {
        await refreshFromStatusApi();
        return;
      } catch (_) {
        // Direct file opens keep the embedded snapshot. HTTP mode uses /api/status.
      }
    }

    setInterval(refresh, 5000);
    refresh();

    document.querySelectorAll("[data-retry]").forEach((button) => {
      button.addEventListener("click", async () => retryTask(button.dataset.taskId));
    });

    if (dispatchForm) {
      dispatchForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const payload = {
          role: document.querySelector("[data-dispatch-role]").value,
          title: document.querySelector("[data-dispatch-title]").value,
          body: document.querySelector("[data-dispatch-body]").value,
          sender: "dashboard"
        };
        if (!payload.body.trim()) {
          dispatchStatus.textContent = "$textTaskBodyRequired";
          return;
        }
        dispatchStatus.textContent = "$textDispatching";
        try {
          const response = await fetch("/api/dispatch", {
            method: "POST",
            headers: apiHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify(payload)
          });
          const result = await response.json();
          if (!response.ok || !result.ok) {
            throw new Error(result.error || "Dispatch failed");
          }
          dispatchStatus.textContent = result.wake && result.wake.ok
            ? "$textDispatchedAndWoke" + result.role + " -> " + result.inbox
            : "$textDispatchedTo" + result.role + " -> " + result.inbox;
          document.querySelector("[data-dispatch-title]").value = "";
          document.querySelector("[data-dispatch-body]").value = "";
          await refresh();
        } catch (error) {
          dispatchStatus.textContent = "$textDispatchServerMissing python scripts/hermes_team_dispatch_server.py --team-dir .omx/hermes-teams/$TeamName --port 8795";
        }
      });
    }
  </script>
</body>
</html>
"@
}

$resolvedTeamId = Get-SafeTeamId -RawTeamId $TeamId
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
  $OutputRoot = Join-Path $root ".omx\hermes-teams"
}

$teamDir = Join-Path $OutputRoot $resolvedTeamId
$dispatchUrl = "http://127.0.0.1:8795"
$dispatchToken = New-DispatchToken
$promptDir = Join-Path $teamDir "prompts"
$inboxDir = Join-Path $teamDir "inbox"
$outboxDir = Join-Path $teamDir "outbox"
$launchDir = Join-Path $teamDir "launch"
$sessionDir = Join-Path $teamDir "sessions"
$workspaceDir = Join-Path $teamDir "workspaces"
$queueDir = Join-Path $teamDir "queue"
$queuePath = Join-Path $queueDir "tasks.json"
New-Item -ItemType Directory -Force -Path $promptDir, $inboxDir, $outboxDir, $launchDir, $sessionDir, $workspaceDir, $queueDir | Out-Null
if (-not (Test-Path -LiteralPath $queuePath)) {
  Write-Utf8File -Path $queuePath -Value "[]"
}
$roleRunnerPath = Join-Path $launchDir "run-role.ps1"
Write-Utf8File -Path $roleRunnerPath -Value (New-RoleRunnerScript)

$allRoles = @()
$allRoles += New-Role `
  -Slug "lead" `
  -Title "Leader" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "\u603b\u7ecf\u7406") `
  -Mission (ConvertFrom-UnicodeEscape "\u8d1f\u8d23\u62c6\u89e3\u4efb\u52a1\u3001\u5b89\u6392\u987a\u5e8f\u3001\u534f\u8c03\u5404\u89d2\u8272\uff0c\u5e76\u8f93\u51fa\u6700\u7ec8\u6c47\u603b\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u9664\u975e\u56e2\u961f\u88ab\u5361\u4f4f\uff0c\u5426\u5219\u4e0d\u8981\u4eb2\u81ea\u505a\u5927\u8303\u56f4\u4ee3\u7801\u4fee\u6539\u3002\u4f60\u7684\u91cd\u70b9\u662f\u5206\u914d\u6e05\u6670\u4efb\u52a1\u7ebf\u3001\u8bfb\u53d6\u5404\u89d2\u8272\u6c47\u62a5\u3001\u5904\u7406\u51b2\u7a81\uff0c\u5e76\u4ea7\u51fa\u6700\u7ec8\u9a8c\u6536\u6e05\u5355\u3002")
$allRoles += New-Role `
  -Slug "product-manager" `
  -Title "Product Manager" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "\u4ea7\u54c1\u7ecf\u7406") `
  -Mission (ConvertFrom-UnicodeEscape "\u628a\u7528\u6237\u76ee\u6807\u7ffb\u8bd1\u6210\u9875\u9762/\u6d41\u7a0b\u9700\u6c42\u3001\u6210\u529f\u6807\u51c6\u548c\u4e1a\u52a1\u98ce\u9669\u4f18\u5148\u7ea7\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u4e0d\u8981\u5b9e\u73b0\u4ee3\u7801\u3002\u4f60\u7684\u91cd\u70b9\u662f\u660e\u786e\u6838\u5fc3\u95ee\u9898\u3001\u975e\u76ee\u6807\u3001\u5fc5\u9700\u8bc1\u636e\u3001\u6b67\u4e49\u70b9\u548c\u9a8c\u6536\u6807\u51c6\u3002")
$allRoles += New-Role `
  -Slug "frontend-developer" `
  -Title "Frontend Developer" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "\u524d\u7aef\u5f00\u53d1\u5de5\u7a0b\u5e08") `
  -Mission (ConvertFrom-UnicodeEscape "\u4e13\u6ce8\u524d\u7aef\u9875\u9762\u3001\u7ec4\u4ef6\u3001\u9002\u914d\u5668\u3001\u72b6\u6001\u5c55\u793a\u3001\u4ea4\u4e92\u548c\u6d4f\u89c8\u5668\u9a8c\u8bc1\uff0c\u628a\u9875\u9762\u505a\u5230\u53ef\u7528\u3001\u53ef\u8ffd\u6eaf\u3001\u53ef\u9a8c\u6536\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u4f18\u5148\u5904\u7406 frontend/ \u8303\u56f4\u5185\u7684\u9875\u9762\u3001\u7ec4\u4ef6\u3001adapter/model/formatter/selector \u548c\u76ee\u6807\u6d4b\u8bd5\u3002\u4e0d\u8981\u5728\u524d\u7aef\u8865\u6b63\u5f0f\u91d1\u878d\u8ba1\u7b97\uff1b\u9047\u5230\u6307\u6807\u53e3\u5f84\u3001\u8840\u7f18\u6216\u540e\u7aef\u5951\u7ea6\u4e0d\u6e05\u65f6\uff0c\u5411 Leader \u62a5\u544a\u800c\u4e0d\u731c\u3002")
$allRoles += New-Role `
  -Slug "developer" `
  -Title "Developer" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "\u5f00\u53d1\u5de5\u7a0b\u5e08") `
  -Mission (ConvertFrom-UnicodeEscape "\u6309\u603b\u7ecf\u7406\u5206\u914d\u7684\u4efb\u52a1\uff0c\u7528\u9879\u76ee\u73b0\u6709\u6a21\u5f0f\u505a\u6700\u5c0f\u6709\u6548\u5b9e\u73b0\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u53ea\u6539\u88ab\u5206\u914d\u7684\u6587\u4ef6\u3002\u9664\u975e\u603b\u7ecf\u7406\u7ed9\u51fa\u8bc1\u636e\u5e76\u660e\u786e\u6307\u6d3e\uff0c\u5426\u5219\u4e0d\u8981\u78b0\u540e\u7aef\u3001\u6570\u636e\u5e93\u3001\u8ba4\u8bc1\u6216\u5171\u4eab\u57fa\u7840\u8bbe\u65bd\u3002")
$allRoles += New-Role `
  -Slug "backend-api-contract-engineer" `
  -Title "Backend API Contract Engineer" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "\u540e\u7aef/API\u5408\u540c\u5de5\u7a0b\u5e08") `
  -Mission (ConvertFrom-UnicodeEscape "\u4e13\u6ce8\u540e\u7aef API \u5951\u7ea6\u3001result_meta/envelope\u3001route/service \u8fb9\u754c\u3001mock/real/fallback \u5206\u5c42\u548c\u76ee\u6807\u5408\u540c\u6d4b\u8bd5\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u4f18\u5148\u5904\u7406 backend/app/api\u3001backend/app/services \u548c tests/ \u4e2d\u7684\u5951\u7ea6\u6d4b\u8bd5\u3002\u672a\u88ab\u660e\u786e\u6307\u6d3e\u65f6\uff0c\u4e0d\u8981\u4fee\u6539\u6570\u636e\u5e93 schema\u3001\u8ba4\u8bc1\u6846\u67b6\u6216\u5171\u4eab\u57fa\u7840\u5c42\u3002")
$allRoles += New-Role `
  -Slug "metric-caliber-officer" `
  -Title "Metric Caliber Officer" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "\u6307\u6807\u53e3\u5f84\u5b98") `
  -Mission (ConvertFrom-UnicodeEscape "\u5ba1\u6838 metric_id\u3001\u5355\u4f4d\u3001\u7cbe\u5ea6\u3001\u62a5\u544a\u65e5/as_of_date\u3001formal/candidate/excluded \u72b6\u6001\u548c\u6307\u6807\u5b57\u5178/\u9875\u9762\u5951\u7ea6\u4e00\u81f4\u6027\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u6307\u6807\u5b9a\u4e49\u4e0d\u6e05\u65f6\u5fc5\u987b\u62a5\u544a\u6b67\u4e49\u548c\u8bc1\u636e\uff0c\u4e0d\u5f97\u731c\u3002\u9ed8\u8ba4\u4e0d\u5b9e\u73b0\u4ee3\u7801\uff1b\u82e5\u88ab\u6307\u6d3e\u4fee\u6539\uff0c\u53ea\u52a8 docs/page_contracts.md\u3001docs/metric_dictionary.md \u6216\u76ee\u6807\u6d4b\u8bd5\u8303\u56f4\u3002")
$allRoles += New-Role `
  -Slug "data-lineage-auditor" `
  -Title "Data Lineage Auditor" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "\u6570\u636e\u8840\u7f18\u5ba1\u8ba1\u5458") `
  -Mission (ConvertFrom-UnicodeEscape "\u8ffd\u8e2a API response -> adapter/model -> state/selector -> component -> chart/table\uff0c\u6838\u5bf9 source/rule/cache version\u3001fallback/stale \u548c\u6570\u636e\u76ee\u5f55\u8bc1\u636e\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u9ed8\u8ba4\u505a\u53ea\u8bfb\u8bc1\u636e\u5ba1\u8ba1\u3002\u4f18\u5148\u4f7f\u7528\u9879\u76ee MCP \u548c\u672c\u5730\u6587\u6863/\u4ee3\u7801\u8bc1\u636e\uff1bMCP \u4e0d\u53ef\u7528\u65f6\u5fc5\u987b\u6807\u6ce8\u6b8b\u4f59\u98ce\u9669\u3002")
$allRoles += New-Role `
  -Slug "security-permission-auditor" `
  -Title "Security Permission Auditor" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "\u5b89\u5168\u6743\u9650\u5ba1\u8ba1\u5458") `
  -Mission (ConvertFrom-UnicodeEscape "\u5ba1\u67e5 agent run\u3001script runner\u3001POST/PUT/DELETE \u5199\u8def\u7531\u3001\u6743\u9650\u62c6\u5206\u3001trust boundary \u548c\u5ba1\u8ba1\u8bb0\u5f55\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u9ed8\u8ba4\u53ea\u8f93\u51fa\u98ce\u9669\u548c\u5efa\u8bae\u3002\u672a\u88ab\u6307\u6d3e\u65f6\uff0c\u4e0d\u4fee\u6539\u8ba4\u8bc1/\u6743\u9650\u6846\u67b6\uff1b\u88ab\u6307\u6d3e\u65f6\u5fc5\u987b\u914d\u5957\u6700\u5c0f route/auth \u6d4b\u8bd5\u3002")
$allRoles += New-Role `
  -Slug "asset-liability-manager" `
  -Title "Asset Liability Manager" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "\u8d44\u4ea7\u8d1f\u503a\u7ba1\u7406\u4e13\u5bb6") `
  -Mission (ConvertFrom-UnicodeEscape "\u4e13\u6ce8\u8d44\u4ea7\u8d1f\u503a\u8868\u3001\u4e45\u671f\u9519\u914d\u3001\u51c0\u5934\u5bf8\u3001\u4ea7\u54c1/\u8d26\u6237/\u5e01\u79cd\u62c6\u5206\u3001\u62a5\u544a\u65e5\u548c\u8d44\u4ea7\u8d1f\u503a\u5206\u6790\u9875\u7684\u4e1a\u52a1\u6b63\u786e\u6027\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u4e0d\u5728\u524d\u7aef\u6216\u672a\u6388\u6743\u4ee3\u7801\u4e2d\u65b0\u9020\u8d44\u4ea7\u8d1f\u503a\u53e3\u5f84\u3002\u5fc5\u987b\u6838\u5bf9\u5355\u4f4d\u3001\u5e01\u79cd\u3001\u65e5\u671f\u3001formal basis \u548c result_meta\u3002")
$allRoles += New-Role `
  -Slug "pnl-attribution-analyst" `
  -Title "PnL Attribution Analyst" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "PnL\u5f52\u56e0\u5206\u6790\u5e08") `
  -Mission (ConvertFrom-UnicodeEscape "\u4e13\u6ce8\u603b\u635f\u76ca\u3001realized/unrealized\u3001carry/accrual\u3001MTM\u3001FX\u3001fee\u3001residual\u3001PnL bridge \u548c\u4ea7\u54c1\u5206\u7c7b\u635f\u76ca\u5bf9\u8d26\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u5148\u5bf9\u9f50 total PnL\uff0c\u518d\u89e3\u91ca\u9a71\u52a8\u3002\u4e0d\u9690\u85cf residual\uff1b\u4e0d\u628a standardized total \u8bef\u8bfb\u4e3a formal total\u3002")
$allRoles += New-Role `
  -Slug "risk-manager" `
  -Title "Risk Manager" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "\u98ce\u9669\u7ba1\u7406\u4e13\u5bb6") `
  -Mission (ConvertFrom-UnicodeEscape "\u4e13\u6ce8 DV01/KRD/CS01\u3001\u4e45\u671f\u3001\u51f8\u6027\u3001\u96c6\u4e2d\u5ea6\u3001\u6d41\u52a8\u6027\u7f3a\u53e3\u3001\u98ce\u9669\u8d28\u91cf\u6807\u8bb0\u548c risk tensor \u9875\u7684\u53e3\u5f84\u5ba1\u6838\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u4e0d\u524d\u7aef\u5408\u6210 regulatory_dv01 \u6216\u65e0\u8bc1\u636e\u4e45\u671f\u3002\u5fc5\u987b\u663e\u793a\u6392\u9664\u884c\u6570\u3001\u5206\u6bcd\u3001quality_flag \u548c\u4f30\u7b97/\u7f3a\u5931\u8bc1\u636e\u3002")
$allRoles += New-Role `
  -Slug "fixed-income-analyst" `
  -Title "Fixed Income Analyst" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "\u56fa\u6536/\u503a\u5238\u5206\u6790\u5e08") `
  -Mission (ConvertFrom-UnicodeEscape "\u4e13\u6ce8\u503a\u5238\u6301\u4ed3\u3001\u6536\u76ca\u7387\u66f2\u7ebf\u3001\u4e45\u671f\u3001\u51f8\u6027\u3001spread\u3001clean/dirty price\u3001coupon/accrual \u548c\u503a\u5238\u603b\u89c8\u9875\u53e3\u5f84\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u5fc5\u987b\u5148\u9501\u5b9a\u4f30\u503c\u65e5\u3001\u5e01\u79cd\u3001day count\u3001compounding\u3001curve \u548c\u672c\u5730\u5b57\u6bb5\u7ea6\u5b9a\u3002\u4e0d\u628a bond dashboard headline \u81ea\u52a8\u7b49\u540c risk tensor/balance formal truth\u3002")
$allRoles += New-Role `
  -Slug "market-data-specialist" `
  -Title "Market Data Specialist" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "\u5e02\u573a\u6570\u636e\u4e13\u5458") `
  -Mission (ConvertFrom-UnicodeEscape "\u4e13\u6ce8\u5229\u7387\u3001\u66f2\u7ebf\u3001FX\u3001\u4ef7\u683c\u3001vendor/preview/source-pending \u5206\u5c42\u3001\u6570\u636e\u65f6\u6548\u3001stale/fallback \u548c market-data \u9875\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u4e0d\u628a macro/FX/Livermore/vendor preview \u6df7\u6210 formal market truth\u3002\u5fc5\u987b\u663e\u793a source\u3001version\u3001as_of/date\u3001fallback/stale \u72b6\u6001\u3002")
$allRoles += New-Role `
  -Slug "valuation-accounting-reconciler" `
  -Title "Valuation Accounting Reconciler" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "\u4f30\u503c/\u4f1a\u8ba1\u5bf9\u8d26\u4e13\u5bb6") `
  -Mission (ConvertFrom-UnicodeEscape "\u4e13\u6ce8\u4f30\u503c\u3001\u8d26\u52a1\u62bd\u53d6\u3001ledger\u3001514/516/517/manual/total_pnl\u3001\u8d26\u8868\u5bf9\u8d26\u3001\u7b26\u53f7\u548c\u5355\u4f4d\u4e00\u81f4\u6027\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u5bf9\u8d26\u4e0d\u5e73\u65f6\u4f18\u5148\u62a5\u544a\u5dee\u5f02\u3001\u7c92\u5ea6\u3001\u671f\u95f4\u3001\u5e01\u79cd\u3001\u7b26\u53f7\u548c\u6765\u6e90\u3002\u4e0d\u5728\u524d\u7aef\u91cd\u505a\u6b63\u5f0f\u4f1a\u8ba1/PnL \u903b\u8f91\u3002")
$allRoles += New-Role `
  -Slug "ui-ux-page-closer" `
  -Title "UI UX Page Closer" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "UI/UX\u9875\u9762\u6536\u53e3\u5e08") `
  -Mission (ConvertFrom-UnicodeEscape "\u628a\u76ee\u6807\u9875\u9762\u6536\u53e3\u5230\u9996\u5c4f\u95ee\u9898\u6e05\u695a\u3001\u4e3b\u7ed3\u8bba\u660e\u663e\u3001\u65e0\u6570\u636e/stale/fallback/loading/definition pending \u72b6\u6001\u53ef\u89c1\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u4e0d\u505a\u8425\u9500\u5f0f\u82f1\u96c4\u9875\u6216\u65e0\u5173\u89c6\u89c9\u7ffb\u65b0\u3002\u4e0d\u5728\u524d\u7aef\u65b0\u9020\u6b63\u5f0f\u6307\u6807\uff1b\u4e0d\u6539\u5168\u5c40\u8bbe\u8ba1\u7cfb\u7edf\uff0c\u9664\u975e Leader \u660e\u786e\u6307\u6d3e\u3002")
$allRoles += New-Role `
  -Slug "docs-delivery-manager" `
  -Title "Docs Delivery Manager" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "\u6587\u6863\u4ea4\u4ed8\u5b98") `
  -Mission (ConvertFrom-UnicodeEscape "\u7ef4\u62a4\u4ea4\u4ed8\u6587\u6863\u3001runbook\u3001\u9a8c\u6536\u6e05\u5355\u3001\u51b3\u7b56\u8bb0\u5f55\u548c\u591a\u89d2\u8272\u6700\u7ec8\u6c47\u603b\uff0c\u8ba9\u4efb\u52a1\u53ef\u8ffd\u6eaf\u3001\u53ef\u590d\u73b0\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u4e0d\u7f16\u9020\u8bc1\u636e\u3001\u4e0d\u66ff\u4e1a\u52a1\u65b9\u6279\u51c6\u6307\u6807\u3002\u6587\u6863\u66f4\u65b0\u5fc5\u987b\u5f15\u7528\u5df2\u8bfb\u6587\u4ef6\u3001\u547d\u4ee4\u8f93\u51fa\u6216\u5404\u89d2\u8272 outbox \u8bc1\u636e\u3002")
$allRoles += New-Role `
  -Slug "code-reviewer" `
  -Title "Code Reviewer" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "\u4ee3\u7801\u5ba1\u67e5\u5458") `
  -Mission (ConvertFrom-UnicodeEscape "\u5ba1\u67e5\u8ba1\u5212\u6216\u5df2\u5b8c\u6210\u4fee\u6539\uff0c\u91cd\u70b9\u627e\u7f3a\u9677\u3001\u56de\u5f52\u3001\u7f3a\u5931\u6d4b\u8bd5\u3001\u8303\u56f4\u8513\u5ef6\u548c\u5951\u7ea6\u8fdd\u89c4\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u9ed8\u8ba4\u53ea\u8f93\u51fa\u5ba1\u67e5\u53d1\u73b0\uff0c\u4e0d\u76f4\u63a5\u5b9e\u73b0\u3002\u82e5\u88ab\u8981\u6c42\u4fee\u590d\uff0c\u4fdd\u6301\u6539\u52a8\u7cbe\u786e\uff0c\u5e76\u8bf4\u660e\u5177\u4f53\u98ce\u9669\u3002")
$allRoles += New-Role `
  -Slug "qa" `
  -Title "QA" `
  -DisplayTitle (ConvertFrom-UnicodeEscape "\u6d4b\u8bd5/QA") `
  -Mission (ConvertFrom-UnicodeEscape "\u5b9a\u4e49\u5e76\u6267\u884c\u6700\u5c0f\u4f46\u6709\u6548\u7684\u9a8c\u8bc1\u8def\u5f84\uff0c\u7136\u540e\u62a5\u544a\u901a\u8fc7/\u5931\u8d25\u8bc1\u636e\u3002") `
  -Boundaries (ConvertFrom-UnicodeEscape "\u4e0d\u8981\u65e0\u6545\u6269\u5927\u6d4b\u8bd5\u8303\u56f4\u3002\u4f18\u5148\u8dd1\u76ee\u6807\u6d4b\u8bd5\uff0c\u518d\u6309\u9700\u8981\u8dd1 lint\u3001\u7c7b\u578b\u68c0\u67e5\u3001\u6784\u5efa\u6216\u6d4f\u89c8\u5668\u68c0\u67e5\u3002")

$selectedRoles = @(Select-Roles -AllRoles $allRoles -RequestedRoles $Roles)
$selectedRoleSlugs = @{}
foreach ($role in $selectedRoles) {
  $selectedRoleSlugs[$role.Slug] = $true
}

$boardPath = Join-Path $teamDir "TEAM_BOARD.md"
$backendRoot = if ($Backend -eq "Wsl") { ConvertTo-WslPath -Path $root } else { $root }
$backendTeamDir = if ($Backend -eq "Wsl") { ConvertTo-WslPath -Path $teamDir } else { $teamDir }
$backendBoardPath = if ($Backend -eq "Wsl") { ConvertTo-WslPath -Path $boardPath } else { $boardPath }
$taskText = if ([string]::IsNullOrWhiteSpace($Task)) { "No task supplied yet. Ask Leader to write the concrete objective." } else { $Task }
$createdAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$roleRows = ($allRoles | ForEach-Object {
  "| $($_.Title) | prompts/$($_.Slug).md | inbox/$($_.Slug).md | outbox/$($_.Slug).md | pending | |"
}) -join [Environment]::NewLine
$workspaceRows = ($allRoles | ForEach-Object {
  "| $($_.Title) | workspaces/$($_.Slug) |"
}) -join [Environment]::NewLine

$board = @"
# Hermes Agent Team Board

Team: $resolvedTeamId
Created: $createdAt
Workspace: $root
Backend: $Backend
Backend workspace: $backendRoot

## Objective

$taskText

## Operating Rule

Leader coordinates. Each role writes only its own outbox unless explicitly assigned a code lane. Use AGENTS.md and subtree instructions as authority.

## Role Status

| Role | Prompt | Inbox | Outbox | Status | Notes |
| --- | --- | --- | --- | --- | --- |
$roleRows

## Role Workspaces

| Role | Independent workspace |
| --- | --- |
$workspaceRows

## Assignments

- Leader: split the objective into lanes, then monitor outboxes.
- Product Manager: define success criteria and ambiguity.
- Frontend Developer: own frontend page/component/adapter lanes and browser-facing verification.
- Developer: wait for assigned backend/API/general implementation lane.
- Backend API Contract Engineer: own API/result_meta/route contract lanes.
- Metric Caliber Officer: verify metric definitions, units, dates, and formal/candidate/excluded status.
- Data Lineage Auditor: trace source lineage, fallback/stale evidence, and page data flow.
- Security Permission Auditor: review permission boundaries, script runners, write routes, and audit evidence.
- Asset Liability Manager: verify balance analysis, net positions, currency/date basis, and ALM business conclusions.
- PnL Attribution Analyst: reconcile PnL totals, bridge components, residuals, and product/category PnL explanations.
- Risk Manager: verify risk tensor metrics, exclusions, denominators, and risk quality flags.
- Fixed Income Analyst: verify bond analytics, curves, duration, convexity, spreads, and fixed-income conventions.
- Market Data Specialist: verify market-data freshness, source/version boundaries, rates, curves, prices, and FX.
- Valuation Accounting Reconciler: reconcile valuation/accounting extracts, ledger paths, signs, and formal PnL sources.
- UI UX Page Closer: close page-level user-facing states and first-screen business clarity.
- Docs Delivery Manager: maintain runbooks, handoff notes, acceptance checklists, and final synthesis.
- Code Reviewer: review plans or diffs once available.
- QA: propose and run verification after implementation.

## Decisions

- Pending.

## Verification Evidence

- Pending.

## Final Synthesis

- Pending.
"@
Write-Utf8File -Path $boardPath -Value $board

foreach ($role in $allRoles) {
  $promptPath = Join-Path $promptDir "$($role.Slug).md"
  $inboxPath = Join-Path $inboxDir "$($role.Slug).md"
  $outboxPath = Join-Path $outboxDir "$($role.Slug).md"
  $launcherPath = Join-Path $launchDir "$($role.Slug).ps1"
  $roleWorkspacePath = Join-Path $workspaceDir $role.Slug
  New-Item -ItemType Directory -Force -Path $roleWorkspacePath | Out-Null
  $sessionTitle = "$resolvedTeamId/$($role.Slug)"
  $backendRoleWorkspacePath = if ($Backend -eq "Wsl") { ConvertTo-WslPath -Path $roleWorkspacePath } else { $roleWorkspacePath }
  $backendPromptPath = if ($Backend -eq "Wsl") { ConvertTo-WslPath -Path $promptPath } else { $promptPath }
  $backendInboxPath = if ($Backend -eq "Wsl") { ConvertTo-WslPath -Path $inboxPath } else { $inboxPath }
  $backendOutboxPath = if ($Backend -eq "Wsl") { ConvertTo-WslPath -Path $outboxPath } else { $outboxPath }
  $backendSessionFile = if ($Backend -eq "Wsl") { ConvertTo-WslPath -Path (Join-Path $sessionDir "$($role.Slug).txt") } else { Join-Path $sessionDir "$($role.Slug).txt" }

  $prompt = New-RolePrompt `
    -Role $role `
    -ProjectWorkspacePath $root `
    -BoardPath $boardPath `
    -InboxPath $inboxPath `
    -OutboxPath $outboxPath `
    -RoleWorkspacePath $roleWorkspacePath `
    -BackendProjectWorkspacePath $backendRoot `
    -BackendBoardPath $backendBoardPath `
    -BackendInboxPath $backendInboxPath `
    -BackendOutboxPath $backendOutboxPath `
    -BackendRoleWorkspacePath $backendRoleWorkspacePath `
    -TaskText $taskText `
    -TeamName $resolvedTeamId

  Write-Utf8File -Path $promptPath -Value $prompt

  if (-not (Test-Path -LiteralPath $inboxPath)) {
    Write-Utf8File -Path $inboxPath -Value "# Inbox: $($role.Title)`n`nNo messages yet.`n"
  }
  if (-not (Test-Path -LiteralPath $outboxPath)) {
    Write-Utf8File -Path $outboxPath -Value "# Outbox: $($role.Title)`n`nNo report yet.`n"
  }

  $sessionFile = Join-Path $sessionDir "$($role.Slug).txt"
  $modelArg = if ([string]::IsNullOrWhiteSpace($Model)) { "" } else { "  Model = $(Quote-PowerShellLiteral $Model)`n" }
  $providerArg = if ([string]::IsNullOrWhiteSpace($Provider)) { "" } else { "  Provider = $(Quote-PowerShellLiteral $Provider)`n" }
  $toolsetsArg = if ([string]::IsNullOrWhiteSpace($Toolsets)) { "" } else { "  Toolsets = $(Quote-PowerShellLiteral $Toolsets)`n" }
  $skillsArg = if ([string]::IsNullOrWhiteSpace($Skills)) { "" } else { "  Skills = $(Quote-PowerShellLiteral $Skills)`n" }
  $wslCommandArg = if ($Backend -eq "Wsl") { "  WslCommand = $(Quote-PowerShellLiteral $WslCommand)`n" } else { "" }
  $yoloArg = if ($Yolo) { "  Yolo = `$true`n" } else { "" }
$launcher = @"
param([string]`$AutoTaskId = "", [string]`$TaskClaimToken = "")
`$ErrorActionPreference = "Stop"
`[Console`]::InputEncoding = `[System.Text.Encoding`]::UTF8
`[Console`]::OutputEncoding = `[System.Text.Encoding`]::UTF8
`$env:PYTHONIOENCODING = "utf-8"
`$env:PYTHONUTF8 = "1"
`$runnerArgs = @{
  Backend = $(Quote-PowerShellLiteral $Backend)
  WslDistro = $(Quote-PowerShellLiteral $WslDistro)
  Workspace = $(Quote-PowerShellLiteral $roleWorkspacePath)
  BackendWorkspace = $(Quote-PowerShellLiteral $backendRoleWorkspacePath)
  RoleTitle = $(Quote-PowerShellLiteral $role.Title)
  PromptPath = $(Quote-PowerShellLiteral $promptPath)
  BackendPromptPath = $(Quote-PowerShellLiteral $backendPromptPath)
  SessionFile = $(Quote-PowerShellLiteral $sessionFile)
  SessionTitle = $(Quote-PowerShellLiteral $sessionTitle)
  AutoTaskId = `$AutoTaskId
  TaskClaimToken = `$TaskClaimToken
  DispatchUrl = $(Quote-PowerShellLiteral $dispatchUrl)
  DispatchToken = $(Quote-PowerShellLiteral $dispatchToken)
  MaxTurns = $MaxTurns
  HermesCommand = $(Quote-PowerShellLiteral $HermesCommand)
$modelArg$providerArg$toolsetsArg$skillsArg$wslCommandArg$yoloArg}
& $(Quote-PowerShellLiteral $roleRunnerPath) @runnerArgs
"@
  Write-Utf8File -Path $launcherPath -Value $launcher

  if ($SeedSessions -and $selectedRoleSlugs.ContainsKey($role.Slug)) {
    $sessionId = Invoke-RoleSeed -PromptPath $promptPath -SessionTitle $sessionTitle -PromptPathForBackend $backendPromptPath
    if (-not [string]::IsNullOrWhiteSpace($sessionId)) {
      Write-Utf8File -Path (Join-Path $sessionDir "$($role.Slug).txt") -Value $sessionId
    }
  }
}

$dashboardPath = Join-Path $teamDir "dashboard.html"
$dashboardHtml = New-DashboardHtml `
  -AllRoles $allRoles `
  -SelectedRoles $selectedRoles `
  -TeamName $resolvedTeamId `
  -TaskText $taskText `
  -Workspace $root `
  -Backend $Backend `
  -BoardPath $boardPath `
  -PromptDir $promptDir `
  -InboxDir $inboxDir `
  -OutboxDir $outboxDir `
  -SessionDir $sessionDir `
  -LaunchDir $launchDir `
  -CreatedAt $createdAt
Write-Utf8File -Path $dashboardPath -Value $dashboardHtml

$manifest = [pscustomobject]@{
  team_id = $resolvedTeamId
  task = $taskText
  workspace = $root
  team_dir = $teamDir
  board = $boardPath
  dashboard = $dashboardPath
  queue = $queuePath
  dispatch_url = $dispatchUrl
  dispatch_token = $dispatchToken
  layout = $Layout
  selected_roles = @($selectedRoles | ForEach-Object { $_.Slug })
  roles = $allRoles | ForEach-Object {
    [pscustomobject]@{
      slug = $_.Slug
      title = $_.Title
      display_title = $_.DisplayTitle
      prompt = Join-Path $promptDir "$($_.Slug).md"
      inbox = Join-Path $inboxDir "$($_.Slug).md"
      outbox = Join-Path $outboxDir "$($_.Slug).md"
      workspace = Join-Path $workspaceDir $_.Slug
      backend_workspace = if ($Backend -eq "Wsl") { ConvertTo-WslPath -Path (Join-Path $workspaceDir $_.Slug) } else { Join-Path $workspaceDir $_.Slug }
      launcher = Join-Path $launchDir "$($_.Slug).ps1"
      session_title = "$resolvedTeamId/$($_.Slug)"
    }
  }
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $teamDir "manifest.json") -Encoding UTF8

Write-Host "Hermes agent team prepared: $teamDir" -ForegroundColor Cyan
Write-Host "Team board: $boardPath" -ForegroundColor DarkGray
Write-Host "Dashboard: $dashboardPath" -ForegroundColor DarkGray
Write-Host "Roles: Leader, Product Manager, Frontend Developer, Developer, Backend API Contract Engineer, Metric Caliber Officer, Data Lineage Auditor, Security Permission Auditor, Asset Liability Manager, PnL Attribution Analyst, Risk Manager, Fixed Income Analyst, Market Data Specialist, Valuation Accounting Reconciler, UI UX Page Closer, Docs Delivery Manager, Code Reviewer, QA" -ForegroundColor DarkGray

if ($PrepareOnly -and -not $Launch) {
  Write-Host "Run with -Launch to open the team windows." -ForegroundColor Cyan
  exit 0
}

if (-not $Launch) {
  Write-Host "Prepared only. Pass -Launch to open Hermes terminals." -ForegroundColor Cyan
  exit 0
}

$wt = Get-Command wt -ErrorAction SilentlyContinue
if (-not $wt) {
  throw "Windows Terminal (wt.exe) was not found. Run individual launch scripts under $launchDir."
}

if ($Layout -eq "Windows") {
  foreach ($role in $selectedRoles) {
    $launcherPath = Join-Path $launchDir "$($role.Slug).ps1"
    Start-Process -FilePath $wt.Source -ArgumentList @(
      "new-tab",
      "--title",
      "Hermes $($role.Title)",
      "powershell",
      "-NoExit",
      "-ExecutionPolicy",
      "Bypass",
      "-File",
      $launcherPath
    )
  }
} else {
  $firstRole = $selectedRoles[0]
  $args = @(
    "new-tab",
    "--title",
    "Hermes $($firstRole.Title)",
    "powershell",
    "-NoExit",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    (Join-Path $launchDir "$($firstRole.Slug).ps1")
  )

  foreach ($role in ($selectedRoles | Where-Object { $_.Slug -ne $firstRole.Slug })) {
    $args += @(
      ";",
      "split-pane",
      "--title",
      "Hermes $($role.Title)",
      "powershell",
      "-NoExit",
      "-ExecutionPolicy",
      "Bypass",
      "-File",
      (Join-Path $launchDir "$($role.Slug).ps1")
    )
  }

  Start-Process -FilePath $wt.Source -ArgumentList $args
}

Write-Host "Hermes team windows launched." -ForegroundColor Cyan
