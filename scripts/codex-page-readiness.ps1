param(
  [string]$PageSlug = "product-category-pnl",

  [switch]$All,
  [switch]$Run,
  [switch]$CheckLive,
  [switch]$RequireApprovalCaptured
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$pythonScript = Join-Path $root "scripts\codex_page_readiness.py"
$smokeScript = Join-Path $root "scripts\codex-page-smoke.ps1"
$verifyScript = Join-Path $root "scripts\codex-verify-page.ps1"

Set-Location $root

function Write-PageReadinessReport {
  param(
    [object]$Report
  )

  Write-Output "Page: $($Report.page_id) $($Report.page_name)"
  Write-Output "Route: $($Report.route)"
  Write-Output "Primary API: $($Report.primary_api)"
  Write-Output "Approval: $($Report.approval_status); formal_use_allowed=$($Report.formal_use_allowed)"

  Write-Output "Static evidence gates:"
  foreach ($gate in $Report.static_gates) {
    Write-Output "- $($gate.name): $($gate.outcome) ($($gate.detail))"
  }

  if ($Report.blocking_gates.Count -gt 0) {
    Write-Output "Blocking gates:"
    foreach ($gateName in $Report.blocking_gates) {
      Write-Output "- $gateName"
    }
    throw "Static page readiness gates blocked."
  }

  Write-Output "Residual gaps surfaced:"
  foreach ($gap in $Report.residual_gaps) {
    Write-Output "- $gap"
  }

  if ($Report.required_commands.Count -gt 0) {
    Write-Output "Required closure commands:"
    foreach ($command in $Report.required_commands) {
      Write-Output "- $command"
    }
  } else {
    Write-Output "Required closure commands: static-only; local smoke/verify helpers are not wired for this page yet."
  }

  if ($null -ne $Report.approval_status_commands -and $Report.approval_status_commands.Count -gt 0) {
    Write-Output "Approval status commands:"
    foreach ($command in $Report.approval_status_commands) {
      Write-Output "- $command"
    }
  }

  if (
    $null -ne $Report.business_owner_approval_status -and
    $null -ne $Report.business_owner_approval_status.remaining_blockers -and
    $Report.business_owner_approval_status.remaining_blockers.Count -gt 0
  ) {
    Write-Output "Approval status blockers:"
    foreach ($blocker in $Report.business_owner_approval_status.remaining_blockers) {
      Write-Output "- $blocker"
    }
  }
  Write-ApprovalEvidenceScope -EvidenceScope $Report.business_owner_approval_status.evidence_scope
  if (
    $null -ne $Report.business_owner_approval_status -and
    $null -ne $Report.business_owner_approval_status.approval_action_items -and
    $Report.business_owner_approval_status.approval_action_items.Count -gt 0
  ) {
    Write-Output "Approval action item count: $($Report.business_owner_approval_status.approval_action_item_count)"
    Write-Output "Approval action items:"
    foreach ($item in $Report.business_owner_approval_status.approval_action_items) {
      Write-Output (Format-ApprovalActionItem -Item $item)
    }
  }

  Write-Output "Boundary: $($Report.boundary)"
}

function Invoke-PageReadinessChecks {
  param(
    [string]$Slug
  )

  $smokeArgs = @("-PageSlug", $Slug)
  if ($CheckLive) {
    $smokeArgs += "-CheckLive"
  }

  & powershell -NoProfile -ExecutionPolicy Bypass -File $smokeScript @smokeArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Page smoke checklist failed for $Slug."
  }

  & powershell -NoProfile -ExecutionPolicy Bypass -File $verifyScript -PageSlug $Slug -Run
  if ($LASTEXITCODE -ne 0) {
    throw "Page verification checks failed for $Slug."
  }
}

function Format-ApprovalActionItem {
  param(
    [object]$Item,
    [string]$Prefix = "- "
  )

  $templateField = "$($Item.template_field)".TrimStart("-").Trim()
  return "$Prefix$($templateField): $($Item.required_value) ($($Item.current_status))"
}

function Write-ApprovalEvidenceScope {
  param(
    [object]$EvidenceScope,
    [string]$Prefix = "- "
  )

  if ($null -eq $EvidenceScope) {
    return
  }

  Write-Output "Approval evidence scope:"
  foreach ($field in @("approves_metric_or_page", "writes_governance_records", "proves_page_execution", "captures_business_owner_approval")) {
    if ($EvidenceScope.PSObject.Properties.Name -contains $field) {
      Write-Output "$Prefix$field=$($EvidenceScope.$field)"
    }
  }
}

function Assert-ApprovalCaptured {
  param(
    [object]$Report,
    [switch]$ActionItemsAlreadyShown
  )

  if (-not $RequireApprovalCaptured) {
    return
  }

  if (
    $null -ne $Report.business_owner_approval_status -and
    $Report.business_owner_approval_status.business_owner_approval_captured
  ) {
    return
  }

  Write-Output "Approval capture is required but not complete."
  if (
    $null -ne $Report.business_owner_approval_status -and
    $null -ne $Report.business_owner_approval_status.remaining_blockers
  ) {
    foreach ($blocker in $Report.business_owner_approval_status.remaining_blockers) {
      Write-Output "- $blocker"
    }
  }
  if (-not $ActionItemsAlreadyShown) {
    Write-ApprovalEvidenceScope -EvidenceScope $Report.business_owner_approval_status.evidence_scope
  }
  if (
    -not $ActionItemsAlreadyShown -and
    $null -ne $Report.business_owner_approval_status -and
    $null -ne $Report.business_owner_approval_status.approval_action_items -and
    $Report.business_owner_approval_status.approval_action_items.Count -gt 0
  ) {
    Write-Output "Approval action items:"
    foreach ($item in $Report.business_owner_approval_status.approval_action_items) {
      Write-Output (Format-ApprovalActionItem -Item $item)
    }
  }
  throw "Business-owner approval capture is required."
}

function Assert-AllApprovalCaptured {
  param(
    [object]$Report
  )

  if (-not $RequireApprovalCaptured) {
    return
  }

  $pendingPages = @()
  foreach ($page in $Report.pages) {
    if (
      $null -ne $page.business_owner_approval_status -and
      -not $page.business_owner_approval_status.business_owner_approval_captured
    ) {
      $pendingPages += $page
    }
  }

  if ($pendingPages.Count -eq 0) {
    return
  }

  Write-Output "Approval capture is required but not complete."
  foreach ($page in $pendingPages) {
    Write-Output "- $($page.page_slug) ($($page.page_id))"
    if ($null -ne $page.business_owner_approval_status.remaining_blockers) {
      foreach ($blocker in $page.business_owner_approval_status.remaining_blockers) {
        Write-Output "  - $blocker"
      }
    }
    Write-ApprovalEvidenceScope -EvidenceScope $page.business_owner_approval_status.evidence_scope -Prefix "  - "
    if (
      $null -ne $page.business_owner_approval_status.approval_action_items -and
      $page.business_owner_approval_status.approval_action_items.Count -gt 0
    ) {
      Write-Output "Approval action items:"
      foreach ($item in $page.business_owner_approval_status.approval_action_items) {
        Write-Output (Format-ApprovalActionItem -Item $item -Prefix "  - ")
      }
    }
  }
  throw "Business-owner approval capture is required."
}

if ($All) {
  Write-Output "MOSS page readiness gate: all seeded pages"

  $json = & python $pythonScript --all
  if ($LASTEXITCODE -ne 0) {
    throw "Static page readiness evaluation failed for all seeded pages."
  }

  $report = $json | ConvertFrom-Json
  Assert-AllApprovalCaptured -Report $report
  Write-Output "Summary: page_count=$($report.summary.page_count); static_pass_count=$($report.summary.static_pass_count); blocked_count=$($report.summary.blocked_count); formal_or_governed_count=$($report.summary.formal_or_governed_count); mixed_or_candidate_count=$($report.summary.mixed_or_candidate_count); run_supported_count=$($report.summary.run_supported_count); business_owner_approval_pending_count=$($report.summary.business_owner_approval_pending_count); business_owner_approval_action_item_count=$($report.summary.business_owner_approval_action_item_count)"
  Write-Output "Page readiness rows:"
  foreach ($page in $report.pages) {
    $goldenGate = $page.static_gates | Where-Object { $_.name -eq "golden_sample_boundary" } | Select-Object -First 1
    Write-Output "- $($page.page_slug): $($page.overall_status); approval=$($page.approval_status); golden=$($goldenGate.detail); run_supported=$($page.run_supported)"
  }
  if (
    $null -ne $report.business_owner_approval_pending_pages -and
    $report.business_owner_approval_pending_pages.Count -gt 0
  ) {
    Write-Output "Business-owner approval pending pages:"
    foreach ($page in $report.business_owner_approval_pending_pages) {
      Write-Output "- $($page.page_slug) ($($page.page_id)): $($page.approval_status); captured=$($page.business_owner_approval_captured); action_items=$($page.approval_action_item_count)"
      Write-ApprovalEvidenceScope -EvidenceScope $page.evidence_scope -Prefix "  - "
      if (
        $null -ne $page.approval_action_items -and
        $page.approval_action_items.Count -gt 0
      ) {
        Write-Output "Approval action items:"
        foreach ($item in $page.approval_action_items) {
          Write-Output (Format-ApprovalActionItem -Item $item -Prefix "  - ")
        }
      }
    }
  }
  if (
    $null -ne $report.approval_status_commands -and
    $report.approval_status_commands.Count -gt 0
  ) {
    Write-Output "Approval status commands:"
    foreach ($command in $report.approval_status_commands) {
      Write-Output "- $command"
    }
  }
  Write-Output "Boundary: $($report.boundary)"

  $hasBlockingPages = $report.blocking_pages.Count -gt 0
  if ($hasBlockingPages) {
    Write-Output "Blocking pages:"
    foreach ($slug in $report.blocking_pages) {
      Write-Output "- $slug"
    }
  }

  if (-not $Run) {
    Write-Output "Batch dry run complete. Pass -Run to execute page checks for supported pages."
    exit 0
  }

  if ($hasBlockingPages) {
    throw "Static page readiness gates blocked."
  }

  foreach ($page in $report.pages) {
    if (-not $page.run_supported) {
      Write-Output "Skipping page checks for $($page.page_slug): local smoke/verify helpers are not wired yet."
      continue
    }
    Invoke-PageReadinessChecks -Slug $page.page_slug
  }

  Write-Output "Page readiness gate passed."
  exit 0
}

Write-Output "MOSS page readiness gate: $PageSlug"

$json = & python $pythonScript --page-slug $PageSlug
if ($LASTEXITCODE -ne 0) {
  throw "Static page readiness evaluation failed for $PageSlug."
}

$report = $json | ConvertFrom-Json

Write-PageReadinessReport -Report $report
Assert-ApprovalCaptured -Report $report -ActionItemsAlreadyShown

if (-not $Run) {
  Write-Output "Dry run complete. Pass -Run to execute page checks."
  exit 0
}

if (-not $report.run_supported) {
  throw "Local smoke/verify helpers are not wired for $PageSlug. Static readiness report is available, but -Run is not supported yet."
}

Invoke-PageReadinessChecks -Slug $PageSlug
Write-Output "Page readiness gate passed."
