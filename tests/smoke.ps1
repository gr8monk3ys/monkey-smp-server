#Requires -Version 5.1
<#
.SYNOPSIS
    End-to-end test: install the packaged server, boot it, check every plugin (Paper) or mod (Fabric)
    and datapack loaded, stop it.

.DESCRIPTION
    Runs realms.ps1 with the PowerShell that runs this script: Windows PowerShell 5.1 (powershell.exe)
    or PowerShell 7 (pwsh, on Windows, Linux or macOS).

.EXAMPLE
    # From an unzipped release (or a copy of package/):
    .\tests\smoke.ps1 -Root C:\temp\TheRealms-Server -Port 25566 -RconPort 25576
    pwsh tests/smoke.ps1 -Root /tmp/TheRealms-Server -MemoryGB 4
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
$script = Join-Path (Join-Path $Root 'realms') 'realms.ps1'
$server = Join-Path $Root 'server'
$onWindows = [IO.Path]::DirectorySeparatorChar -eq '\'
# realms.ps1 runs in a new process of this same PowerShell (powershell.exe, or pwsh on any platform).
$shell = if ($PSVersionTable.PSEdition -eq 'Core') { (Get-Process -Id $PID).Path } else { 'powershell.exe' }
$shellArgs = @('-NoProfile')
if ($onWindows) { $shellArgs += @('-ExecutionPolicy', 'Bypass') }
# The package's own module: one server.properties parser for the installer and this test.
Import-Module (Join-Path (Join-Path $Root 'realms') 'Realms.psm1') -Force
$manifest = (New-RealmsContext -Root $Root).Manifest
$layout = Get-ServerLayout -Manifest $manifest
$isPaper = $layout.Type -eq 'paper'
# The plugins (Paper) or mods (Fabric) the manifest pins, and the folder they go in.
$addOns = @($manifest.($layout.AddOns) | Where-Object { $_ })
$datapacks = @($manifest.datapacks | Where-Object { $_ })
# Ranks are whatever LuckPerms groups the Defaults ship, in the server type's LuckPerms storage folder.
$ranks = @(Get-ChildItem -LiteralPath (Join-Path $Root "realms/defaults/$($layout.LuckPerms)/groups") -Filter *.yml |
    ForEach-Object { $_.BaseName })
if (-not $ranks.Count) { throw 'No LuckPerms ranks found in the package Defaults' }
Write-Host "--- $($manifest.name) $($manifest.version): $($layout.Description), $($addOns.Count) $($layout.AddOns), $($datapacks.Count) datapacks"
$failures = New-Object System.Collections.Generic.List[string]

function Invoke-Realms([string[]]$Arguments) {
    & $shell @shellArgs -File $script @Arguments
    if ($LASTEXITCODE -ne 0) { throw "realms.ps1 $($Arguments -join ' ') failed ($LASTEXITCODE)" }
}

Write-Host '--- install (non-interactive)'
Invoke-Realms @('install', '-AcceptEula', '-NonInteractive', '-NoOwner')

Write-Host '--- second install must be a no-op'
$again = & $shell @shellArgs -File $script install -NonInteractive -NoOwner | Out-String
if ($again -notmatch 'Everything is up to date') { $failures.Add("re-install was not a no-op:`n$again") }

$props = Join-Path $server 'server.properties'
if ([IO.File]::ReadAllText($props) -match '\{\{') { $failures.Add('server.properties still has {{placeholders}}') }
$values = Read-ServerProperties $props
if ($values['level-seed'] -ne [string]$manifest.world.seed) { $failures.Add('seed not applied') }
if ($values['level-name'] -ne $manifest.world.level_name) { $failures.Add('level name not applied') }
Set-ServerProperty -Path $props -Name 'server-port' -Value $Port
Set-ServerProperty -Path $props -Name 'rcon.port' -Value $RconPort

Write-Host "--- start (port $Port)"
$out = Join-Path $Root 'smoke-console.log'
$startArgs = @{ FilePath = $shell; PassThru = $true; RedirectStandardOutput = $out; RedirectStandardError = "$out.err"
    ArgumentList = $shellArgs + @('-File', "`"$script`"", 'start', '-NonInteractive', '-MemoryGB', $MemoryGB) }
if ($onWindows) { $startArgs.WindowStyle = 'Hidden' }   # not supported on Linux and macOS
$proc = Start-Process @startArgs
$log = Join-Path (Join-Path $server 'logs') 'latest.log'
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
    if ($count -lt $datapacks.Count + 1) { $failures.Add("only $count datapacks enabled: $enabled") }
    $available = (Invoke-Realms @('rcon', 'datapack list available')) -join "`n"
    if ($available -match 'file/') { $failures.Add("datapacks present but not enabled: $available") }
    if ($isPaper) {
        # Fabric has no plugins command; its mods are checked in the log below.
        $plugins = (Invoke-Realms @('rcon', 'plugins')) -join "`n"
        Write-Host $plugins
        if ($plugins -notmatch "Server Plugins \($($addOns.Count)\)") { $failures.Add('not every plugin loaded') }
    }
    $seed = (Invoke-Realms @('rcon', 'seed')) -join ''
    if ($seed -notmatch [regex]::Escape("[$($manifest.world.seed)]")) { $failures.Add("world seed is not the pinned one: $seed") }
} finally {
    Write-Host '--- stop'
    Invoke-Realms @('stop')
    if (-not $proc.WaitForExit(120000)) {
        # PowerShell 7 can kill java (a child of realms.ps1) too; 5.1's .NET Framework can't.
        if ($PSVersionTable.PSEdition -eq 'Core') { $proc.Kill($true) } else { $proc.Kill() }
        $failures.Add('server did not exit after stop')
    }
}

$logText = Get-Content $log -Raw
if ($isPaper) {
    $bad = 'Error occurred while enabling', 'Could not load ''plugins', 'Unknown dependency', 'Ambiguous plugin name'
} else {
    $bad = 'Incompatible mods', 'Mixin apply', 'Exception in server tick loop', 'Minecraft Crash Report', 'This crash report has been saved'
    # Fabric Loader lists the mods it found ("Loading 42 mods:", counting Minecraft, Java and bundled
    # libraries too), possibly before the log file starts, so look at the console output as well.
    $boot = $logText
    if (Test-Path -LiteralPath $out) { $boot += "`n" + (Get-Content -LiteralPath $out -Raw) }
    if ($boot -match 'Loading (\d+) mods') {
        if ([int]$Matches[1] -lt $addOns.Count) { $failures.Add("Fabric loaded $($Matches[1]) mods, fewer than the $($addOns.Count) pinned") }
    } else { $failures.Add('no "Loading <N> mods" line from Fabric Loader') }
    $crashes = Join-Path $server 'crash-reports'
    if ((Test-Path -LiteralPath $crashes) -and @(Get-ChildItem -LiteralPath $crashes -File).Count) { $failures.Add('crash-reports/ is not empty') }
}
foreach ($pattern in $bad) {
    foreach ($m in [regex]::Matches($logText, "(?m)^.*$([regex]::Escape($pattern)).*$")) { $failures.Add("log: $($m.Value)") }
}
# LuckPerms answers commands on the console, not over RCON, so check its storage instead. On Fabric
# the line has no [LuckPerms] prefix.
$storageLine = if ($isPaper) { 'LuckPerms\] Loading storage provider\.\.\. \[YAML\]' } else { '(?i)Loading storage provider\.\.\. \[YAML\]' }
if ($logText -notmatch $storageLine) { $failures.Add('LuckPerms is not using the YAML ranks') }
foreach ($g in $ranks) {
    if (-not (Test-Path -LiteralPath (Join-Path $server "$($layout.LuckPerms)/groups/$g.yml"))) { $failures.Add("LuckPerms rank missing: $g") }
}
$kind = $layout.AddOns.TrimEnd('s')
foreach ($p in $addOns) {
    $jar = Join-Path $server "$($layout.AddOns)/$($p.file)"
    if (-not (Test-Path -LiteralPath $jar)) { $failures.Add("$kind jar missing: $($p.file)") }
}
foreach ($p in $datapacks) {
    $pack = Join-Path $server "$($manifest.world.level_name)/datapacks/$($p.file)"
    if (-not (Test-Path -LiteralPath $pack)) { $failures.Add("datapack missing: $($p.file)") }
}
# 26.1 logs 'All dimensions are saved' (Paper: 'Closing Server'); 26.3 logs 'Saving worlds' on the way down.
if ($logText -notmatch 'All dimensions are saved|Closing Server|Saving worlds') { $failures.Add('server did not shut down cleanly') }

if ($failures.Count) {
    Write-Host "`nSMOKE TEST FAILED ($($failures.Count)):" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 1
}
Write-Host "`nSMOKE TEST PASSED: $($layout.Description), $($addOns.Count) $($layout.AddOns), $($datapacks.Count) datapacks" -ForegroundColor Green
