<#
.SYNOPSIS
  Boot the assembled Fabric server once and record what happened.

.DESCRIPTION
  Pre-flight: server dir exists, Java >= 21, a Fabric server launcher jar is
  present, mods/ is non-empty, and eula.txt already accepts the EULA (this
  script never writes eula.txt; if it is missing or still false it stops and
  tells the human to read and accept it). Then launches the server with -nogui,
  tails logs/latest.log until "Done (" (success) or a crash / process exit /
  timeout, sends "stop", and copies logs/latest.log plus any new crash report
  into experiments/EXP-000-cobblemon-1.8-compat/runs/<timestamp>/ together with
  a verdict.txt. Exit 0 = booted, 1 = failed, 2 = pre-flight refused.

.PARAMETER ServerDir   Directory containing the Fabric server launcher, mods/, eula.txt.
.PARAMETER JavaExe     Java executable (default: 'java' from PATH).
.PARAMETER XmxMB       Max heap in MB (default 6144). Xms is half of it.
.PARAMETER TimeoutSec  Give up waiting for "Done (" after this many seconds (default 600).
.PARAMETER RunsDir     Where to store run captures (default: the EXP-000 runs folder).
.PARAMETER Label       Free text stored in verdict.txt (e.g. "cobblemon-1.8.0 first boot").
.PARAMETER AllowEulaPrompt
  Permit an initialization launch when eula.txt is missing or false. The server
  may create eula.txt and exit at its EULA notice; this script never changes its
  value. Use only to prove initialization reaches EULA handling.
.PARAMETER WhatIf      Run pre-flight only, print the launch command, do not start Java.

.EXAMPLE
  pwsh server/scripts/boot-test.ps1 -ServerDir D:\srv -WhatIf
  pwsh server/scripts/boot-test.ps1 -ServerDir D:\srv -Label "1.8.0 + overlay"
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$ServerDir,
    [string]$JavaExe = 'java',
    [int]$XmxMB = 6144,
    [int]$TimeoutSec = 600,
    [string]$RunsDir,
    [string]$Label = '',
    [switch]$AllowEulaPrompt
)
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $RunsDir) { $RunsDir = Join-Path $Repo 'experiments\EXP-000-cobblemon-1.8-compat\runs' }

function Refuse([string]$msg) { Write-Host "PRE-FLIGHT REFUSED: $msg"; exit 2 }

# ---- pre-flight -----------------------------------------------------------
if (-not (Test-Path -LiteralPath $ServerDir -PathType Container)) { Refuse "server dir not found: $ServerDir" }
$ServerDir = (Resolve-Path -LiteralPath $ServerDir).Path

try { $javaOut = & $JavaExe -version 2>&1 | Out-String } catch { Refuse "cannot run '$JavaExe -version': $($_.Exception.Message)" }
if ($LASTEXITCODE -ne 0 -or -not $javaOut) { Refuse "cannot run '$JavaExe -version'" }
if ($javaOut -notmatch 'version "(\d+)(?:\.(\d+))?') { Refuse "cannot parse java version from: $javaOut" }
$major = [int]$Matches[1]; if ($major -eq 1) { $major = [int]$Matches[2] }
if ($major -lt 21) { Refuse "Java 21 required, found major version $major ($($javaOut.Trim().Split("`n")[0]))" }
Write-Host "java:      $($javaOut.Trim().Split("`n")[0])"

$launcher = Get-ChildItem -LiteralPath $ServerDir -File -Filter '*.jar' |
    Where-Object { $_.Name -match '^fabric-server' } | Select-Object -First 1
if (-not $launcher) { Refuse "no fabric-server*.jar launcher in $ServerDir (run the Fabric installer first; see server/launch/README.md)" }
Write-Host "launcher:  $($launcher.Name)"

$modsDir = Join-Path $ServerDir 'mods'
$modCount = if (Test-Path -LiteralPath $modsDir) { @(Get-ChildItem -LiteralPath $modsDir -File -Filter '*.jar').Count } else { 0 }
if ($modCount -eq 0) { Refuse "no jars in $modsDir (run server/scripts/assemble-server.ps1 -Apply)" }
Write-Host "mods:      $modCount jars"

# EULA: must already be accepted by a human. Match 'eula', '=', 'true' with optional spaces.
$eulaPath = Join-Path $ServerDir 'eula.txt'
$eulaPattern = 'eula' + '\s*=\s*' + 'true'
if (-not (Test-Path -LiteralPath $eulaPath)) {
    if (-not $AllowEulaPrompt) {
        Refuse "eula.txt not found in $ServerDir. Start the server once by hand (it writes the file), read https://aka.ms/MinecraftEULA, and accept it yourself if you agree. This script will not write it."
    }
    Write-Host "eula:      absent; initialization launch allowed (the script will not accept it)"
}
else {
    $eulaLines = Get-Content -LiteralPath $eulaPath | Where-Object { $_ -notmatch '^\s*#' }
    if (-not ($eulaLines -match $eulaPattern)) {
        if (-not $AllowEulaPrompt) {
            Refuse "eula.txt does not accept the EULA. Read https://aka.ms/MinecraftEULA and, if you agree, edit $eulaPath yourself. This script will not write it."
        }
        Write-Host "eula:      not accepted; initialization launch allowed (the script will not change it)"
    }
    else {
        Write-Host "eula:      accepted by a human in $eulaPath"
    }
}

$xms = [math]::Max(1024, [int]($XmxMB / 2))
$jvmArgs = @("-Xms${xms}M", "-Xmx${XmxMB}M", '-jar', $launcher.Name, '-nogui')
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$runDir = Join-Path $RunsDir $stamp
Write-Host "command:   $JavaExe $($jvmArgs -join ' ')   (cwd $ServerDir)"
Write-Host "capture:   $runDir"

if ($WhatIfPreference) {
    Write-Host 'WhatIf: pre-flight passed; server NOT started.'
    exit 0
}
if (-not $PSCmdlet.ShouldProcess($ServerDir, "launch server")) { exit 0 }

# ---- launch ----------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
$logPath = Join-Path $ServerDir 'logs\latest.log'
$crashDir = Join-Path $ServerDir 'crash-reports'
$start = Get-Date
$stdoutPath = Join-Path $runDir 'stdout.txt'

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $JavaExe
$psi.Arguments = ($jvmArgs -join ' ')
$psi.WorkingDirectory = $ServerDir
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$proc = [System.Diagnostics.Process]::Start($psi)
$stdoutTask = $proc.StandardOutput.ReadToEndAsync()
$stderrTask = $proc.StandardError.ReadToEndAsync()

$verdict = 'TIMEOUT'; $detail = "no 'Done (' within $TimeoutSec s"
while ($true) {
    Start-Sleep -Seconds 2
    $tail = if (Test-Path -LiteralPath $logPath) { Get-Content -LiteralPath $logPath -Tail 200 -ErrorAction SilentlyContinue } else { @() }
    $done = $tail | Where-Object { $_ -match 'Done \(' } | Select-Object -First 1
    if ($done) { $verdict = 'BOOTED'; $detail = $done.Trim(); break }
    $fatal = $tail | Where-Object { $_ -match 'Incompatible mods found|Mod resolution failed|FATAL|MixinApplyError|Failed to start the minecraft server' } | Select-Object -First 1
    if ($fatal) { $verdict = 'CRASH'; $detail = $fatal.Trim(); break }
    if ($proc.HasExited) { $verdict = 'EXITED'; $detail = "process exited with code $($proc.ExitCode) before 'Done ('"; break }
    if (((Get-Date) - $start).TotalSeconds -gt $TimeoutSec) { break }
}

if (-not $proc.HasExited) {
    try { $proc.StandardInput.WriteLine('stop'); $proc.StandardInput.Flush() } catch {}
    if (-not $proc.WaitForExit(90000)) { try { $proc.Kill() } catch {} ; $detail += ' (killed after stop timeout)' }
}
$combinedOutput = $stdoutTask.Result + "`n--- stderr ---`n" + $stderrTask.Result
$combinedOutput | Set-Content -LiteralPath $stdoutPath
if ($verdict -eq 'EXITED' -and $combinedOutput -match '(?i)agree to the EULA|eula\.txt') {
    $verdict = 'EULA-REQUIRED'
    $detail = 'initialization reached Minecraft EULA handling; EULA remains unaccepted'
}

# ---- capture ---------------------------------------------------------------
if (Test-Path -LiteralPath $logPath) { Copy-Item -LiteralPath $logPath -Destination (Join-Path $runDir 'latest.log') }
if (Test-Path -LiteralPath $crashDir) {
    Get-ChildItem -LiteralPath $crashDir -File | Where-Object { $_.LastWriteTime -ge $start } |
        ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $runDir; if ($verdict -eq 'BOOTED') { $verdict = 'BOOTED-WITH-CRASH-REPORT' } }
}
$modList = Get-ChildItem -LiteralPath $modsDir -File -Filter '*.jar' | Sort-Object Name | ForEach-Object { $_.Name }
$modList | Set-Content -LiteralPath (Join-Path $runDir 'mods.txt')
$modSetHash = (Get-FileHash -InputStream ([IO.MemoryStream]::new([Text.Encoding]::UTF8.GetBytes(($modList -join "`n")))) -Algorithm SHA256).Hash.Substring(0, 12)
@(
    "verdict:      $verdict",
    "detail:       $detail",
    "label:        $Label",
    "started:      $($start.ToString('s'))",
    "duration_s:   $([int]((Get-Date) - $start).TotalSeconds)",
    "server_dir:   $ServerDir",
    "launcher:     $($launcher.Name)",
    "java:         $($javaOut.Trim().Split("`n")[0])",
    "mods:         $modCount (set hash $modSetHash, list in mods.txt)",
    "jvm_args:     $($jvmArgs -join ' ')"
) | Set-Content -LiteralPath (Join-Path $runDir 'verdict.txt')

Write-Host ''
Write-Host "VERDICT: $verdict - $detail"
Write-Host "captured to $runDir (mod set hash $modSetHash). Add a row to experiments/EXP-000-cobblemon-1.8-compat/results.md."
exit $(if ($verdict -like 'BOOTED*') { 0 } else { 1 })
