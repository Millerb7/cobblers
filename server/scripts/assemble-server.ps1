<#
.SYNOPSIS
  Build the dedicated server's mods/ folder from the manifest plan (--side server).

.DESCRIPTION
  Asks tools/pack_manifest.py for the effective server-side mod list (base pack
  + overlay: replacements applied, removals dropped, client-only mods excluded),
  then copies each jar from -SourceDir (and optionally -ExtraDir, searched first)
  into -TargetDir. Jars that exist nowhere are listed as MISSING. Dry-run by
  default; pass -Apply to write. Never downloads anything.

.PARAMETER SourceDir
  Folder of jars to copy from. Defaults to the base-pack mods folder of this
  checkout (which is empty in a fresh clone - jars are gitignored).
.PARAMETER ExtraDir
  Optional second folder, searched before SourceDir - e.g. where you downloaded
  the Cobblemon 1.8 replacement jars.
.PARAMETER TargetDir
  Destination mods/ folder. Default: <repo>/server/mods.
.PARAMETER Apply
  Actually copy. Without it the script only prints what it would do.
.PARAMETER Clean
  With -Apply: delete jars in TargetDir that are not in the plan.

.EXAMPLE
  pwsh server/scripts/assemble-server.ps1
  pwsh server/scripts/assemble-server.ps1 -ExtraDir D:\cobblemon18 -TargetDir D:\srv\mods -Apply
#>
[CmdletBinding()]
param(
    [string]$SourceDir,
    [string]$ExtraDir,
    [string]$TargetDir,
    [switch]$Apply,
    [switch]$Clean
)
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $SourceDir) { $SourceDir = Join-Path $Repo 'base-pack\cobbleverse\mods' }
if (-not $TargetDir) { $TargetDir = Join-Path $Repo 'server\mods' }
$Tool = Join-Path $Repo 'tools\pack_manifest.py'

Write-Host "repo:      $Repo"
Write-Host "source:    $SourceDir"
if ($ExtraDir) { Write-Host "extra:     $ExtraDir" }
Write-Host "target:    $TargetDir"
Write-Host "mode:      $(if ($Apply) { 'APPLY' } else { 'DRY RUN (pass -Apply to write)' })"
Write-Host ''

$json = & python $Tool plan --side server --json
if ($LASTEXITCODE -ne 0) { throw "pack_manifest.py plan failed" }
$plan = $json | ConvertFrom-Json
$active = @($plan | Where-Object { $_.status -in @('base', 'replace', 'add') })
Write-Host "$($active.Count) server-side jars in plan ($(@($plan | Where-Object status -eq 'replace').Count) replacements, $(@($plan | Where-Object status -eq 'remove').Count) removed)"

function Find-Jar([string]$name) {
    foreach ($d in @($ExtraDir, $SourceDir) | Where-Object { $_ }) {
        $p = Join-Path $d $name
        if (Test-Path -LiteralPath $p -PathType Leaf) { return $p }
    }
    return $null
}

$copied = @(); $missing = @(); $skipped = @()
foreach ($e in $active) {
    $src = Find-Jar $e.filename
    if (-not $src) {
        $missing += $e
        $why = if ($e.status -eq 'replace') { "replacement for $($e.replaces)" } else { 'base jar' }
        Write-Host ("MISSING   {0}  ({1}; mod {2})" -f $e.filename, $why, $e.mod_id)
        continue
    }
    $dst = Join-Path $TargetDir $e.filename
    if ((Test-Path -LiteralPath $dst) -and ((Get-Item -LiteralPath $dst).Length -eq (Get-Item -LiteralPath $src).Length)) {
        $skipped += $e.filename
        continue
    }
    Write-Host ("{0} {1}  <- {2}" -f $(if ($Apply) { 'COPY     ' } else { 'would copy' }), $e.filename, $src)
    if ($Apply) {
        New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
        Copy-Item -LiteralPath $src -Destination $dst -Force
    }
    $copied += $e.filename
}

$wanted = $active.filename
if (Test-Path -LiteralPath $TargetDir) {
    $extra = Get-ChildItem -LiteralPath $TargetDir -File -Filter '*.jar' | Where-Object { $_.Name -notin $wanted }
    foreach ($x in $extra) {
        if ($Apply -and $Clean) { Write-Host "REMOVE    $($x.Name)"; Remove-Item -LiteralPath $x.FullName -Force }
        else { Write-Host "EXTRA     $($x.Name)  (not in plan; -Apply -Clean deletes it)" }
    }
}

Write-Host ''
Write-Host "$($copied.Count) copied/would copy, $($skipped.Count) already present, $($missing.Count) missing"
if ($missing.Count -gt 0) {
    Write-Host 'Missing jars with a Modrinth URL can be fetched with:'
    Write-Host "  python tools/pack_manifest.py download --side server --target <dir> --yes"
    Write-Host 'then re-run with -ExtraDir <dir>.'
}
if ($Apply -and $missing.Count -eq 0) {
    Write-Host ''
    & python $Tool verify $TargetDir --side server
}
exit $(if ($missing.Count -gt 0) { 1 } else { 0 })
