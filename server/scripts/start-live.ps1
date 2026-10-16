# Start the live server detached, its console written to files instead of a window.
#
# Why (2026-10-16): on 2026-10-15 23:42 the live server's thread blocked ~168 s inside a log write to its console
# window (a Windows console pauses output while text is selected, QuickEdit), the watchdog called it crashed and shut it
# down. With stdout/stderr going to files nothing can pause the writes. The game log is still logs/latest.log; commands
# go through RCON; stop it with RCON `stop`.
#
# Usage: & .\server\scripts\start-live.ps1 [-ServerDir <dir>] [-Heap 12G]
param(
    [string]$ServerDir = "C:\Users\wnd\Documents\github\cobblers-server",
    [string]$Heap = "12G"
)
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$out = Join-Path $ServerDir "logs\console-$stamp.out.log"
$err = Join-Path $ServerDir "logs\console-$stamp.err.log"
$p = Start-Process -FilePath java -ArgumentList "-Xmx$Heap", "-jar", "fabric-server-launch.jar", "nogui" `
    -WorkingDirectory $ServerDir -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
Write-Output ("started java pid {0}; console -> {1}" -f $p.Id, $out)
