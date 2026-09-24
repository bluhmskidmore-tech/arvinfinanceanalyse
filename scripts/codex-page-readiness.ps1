param(
  [string]$PageSlug = "product-category-pnl",

  [switch]$All,
  [switch]$RouteScope,
  [switch]$Run,
  [switch]$CheckLive,
  [switch]$RequireApprovalCaptured
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$pythonScript = Join-Path $root "scripts\codex_page_readiness.py"
$smokeScript = Join-Path $root "scripts\codex-page-smoke.ps1"
$verifyScript = Join-Path $root "scripts\codex-verify-page.ps1"
. "$root\scripts\codex-python-helper.ps1"

Set-Location $root
$pythonExe = Resolve-CodexPython

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
  }

  Write-Output "Residual gaps surfaced:"
  foreach ($gap in $Report.residual_gaps) {
    Write-Output "- $gap"
  }
  if ($Report.page_slug -in @("pnl", "pnl-bridge")) {
    Write-Output "- full data-catalog/date review required before page-level closure."
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
  Write-CertificationPacketConsistency -Consistency $Report.certification_packet_consistency
  Write-BusinessOwnerActionSignoffSummary -Summary $Report.business_owner_approval_status.business_owner_action_signoff_summary
  Write-OwnerPreSignatureBlockerScope -Scope $Report.business_owner_approval_status.owner_pre_signature_blocker_scope
  Write-GeneratedArtifactFreshnessScope -Scope $Report.business_owner_approval_status.generated_artifact_freshness_scope
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
  foreach ($field in @("approves_metric_or_page", "writes_governance_records", "proves_page_execution", "captures_business_owner_approval", "certification_effect")) {
    if ($EvidenceScope.PSObject.Properties.Name -contains $field) {
      Write-Output "$Prefix$field=$($EvidenceScope.$field)"
    }
  }
}

function Write-CertificationPacketConsistency {
  param(
    [object]$Consistency,
    [string]$Prefix = "- "
  )

  if ($null -eq $Consistency) {
    return
  }

  $missingMarkerCount = 0
  if ($null -ne $Consistency.missing_markers) {
    $missingMarkerCount = $Consistency.missing_markers.Count
  }

  Write-Output "Certification packet consistency:"
  Write-Output "${Prefix}status=$($Consistency.status)"
  Write-Output "${Prefix}missing_marker_count=$missingMarkerCount"
  foreach ($field in @("formal_decision_item_count", "next_review_queue_item_count", "approval_action_item_count", "business_owner_action_signoff_item_count", "business_owner_action_signed_item_count", "business_owner_action_pending_or_missing_item_count", "owner_signable", "can_promote_certification", "approves_metric_or_page", "captures_business_owner_approval", "captures_business_owner_signature", "captures_product_or_api_decisions", "captures_golden_sample_approval", "captures_closure_approval", "writes_governance_records", "verification_commands_rerun_captured", "certification_effect")) {
    if ($Consistency.PSObject.Properties.Name -contains $field) {
      Write-Output "${Prefix}${field}=$($Consistency.$field)"
    }
  }
  Write-Output "$($Prefix)boundary=consistency only; does not capture approval or certify route"
}

function Write-GroupCounts {
  param(
    [object]$GroupCounts,
    [string]$Label,
    [string]$Prefix = "- "
  )

  $properties = @()
  if ($null -ne $GroupCounts) {
    $properties = @($GroupCounts.PSObject.Properties | Sort-Object Name)
  }

  if ($properties.Count -eq 0) {
    Write-Output "${Prefix}${Label}.none=0"
    return
  }

  foreach ($property in $properties) {
    Write-Output "${Prefix}${Label}.$($property.Name)=$($property.Value)"
  }
}

function Get-OwnerActionStatusCount {
  param(
    [object]$Summary,
    [string]$CanonicalField,
    [string]$LegacyField
  )

  if ($null -eq $Summary) {
    return $null
  }

  if ($Summary.PSObject.Properties.Name -contains $CanonicalField) {
    return $Summary.PSObject.Properties[$CanonicalField].Value
  }
  if ($Summary.PSObject.Properties.Name -contains $LegacyField) {
    return $Summary.PSObject.Properties[$LegacyField].Value
  }
  return $null
}

function Write-BusinessOwnerActionSignoffSummary {
  param(
    [object]$Summary,
    [string]$Prefix = "- "
  )

  if ($null -eq $Summary) {
    return
  }

  Write-Output "Business owner action signoff summary:"
  foreach ($field in @("action_item_count", "signed_item_count", "unsigned_item_count", "owner_signable", "captures_business_owner_approval", "can_promote_certification", "certification_blocked")) {
    if ($Summary.PSObject.Properties.Name -contains $field) {
      Write-Output "${Prefix}${field}=$($Summary.$field)"
    }
  }
  $missingOrInvalidCount = Get-OwnerActionStatusCount -Summary $Summary -CanonicalField "missing_or_invalid_item_count" -LegacyField "invalid_or_missing_item_count"
  if ($null -ne $missingOrInvalidCount) {
    Write-Output "${Prefix}missing_or_invalid_item_count=$missingOrInvalidCount"
  }
  $pendingReviewCount = Get-OwnerActionStatusCount -Summary $Summary -CanonicalField "pending_review_item_count" -LegacyField "pending_item_count"
  if ($null -ne $pendingReviewCount) {
    Write-Output "${Prefix}pending_review_item_count=$pendingReviewCount"
  }
  $signoffGroupCounts = $Summary.signoff_group_counts
  $signedGroupCounts = $Summary.signed_group_counts
  $unsignedGroupCounts = $Summary.unsigned_group_counts
  Write-GroupCounts -GroupCounts $signoffGroupCounts -Label "signoff_group_counts" -Prefix $Prefix
  Write-GroupCounts -GroupCounts $signedGroupCounts -Label "signed_group_counts" -Prefix $Prefix
  Write-GroupCounts -GroupCounts $unsignedGroupCounts -Label "pending_or_missing_group_counts" -Prefix $Prefix
  Write-Output "$($Prefix)boundary=signoff summary only; unsigned groups still block approval capture"
}

function Write-OwnerPreSignatureBlockerScope {
  param(
    [object]$Scope,
    [string]$Prefix = "- "
  )

  if (
    $null -eq $Scope -or
    $Scope.PSObject.Properties.Name -notcontains "remaining_blocker_count"
  ) {
    return
  }

  Write-Output "Owner pre-signature blocker scope:"
  foreach ($field in @("remaining_blocker_count", "approval_action_item_count", "signed_item_count", "unsigned_item_count", "missing_or_invalid_item_count", "pending_review_item_count", "owner_signable", "captures_business_owner_approval", "captures_product_or_api_decisions", "can_promote_certification", "certification_effect")) {
    if ($Scope.PSObject.Properties.Name -contains $field) {
      Write-Output "${Prefix}${field}=$($Scope.$field)"
    }
  }
  Write-GroupCounts -GroupCounts $Scope.signoff_group_counts -Label "signoff_group_counts" -Prefix $Prefix
  Write-GroupCounts -GroupCounts $Scope.signed_group_counts -Label "signed_group_counts" -Prefix $Prefix
  Write-GroupCounts -GroupCounts $Scope.unsigned_group_counts -Label "unsigned_group_counts" -Prefix $Prefix
  Write-Output "$($Prefix)boundary=pre-signature scope only; does not approve, sign, or certify route"
}

function Write-GeneratedArtifactFreshnessScope {
  param(
    [object]$Scope,
    [string]$Prefix = "- "
  )

  if (
    $null -eq $Scope -or
    $Scope.PSObject.Properties.Name -notcontains "artifact_count"
  ) {
    return
  }

  Write-Output "Generated artifact freshness scope:"
  foreach ($field in @("artifact_count", "valid_artifact_count", "stale_or_missing_artifact_count", "freshness_check_effect", "captures_business_owner_approval", "captures_product_or_api_decisions", "captures_golden_sample_approval", "captures_closure_approval", "writes_governance_records", "certification_effect")) {
    if ($Scope.PSObject.Properties.Name -contains $field) {
      Write-Output "${Prefix}${field}=$($Scope.$field)"
    }
  }
  Write-Output "$($Prefix)boundary=freshness scope only; does not approve, sign, write governance, or certify route"
}

function Format-RouteScopeRow {
  param(
    [object]$Row
  )

  $parts = @(
    "- $($Row.page_slug): $($Row.classification)",
    "route=$($Row.route)",
    "source=$($Row.source)",
    "blocking_reason=$($Row.blocking_reason)"
  )

  foreach ($field in @("business_owner_approval_captured", "golden_sample_approved")) {
    if ($Row.PSObject.Properties.Name -contains $field) {
      $parts += "$field=$($Row.$field)"
    }
  }
  if ($Row.PSObject.Properties.Name -contains "golden_sample_boundary_status") {
    $parts += "golden_boundary_status=$($Row.golden_sample_boundary_status)"
  }
  if (
    $Row.PSObject.Properties.Name -contains "golden_sample_artifact_status" -and
    $null -ne $Row.golden_sample_artifact_status -and
    "$($Row.golden_sample_artifact_status)" -ne ""
  ) {
    $parts += "golden_artifact_status=$($Row.golden_sample_artifact_status)"
  }
  if ($Row.PSObject.Properties.Name -contains "golden_sample_artifact_approved") {
    $parts += "golden_artifact_approved=$($Row.golden_sample_artifact_approved)"
  }
  if ($Row.PSObject.Properties.Name -contains "golden_sample_artifact_mismatch") {
    $parts += "golden_artifact_mismatch=$($Row.golden_sample_artifact_mismatch)"
  }
  if (
    $Row.PSObject.Properties.Name -contains "business_owner_action_missing_or_invalid_item_count" -and
    $null -ne $Row.business_owner_action_missing_or_invalid_item_count
  ) {
    $parts += "owner_action_missing_or_invalid=$($Row.business_owner_action_missing_or_invalid_item_count)"
  }
  if (
    $Row.PSObject.Properties.Name -contains "business_owner_action_pending_review_item_count" -and
    $null -ne $Row.business_owner_action_pending_review_item_count
  ) {
    $parts += "owner_action_pending_review=$($Row.business_owner_action_pending_review_item_count)"
  }
  if (
    $Row.PSObject.Properties.Name -contains "certification_packet_consistency_status" -and
    $null -ne $Row.certification_packet_consistency_status -and
    $Row.PSObject.Properties.Name -contains "certification_packet_consistency_owner_signable"
  ) {
    $parts += "owner_signable=$($Row.certification_packet_consistency_owner_signable)"
  }
  if (
    $Row.PSObject.Properties.Name -contains "certification_packet_consistency_status" -and
    $null -ne $Row.certification_packet_consistency_status -and
    $Row.PSObject.Properties.Name -contains "certification_packet_consistency_can_promote"
  ) {
    $parts += "can_promote_certification=$($Row.certification_packet_consistency_can_promote)"
  }
  if (
    $Row.PSObject.Properties.Name -contains "certification_effect" -and
    $null -ne $Row.certification_effect -and
    "$($Row.certification_effect)" -ne ""
  ) {
    $parts += "certification_effect=$($Row.certification_effect)"
  }
  if (
    $Row.PSObject.Properties.Name -contains "captures_product_or_api_decisions" -and
    $null -ne $Row.captures_product_or_api_decisions -and
    "$($Row.captures_product_or_api_decisions)" -ne ""
  ) {
    $parts += "captures_product_or_api_decisions=$($Row.captures_product_or_api_decisions)"
  }
  if (
    $Row.PSObject.Properties.Name -contains "certification_packet_consistency_status" -and
    $null -ne $Row.certification_packet_consistency_status -and
    $Row.PSObject.Properties.Name -contains "certification_packet_consistency_certification_effect" -and
    $null -ne $Row.certification_packet_consistency_certification_effect -and
    "$($Row.certification_packet_consistency_certification_effect)" -ne ""
  ) {
    $parts += "consistency_certification_effect=$($Row.certification_packet_consistency_certification_effect)"
  }
  if (
    $Row.PSObject.Properties.Name -contains "certification_packet_consistency_status" -and
    $null -ne $Row.certification_packet_consistency_status -and
    $Row.PSObject.Properties.Name -contains "certification_packet_consistency_captures_product_or_api_decisions"
  ) {
    $parts += "consistency_captures_product_or_api_decisions=$($Row.certification_packet_consistency_captures_product_or_api_decisions)"
  }
  if (
    $Row.PSObject.Properties.Name -contains "certification_packet_consistency_status" -and
    $null -ne $Row.certification_packet_consistency_status -and
    $Row.PSObject.Properties.Name -contains "certification_packet_consistency_writes_governance_records"
  ) {
    $parts += "consistency_writes_governance_records=$($Row.certification_packet_consistency_writes_governance_records)"
  }
  if (
    $Row.PSObject.Properties.Name -contains "generated_artifact_freshness_scope" -and
    $null -ne $Row.generated_artifact_freshness_scope -and
    $Row.generated_artifact_freshness_scope.PSObject.Properties.Name -contains "freshness_check_effect"
  ) {
    $parts += "freshness_check_effect=$($Row.generated_artifact_freshness_scope.freshness_check_effect)"
  }
  if (
    $Row.PSObject.Properties.Name -contains "generated_artifact_freshness_scope" -and
    $null -ne $Row.generated_artifact_freshness_scope -and
    $Row.generated_artifact_freshness_scope.PSObject.Properties.Name -contains "writes_governance_records"
  ) {
    $parts += "freshness_writes_governance_records=$($Row.generated_artifact_freshness_scope.writes_governance_records)"
  }
  if (
    $Row.PSObject.Properties.Name -contains "generated_artifact_freshness_scope" -and
    $null -ne $Row.generated_artifact_freshness_scope -and
    $Row.generated_artifact_freshness_scope.PSObject.Properties.Name -contains "certification_effect"
  ) {
    $parts += "freshness_certification_effect=$($Row.generated_artifact_freshness_scope.certification_effect)"
  }

  return ($parts -join "; ")
}

function Write-RouteScopeClassificationReport {
  param(
    [object]$Report
  )

  Write-Output "Summary: route_count=$($Report.summary.route_count); seeded_trace_bundle_count=$($Report.summary.seeded_trace_bundle_count); visible_unseeded_route_count=$($Report.summary.visible_unseeded_route_count); business_contract_certified_count=$($Report.summary.business_contract_certified_count); evidence_pending_count=$($Report.summary.evidence_pending_count); gate_i_gap_count=$($Report.summary.gate_i_gap_count); unclassified_count=$($Report.summary.unclassified_count); business_owner_action_signoff_missing_or_invalid_item_count=$($Report.summary.business_owner_action_signoff_missing_or_invalid_item_count); business_owner_action_signoff_pending_review_item_count=$($Report.summary.business_owner_action_signoff_pending_review_item_count)"
  Write-Output "Route classification rows:"
  foreach ($row in $Report.routes) {
    Write-Output (Format-RouteScopeRow -Row $row)
  }
  Write-Output "Boundary: $($Report.claim_boundary)"
}

function Get-GoldenBoundaryStatus {
  param(
    [object]$GoldenGate
  )

  if ($null -eq $GoldenGate) {
    return "missing"
  }

  $detail = "$($GoldenGate.detail)"
  if ($detail.Contains(";")) {
    return $detail.Split(";")[0].Trim()
  }
  return $detail
}

function Test-GoldenArtifactApproved {
  param(
    [object]$Page
  )

  if (
    $Page.PSObject.Properties.Name -notcontains "golden_sample_approval_artifacts" -or
    $null -eq $Page.golden_sample_approval_artifacts
  ) {
    return $false
  }

  $artifacts = @($Page.golden_sample_approval_artifacts)
  if ($artifacts.Count -eq 0) {
    return $false
  }

  foreach ($artifact in $artifacts) {
    if (
      $artifact.status -ne "approved" -or
      $artifact.owner -in @($null, "", "TBD", "unknown") -or
      $artifact.approver -in @($null, "", "TBD", "unknown") -or
      $artifact.approved_at -in @($null, "", "TBD", "unknown")
    ) {
      return $false
    }
  }
  return $true
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
    Write-CertificationPacketConsistency -Consistency $Report.certification_packet_consistency
    Write-BusinessOwnerActionSignoffSummary -Summary $Report.business_owner_approval_status.business_owner_action_signoff_summary
    Write-OwnerPreSignatureBlockerScope -Scope $Report.business_owner_approval_status.owner_pre_signature_blocker_scope
    Write-GeneratedArtifactFreshnessScope -Scope $Report.business_owner_approval_status.generated_artifact_freshness_scope
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
    Write-CertificationPacketConsistency -Consistency $page.certification_packet_consistency -Prefix "  - "
    Write-BusinessOwnerActionSignoffSummary -Summary $page.business_owner_approval_status.business_owner_action_signoff_summary -Prefix "  - "
    Write-OwnerPreSignatureBlockerScope -Scope $page.business_owner_approval_status.owner_pre_signature_blocker_scope -Prefix "  - "
    Write-GeneratedArtifactFreshnessScope -Scope $page.business_owner_approval_status.generated_artifact_freshness_scope -Prefix "  - "
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

if ($RouteScope) {
  Write-Output "MOSS page readiness gate: route-scope classification"

  $json = & $pythonExe $pythonScript --route-scope
  if ($LASTEXITCODE -ne 0) {
    throw "Static route-scope classification failed."
  }

  $report = $json | ConvertFrom-Json
  Write-RouteScopeClassificationReport -Report $report
  Write-Output "Route-scope dry run complete. Classification only; no approval is captured."
  exit 0
}

if ($All) {
  Write-Output "MOSS page readiness gate: all seeded pages"

  $json = & $pythonExe $pythonScript --all
  if ($LASTEXITCODE -ne 0) {
    throw "Static page readiness evaluation failed for all seeded pages."
  }

  $report = $json | ConvertFrom-Json
  Assert-AllApprovalCaptured -Report $report
  Write-Output "Summary: page_count=$($report.summary.page_count); static_pass_count=$($report.summary.static_pass_count); blocked_count=$($report.summary.blocked_count); formal_or_governed_count=$($report.summary.formal_or_governed_count); mixed_or_candidate_count=$($report.summary.mixed_or_candidate_count); run_supported_count=$($report.summary.run_supported_count); business_owner_approval_pending_count=$($report.summary.business_owner_approval_pending_count); business_owner_approval_action_item_count=$($report.summary.business_owner_approval_action_item_count); business_owner_action_signoff_missing_or_invalid_item_count=$($report.summary.business_owner_action_signoff_missing_or_invalid_item_count); business_owner_action_signoff_pending_review_item_count=$($report.summary.business_owner_action_signoff_pending_review_item_count)"
  Write-Output "Page readiness rows:"
  foreach ($page in $report.pages) {
    $goldenGate = $page.static_gates | Where-Object { $_.name -eq "golden_sample_boundary" } | Select-Object -First 1
    $goldenBoundaryStatus = Get-GoldenBoundaryStatus -GoldenGate $goldenGate
    $goldenArtifactStatus = "missing"
    if ($page.PSObject.Properties.Name -contains "golden_sample_approval_artifact_status") {
      $goldenArtifactStatus = "$($page.golden_sample_approval_artifact_status)"
    }
    $goldenArtifactApproved = Test-GoldenArtifactApproved -Page $page
    $goldenArtifactMismatch = $false
    if ($page.PSObject.Properties.Name -contains "golden_sample_approval_artifact_mismatch") {
      $goldenArtifactMismatch = [bool]$page.golden_sample_approval_artifact_mismatch
    }
    Write-Output "- $($page.page_slug): $($page.overall_status); approval=$($page.approval_status); golden_boundary_status=$goldenBoundaryStatus; golden_artifact_status=$goldenArtifactStatus; golden_artifact_approved=$goldenArtifactApproved; golden_artifact_mismatch=$goldenArtifactMismatch; run_supported=$($page.run_supported)"
  }
  if (
    $null -ne $report.business_owner_approval_pending_pages -and
    $report.business_owner_approval_pending_pages.Count -gt 0
  ) {
    Write-Output "Business-owner approval pending pages:"
    foreach ($page in $report.business_owner_approval_pending_pages) {
      Write-Output "- $($page.page_slug) ($($page.page_id)): $($page.approval_status); captured=$($page.business_owner_approval_captured); action_items=$($page.approval_action_item_count)"
      Write-ApprovalEvidenceScope -EvidenceScope $page.evidence_scope -Prefix "  - "
      Write-CertificationPacketConsistency -Consistency $page.certification_packet_consistency -Prefix "  - "
      Write-BusinessOwnerActionSignoffSummary -Summary $page.business_owner_action_signoff_summary -Prefix "  - "
      Write-OwnerPreSignatureBlockerScope -Scope $page.owner_pre_signature_blocker_scope -Prefix "  - "
      Write-GeneratedArtifactFreshnessScope -Scope $page.generated_artifact_freshness_scope -Prefix "  - "
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

$json = & $pythonExe $pythonScript --page-slug $PageSlug
$pythonExitCode = $LASTEXITCODE
$jsonText = $json | Out-String
if ([string]::IsNullOrWhiteSpace($jsonText)) {
  throw "Static page readiness evaluation failed for $PageSlug."
}

$report = $jsonText | ConvertFrom-Json
if ($pythonExitCode -ne 0 -and $report.blocking_gates.Count -eq 0) {
  throw "Static page readiness evaluation failed for $PageSlug."
}

Write-PageReadinessReport -Report $report
Assert-ApprovalCaptured -Report $report -ActionItemsAlreadyShown

if ($report.blocking_gates.Count -gt 0) {
  throw "Static page readiness gates blocked."
}

if (-not $Run) {
  Write-Output "Dry run complete. Pass -Run to execute page checks."
  exit 0
}

if (-not $report.run_supported) {
  throw "Local smoke/verify helpers are not wired for $PageSlug. Static readiness report is available, but -Run is not supported yet."
}

Invoke-PageReadinessChecks -Slug $PageSlug
Write-Output "Page readiness gate passed."
