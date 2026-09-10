<# Start the installed EXP-001 F4 profile in this terminal. Type stop to exit. #>
[CmdletBinding()]
param(
    [string]$ServerDir,
    [string]$JavaExe = 'java',
    [int]$XmxMB = 6144
)
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $ServerDir) { $ServerDir = Join-Path $Repo 'experiments\EXP-000-cobblemon-1.8-compat\runtime\server' }
$ServerDir = (Resolve-Path -LiteralPath $ServerDir -ErrorAction Stop).Path
$worldName = 'exp001-f4-pallet-prototype'
$properties = Join-Path $ServerDir 'server.properties'
if (-not ((Get-Content -LiteralPath $properties) -contains "level-name=$worldName")) {
    throw "EXP-001 is not selected. Run server/scripts/install-exp001-world.ps1 first."
}
if (-not (Test-Path -LiteralPath (Join-Path $ServerDir "$worldName\level.dat"))) { throw "EXP-001 save is missing." }
if (-not (Test-Path -LiteralPath (Join-Path $ServerDir 'datapacks\cobblers_campaign\data\cobblers\function\exp_001\f4\setup.mcfunction'))) { throw "EXP-001 datapack is missing." }
$launcher = Get-ChildItem -LiteralPath $ServerDir -File -Filter 'fabric-server*.jar' | Select-Object -First 1
if (-not $launcher) { throw "Fabric launcher is missing from $ServerDir" }
$xms = [Math]::Max(1024, [int]($XmxMB / 2))
Write-Host "Launching EXP-001 F4 on the shared complete-overlay runtime."
Write-Host "Join Multiplayer at localhost after the server prints Done (...)."
Push-Location $ServerDir
try {
    & $JavaExe "-Xms${xms}M" "-Xmx${XmxMB}M" -jar $launcher.Name -nogui
} finally {
    Pop-Location
}
