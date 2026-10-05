#Requires -Version 5.1
<#
.SYNOPSIS
    End-to-end test: install the packaged server, boot it, check every plugin and datapack loaded, stop it.

.EXAMPLE
    # From an unzipped release (or a copy of package/):
    .\tests\smoke.ps1 -Root C:\temp\TheRealms-Server -Port 25566 -RconPort 25576
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$Root,
    [int]$Port = 25565,
    [int]$RconPort = 25575,
    [int]$MemoryGB = 3,
    [int]$TimeoutMinutes = 20
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path $Root).Path
$script = Join-Path $Root 'realms\realms.ps1'
$server = Join-Path $Root 'server'
$manifest = Get-Content (Join-Path $Root 'realms\manifest.json') -Raw | ConvertFrom-Json
$failures = New-Object System.Collections.Generic.List[string]

function Invoke-Realms([string[]]$Arguments) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script @Arguments
    if ($LASTEXITCODE -ne 0) { throw "realms.ps1 $($Arguments -join ' ') failed ($LASTEXITCODE)" }
}

Write-Host '--- install (non-interactive)'
Invoke-Realms @('install', '-AcceptEula', '-NonInteractive', '-NoOwner')

Write-Host '--- second install must be a no-op'
$again = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script install -NonInteractive -NoOwner | Out-String
if ($again -notmatch 'Everything is up to date') { $failures.Add("re-install was not a no-op:`n$again") }

$props = Join-Path $server 'server.properties'
$text = [IO.File]::ReadAllText($props)
if ($text -match '\{\{') { $failures.Add('server.properties still has {{placeholders}}') }
if ($text -notmatch "(?m)^level-seed=$([regex]::Escape([string]$manifest.world.seed))\s*$") { $failures.Add('seed not applied') }
$text = $text -replace '(?m)^server-port=.*$', "server-port=$Port" -replace '(?m)^rcon\.port=.*$', "rcon.port=$RconPort"
[IO.File]::WriteAllText($props, $text, (New-Object System.Text.UTF8Encoding $false))

Write-Host "--- start (port $Port)"
$out = Join-Path $Root 'smoke-console.log'
$proc = Start-Process powershell.exe -PassThru -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError "$out.err" `
    -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$script`"", 'start', '-NonInteractive', '-MemoryGB', $MemoryGB)
$log = Join-Path $server 'logs\latest.log'
$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
$started = $false
while ((Get-Date) -lt $deadline -and -not $proc.HasExited) {
    if ((Test-Path $log) -and (Select-String -Path $log -Pattern 'Done \(' -Quiet)) { $started = $true; break }
    Start-Sleep -Seconds 5
}
if (-not $started) {
    if (Test-Path $out) { Get-Content $out -Tail 60 }
    throw "Server did not finish starting within $TimeoutMinutes minutes (exited: $($proc.HasExited))"
}
$doneLine = (Select-String -Path $log -Pattern 'Done \(' | Select-Object -First 1).Line
Write-Host "--- started: $doneLine"

try {
    # Paper shortens long replies with "...", so check the count and that nothing was left disabled.
    $enabled = (Invoke-Realms @('rcon', 'datapack list enabled')) -join "`n"
    $count = if ($enabled -match 'There are (\d+) data pack') { [int]$Matches[1] } else { 0 }
    if ($count -lt @($manifest.datapacks).Count + 1) { $failures.Add("only $count datapacks enabled: $enabled") }
    $available = (Invoke-Realms @('rcon', 'datapack list available')) -join "`n"
    if ($available -match 'file/') { $failures.Add("datapacks present but not enabled: $available") }
    $plugins = (Invoke-Realms @('rcon', 'plugins')) -join "`n"
    Write-Host $plugins
    if ($plugins -notmatch "Server Plugins \($(@($manifest.plugins).Count)\)") { $failures.Add('not every plugin loaded') }
    $seed = (Invoke-Realms @('rcon', 'seed')) -join ''
    if ($seed -notmatch [regex]::Escape("[$($manifest.world.seed)]")) { $failures.Add("world seed is not the pinned one: $seed") }
} finally {
    Write-Host '--- stop'
    Invoke-Realms @('stop')
    if (-not $proc.WaitForExit(120000)) { $proc.Kill(); $failures.Add('server did not exit after stop') }
}

$logText = Get-Content $log -Raw
foreach ($pattern in 'Error occurred while enabling', 'Could not load ''plugins', 'Unknown dependency', 'Ambiguous plugin name') {
    foreach ($m in [regex]::Matches($logText, "(?m)^.*$([regex]::Escape($pattern)).*$")) { $failures.Add("log: $($m.Value)") }
}
# LuckPerms answers commands on the console, not over RCON, so check its storage instead.
if ($logText -notmatch 'LuckPerms\] Loading storage provider\.\.\. \[YAML\]') { $failures.Add('LuckPerms is not using the YAML ranks') }
foreach ($g in 'default', 'builder', 'moderator', 'admin') {
    if (-not (Test-Path (Join-Path $server "plugins\LuckPerms\yaml-storage\groups\$g.yml"))) { $failures.Add("LuckPerms rank missing: $g") }
}
foreach ($p in $manifest.plugins) {
    $jar = Join-Path $server "plugins\$($p.file)"
    if (-not (Test-Path -LiteralPath $jar)) { $failures.Add("plugin jar missing: $($p.file)") }
}
if ($logText -notmatch 'All dimensions are saved|Closing Server') { $failures.Add('server did not shut down cleanly') }

if ($failures.Count) {
    Write-Host "`nSMOKE TEST FAILED ($($failures.Count)):" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 1
}
Write-Host "`nSMOKE TEST PASSED: $(@($manifest.plugins).Count) plugins, $(@($manifest.datapacks).Count) datapacks" -ForegroundColor Green
