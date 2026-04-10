param(
    [string]$PythonExe = "python",
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Category = "Drawings",
    [string]$Component = "FB",
    [switch]$StartServer,
    [switch]$AllowEmptySearch
)

$scriptPath = Join-Path $PSScriptRoot "api_regression_smoke.py"
$args = @(
    $scriptPath,
    "--base-url", $BaseUrl,
    "--category", $Category,
    "--component", $Component
)

if ($StartServer.IsPresent) {
    $args += "--start-server"
}

if ($AllowEmptySearch.IsPresent) {
    $args += "--allow-empty-search"
}

& $PythonExe @args
exit $LASTEXITCODE
