# W17, direct HPC Pack example (lowest priority; NOT VERIFIED - no cluster was available).
# One task of a parametric sweep job: HPC Pack replaces * in the command line with the sweep index (1..N);
# this script finds row N of the round's runs.csv (written by `study next`, column `index`), writes that run's
# parameters file from the template and runs the simulation with it.
#
#   job new /jobname:"round 3"
#   job add <id> /parametric:1-240 /workdir:\\share\study\next\round_3 ^
#       powershell -ExecutionPolicy Bypass -File \\share\tools\hpc\run_one.ps1 -Index * -Exe \\share\sim\sim.exe
#   job submit /id:<id>
param(
    [Parameter(Mandatory = $true)][int]$Index,
    [Parameter(Mandatory = $true)][string]$Exe,
    [string]$Runs = "runs.csv",
    [string]$Template = "params_template.xml",
    [string]$Results = "results"
)
$ErrorActionPreference = "Stop"
$row = Import-Csv $Runs | Where-Object { [int]$_.index -eq $Index }
if (-not $row) { throw "No row with index $Index in $Runs" }
$text = Get-Content $Template -Raw
foreach ($p in $row.PSObject.Properties) {
    $value = [System.Security.SecurityElement]::Escape([string]$p.Value)    # XML-safe
    $text = $text -replace ("\{\{\s*" + [regex]::Escape($p.Name) + "\s*\}\}"), $value
}
New-Item -ItemType Directory -Force -Path "params", $Results | Out-Null
$params = Join-Path "params" ($row.run_id + ".xml")
Set-Content -Path $params -Value $text -Encoding UTF8
& $Exe $params
if ($LASTEXITCODE -ne 0) { New-Item -ItemType File -Force -Path (Join-Path $Results ($row.run_id + ".failed")) | Out-Null }
exit $LASTEXITCODE
