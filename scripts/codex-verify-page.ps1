param(
  [ValidateSet("product-category-pnl")]
  [string]$PageSlug = "product-category-pnl",

  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $root "frontend"

Set-Location $root

Write-Output "CODEx verify page: $PageSlug"

if ($PageSlug -ne "product-category-pnl") {
  throw "Unsupported page slug: $PageSlug"
}

$checks = @(
  @{
    Label = "MCP contract tests"
    WorkingDirectory = $root
    Command = "python"
    Args = @("-m", "pytest", "tests/test_project_mcp_servers.py", "-q")
  },
  @{
    Label = "Product-category backend flow and mapping tests"
    WorkingDirectory = $root
    Command = "python"
    Args = @("-m", "pytest", "tests/test_product_category_pnl_flow.py", "tests/test_product_category_mapping_contract.py", "-q")
  },
  @{
    Label = "Product-category frontend tests"
    WorkingDirectory = $frontendRoot
    Command = "npm.cmd"
    Args = @(
      "run",
      "test",
      "--",
      "src/test/ProductCategoryPnlPage.test.tsx",
      "src/test/ProductCategoryBranchSwitcher.test.tsx",
      "src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts"
    )
  },
  @{
    Label = "Frontend typecheck"
    WorkingDirectory = $frontendRoot
    Command = "npm.cmd"
    Args = @("run", "typecheck")
  },
  @{
    Label = "Frontend debt audit"
    WorkingDirectory = $frontendRoot
    Command = "npm.cmd"
    Args = @("run", "debt:audit")
  }
)

foreach ($check in $checks) {
  $argsText = ($check.Args -join " ")
  Write-Output "[$($check.Label)] $($check.Command) $argsText"

  if ($DryRun) {
    continue
  }

  Push-Location $check.WorkingDirectory
  try {
    & $check.Command @($check.Args)
    if ($LASTEXITCODE -ne 0) {
      throw "$($check.Label) failed with exit code $LASTEXITCODE"
    }
  } finally {
    Pop-Location
  }
}

if ($DryRun) {
  Write-Output "CODEx verify page dry run complete."
} else {
  Write-Output "CODEx verify page checks passed."
}
