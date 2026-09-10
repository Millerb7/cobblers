<#
.SYNOPSIS
  Install the exported EXP-001 F4 world into the proven complete-overlay runtime.

.DESCRIPTION
  Keeps the EXP-000 server binaries/mods as the shared runtime, but installs a
  separate level named exp001-f4-pallet-prototype and selects it in
  server.properties. Existing worlds are never overwritten unless -Replace is
  supplied; replacements are moved into EXP-001's ignored runtime/backups.
  This script does not create, edit, or copy eula.txt.
#>
[CmdletBinding()]
param(
    [string]$ServerDir,
    [string]$ExportedWorld,
    [string]$WorldName = 'exp001-f4-pallet-prototype',
    [switch]$Replace
)
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $ServerDir) { $ServerDir = Join-Path $Repo 'experiments\EXP-000-cobblemon-1.8-compat\runtime\server' }
if (-not $ExportedWorld) { $ExportedWorld = Join-Path $Repo 'experiments\EXP-001-curated-route\runtime\export\heightmap' }
if (-not (Test-Path -LiteralPath $ServerDir -PathType Container)) { throw "Shared server runtime not found: $ServerDir" }
if (-not (Test-Path -LiteralPath (Join-Path $ExportedWorld 'level.dat') -PathType Leaf)) { throw "WorldPainter export is not a usable save: $ExportedWorld" }
$ServerDir = (Resolve-Path -LiteralPath $ServerDir).Path
$ExportedWorld = (Resolve-Path -LiteralPath $ExportedWorld).Path
$target = Join-Path $ServerDir $WorldName
$serverPrefix = $ServerDir.TrimEnd('\') + '\'
if (-not $target.StartsWith($serverPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe target path: $target" }

if (Test-Path -LiteralPath $target) {
    if (-not $Replace) { throw "Target world already exists. Re-run with -Replace to archive and reinstall it: $target" }
    $backupRoot = Join-Path $Repo 'experiments\EXP-001-curated-route\runtime\backups'
    New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
    $backup = Join-Path $backupRoot ("$WorldName-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    Move-Item -LiteralPath $target -Destination $backup
    Write-Host "archived:   $backup"
}
Copy-Item -LiteralPath $ExportedWorld -Destination $target -Recurse

$campaignSource = Join-Path $Repo 'modpack\datapacks\cobblers_campaign'
$campaignTarget = Join-Path $ServerDir 'datapacks\cobblers_campaign'
New-Item -ItemType Directory -Force -Path $campaignTarget | Out-Null
Copy-Item -Path (Join-Path $campaignSource '*') -Destination $campaignTarget -Recurse -Force

$properties = Join-Path $ServerDir 'server.properties'
if (-not (Test-Path -LiteralPath $properties)) { throw "Missing server.properties: $properties" }
$text = Get-Content -LiteralPath $properties -Raw
if ($text -match '(?m)^level-name=') {
    $text = $text -replace '(?m)^level-name=.*$', "level-name=$WorldName"
} else {
    $text = $text.TrimEnd() + "`r`nlevel-name=$WorldName`r`n"
}
Set-Content -LiteralPath $properties -Value $text -NoNewline
Write-Host "installed:  $target"
Write-Host "selected:   level-name=$WorldName"
Write-Host "datapack:   $campaignTarget"
Write-Host 'EULA:       unchanged'
