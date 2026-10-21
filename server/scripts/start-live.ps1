# Start the live server fully detached, its console written to files instead of a window.
#
# Why (2026-10-16): on 2026-10-15 23:42 the live server's thread blocked ~168 s inside a log write to its console
# window (a Windows console pauses output while text is selected, QuickEdit), the watchdog called it crashed and shut it
# down. With stdout/stderr going to files nothing can pause the writes.
# Why WMI (2026-10-20): a server started with Start-Process from a Claude terminal tab died silently when the app reset
# its terminal (the log ends after boot, no shutdown line). Win32_Process.Create starts it outside the caller's process
# tree and job, so it survives the terminal, the tab and the app.
# The game log is still logs/latest.log; commands go through RCON; stop it with RCON `stop`.
#
# Usage: & .\server\scripts\start-live.ps1 [-ServerDir <dir>] [-Heap 12G]
param(
    [string]$ServerDir = "C:\Users\wnd\Documents\github\cobblers-server",
    [string]$Heap = "12G"
)
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$out = Join-Path $ServerDir "logs\console-$stamp.out.log"
$err = Join-Path $ServerDir "logs\console-$stamp.err.log"
$cmd = 'cmd.exe /c java -Xmx{0} -jar fabric-server-launch.jar nogui > "{1}" 2> "{2}"' -f $Heap, $out, $err
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = $ServerDir }
if ($r.ReturnValue -ne 0) { throw "Win32_Process.Create failed: $($r.ReturnValue)" }
Write-Output ("started (cmd pid {0}); console -> {1}" -f $r.ProcessId, $out)
