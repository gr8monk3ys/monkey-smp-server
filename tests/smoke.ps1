#Requires -Version 5.1
<#
.SYNOPSIS
    End-to-end test: install the packaged server, boot it, check every plugin (Paper) or mod (Fabric)
    and datapack loaded, stop it.

.DESCRIPTION
    Runs monkey.ps1 with the PowerShell that runs this script: Windows PowerShell 5.1 (powershell.exe)
    or PowerShell 7 (pwsh, on Windows, Linux or macOS).

    Before it installs and again before it starts, it stops if any of its ports is already in use: the
    game, RCON and map TCP ports and the voice chat UDP port. Another server on the same machine (a test
    boot in another folder included) holding one would make this one shut down or answer for it.

.EXAMPLE
    # From an unzipped release (or a copy of package/):
    .\tests\smoke.ps1 -Root C:\temp\MonkeySMP-Server -Port 25566 -RconPort 25576 -VoicePort 24455 -MapPort 8101
    pwsh tests/smoke.ps1 -Root /tmp/MonkeySMP-Server -MemoryGB 4
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$Root,
    [int]$Port = 25565,
    [int]$RconPort = 25575,
    # Simple Voice Chat (UDP) and the BlueMap web map; the defaults are the mods' own (and Monkey.psm1's).
    [int]$VoicePort = 24454,
    [int]$MapPort = 8100,
    [int]$MemoryGB = 3,
    [int]$TimeoutMinutes = 20
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path $Root).Path
$script = Join-Path (Join-Path $Root 'monkey') 'monkey.ps1'
$server = Join-Path $Root 'server'
$onWindows = [IO.Path]::DirectorySeparatorChar -eq '\'
# monkey.ps1 runs in a new process of this same PowerShell (powershell.exe, or pwsh on any platform).
$shell = if ($PSVersionTable.PSEdition -eq 'Core') { (Get-Process -Id $PID).Path } else { 'powershell.exe' }
$shellArgs = @('-NoProfile')
if ($onWindows) { $shellArgs += @('-ExecutionPolicy', 'Bypass') }
# The package's own module: one server.properties parser for the installer and this test.
Import-Module (Join-Path (Join-Path $Root 'monkey') 'Monkey.psm1') -Force
$manifest = (New-MonkeyContext -Root $Root).Manifest
$layout = Get-ServerLayout -Manifest $manifest
$isPaper = $layout.Type -eq 'paper'
# The plugins (Paper) or mods (Fabric) the manifest pins, and the folder they go in.
$addOns = @($manifest.($layout.AddOns) | Where-Object { $_ })
$datapacks = @($manifest.datapacks | Where-Object { $_ })
# Ranks are whatever LuckPerms groups the Defaults ship, in the server type's LuckPerms storage folder.
$ranks = @(Get-ChildItem -LiteralPath (Join-Path $Root "monkey/defaults/$($layout.LuckPerms)/groups") -Filter *.yml |
    ForEach-Object { $_.BaseName })
if (-not $ranks.Count) { throw 'No LuckPerms ranks found in the package Defaults' }
Write-Host "--- $($manifest.name) $($manifest.version): $($layout.Description), $($addOns.Count) $($layout.AddOns), $($datapacks.Count) datapacks"
$failures = New-Object System.Collections.Generic.List[string]

function Invoke-Monkey([string[]]$Arguments) {
    & $shell @shellArgs -File $script @Arguments
    if ($LASTEXITCODE -ne 0) { throw "monkey.ps1 $($Arguments -join ' ') failed ($LASTEXITCODE)" }
}

# Who holds a local port: '' if nobody, else a description ('java pid 1234' where the OS says).
function Get-PortHolder([string]$Protocol, [int]$Number) {
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        # Windows: ask the TCP/IP stack.
        $found = @(if ($Protocol -eq 'udp') { Get-NetUDPEndpoint -LocalPort $Number -ErrorAction SilentlyContinue }
            else { Get-NetTCPConnection -LocalPort $Number -State Listen, Bound -ErrorAction SilentlyContinue })
        if (-not $found.Count) { return '' }
        $id = $found[0].OwningProcess
        $name = (Get-Process -Id $id -ErrorAction SilentlyContinue).ProcessName
        return "$name pid $id".Trim()
    }
    # Linux and macOS (PowerShell 7): something answers on it, or it can't be bound.
    if ($Protocol -eq 'tcp') {
        $client = New-Object Net.Sockets.TcpClient
        try { $answers = $client.ConnectAsync('127.0.0.1', $Number).Wait(1000) } catch { $answers = $false } finally { $client.Close() }
        if ($answers) { return 'another program' }
    }
    try {
        if ($Protocol -eq 'udp') { (New-Object Net.Sockets.UdpClient $Number).Close() }
        else { $listener = New-Object Net.Sockets.TcpListener ([Net.IPAddress]::Any), $Number; $listener.Start(); $listener.Stop() }
        return ''
    } catch { return 'another program' }
}

# Throws, naming each one, if any of $Ports (@{ Protocol; Number; What; Parameter }) is in use.
function Assert-PortsFree([hashtable[]]$Ports) {
    $busy = foreach ($p in $Ports) {
        $holder = Get-PortHolder $p.Protocol $p.Number
        if ($holder) { "  $($p.What) port $($p.Number)/$($p.Protocol) ($($p.Parameter)), held by $holder" }
    }
    if ($busy) {
        throw ("Port(s) already in use on this machine:`n$($busy -join "`n")`n" +
            'Stop the server that holds them, or pick free ports, e.g. -Port 25568 -RconPort 25578 -VoicePort 24468 -MapPort 8108.')
    }
}

# Sets the port in BlueMap's webserver.conf (HOCON), keeping the rest of the file; creates it if missing.
function Set-MapPort([string]$Path, [int]$Number) {
    $text = if (Test-Path -LiteralPath $Path) { [IO.File]::ReadAllText($Path) } else { '' }
    $portLine = '(?m)^[ \t]*port[ \t]*[:=][^\r\n]*'
    if ($text -match $portLine) { $text = $text -replace $portLine, "port: $Number" } else { $text += "`nport: $Number`n" }
    New-Item -ItemType Directory -Force -Path (Split-Path $Path -Parent) | Out-Null
    [IO.File]::WriteAllText($Path, $text)
}

# Whether this boot has logged "Done". A re-run in the same folder finds the last boot's latest.log, "Done"
# line and all, until the new server rotates it, so a log last written before $Since doesn't count.
function Test-BootDone([string]$Log, [datetime]$Since) {
    $item = Get-Item -LiteralPath $Log -ErrorAction SilentlyContinue
    return [bool]($item -and $item.LastWriteTime -gt $Since -and (Select-String -LiteralPath $Log -Pattern 'Done \(' -Quiet))
}

# Simple Voice Chat stops the whole server when it can't bind its UDP port, and so does BlueMap with its
# map port; on a taken RCON port this test would talk to (and stop) the other server.
$ports = @(
    @{ Protocol = 'tcp'; Number = $Port; What = 'game'; Parameter = '-Port' }
    @{ Protocol = 'tcp'; Number = $RconPort; What = 'RCON'; Parameter = '-RconPort' }
    @{ Protocol = 'tcp'; Number = $MapPort; What = 'BlueMap web map'; Parameter = '-MapPort' }
    @{ Protocol = 'udp'; Number = $VoicePort; What = 'Simple Voice Chat'; Parameter = '-VoicePort' }
)
Write-Host "--- ports free? game $Port, RCON $RconPort, map $MapPort (TCP), voice $VoicePort (UDP)"
Assert-PortsFree $ports

Write-Host '--- install (non-interactive)'
Invoke-Monkey @('install', '-AcceptEula', '-NonInteractive', '-NoOwner')

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
# Voice chat and the map read their ports from their own config files, which the mods write on first boot
# (the package ships neither), so create them now; each mod uses its defaults for the settings left out.
$configDir = if ($isPaper) { 'plugins' } else { 'config' }
Set-ServerProperty -Path (Join-Path $server "$configDir/voicechat/voicechat-server.properties") -Name 'port' -Value $VoicePort
Set-MapPort (Join-Path $server $(if ($isPaper) { 'plugins/BlueMap/webserver.conf' } else { 'config/bluemap/webserver.conf' })) $MapPort

# Again: another boot may have taken one during the install.
Assert-PortsFree $ports
Write-Host "--- start (port $Port)"
$out = Join-Path $Root 'smoke-console.log'
$startArgs = @{ FilePath = $shell; PassThru = $true; RedirectStandardOutput = $out; RedirectStandardError = "$out.err"
    ArgumentList = $shellArgs + @('-File', "`"$script`"", 'start', '-NonInteractive', '-MemoryGB', $MemoryGB) }
if ($onWindows) { $startArgs.WindowStyle = 'Hidden' }   # not supported on Linux and macOS
$log = Join-Path (Join-Path $server 'logs') 'latest.log'
$startTime = Get-Date
$proc = Start-Process @startArgs
$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
$started = $false
while ((Get-Date) -lt $deadline -and -not $proc.HasExited) {
    if (Test-BootDone $log $startTime) { $started = $true; break }
    Start-Sleep -Seconds 5
}
if (-not $started) {
    if (Test-Path $out) { Get-Content $out -Tail 60 }
    throw "Server did not finish starting within $TimeoutMinutes minutes (exited: $($proc.HasExited))"
}
$doneLine = (Select-String -Path $log -Pattern 'Done \(' | Select-Object -First 1).Line
Write-Host "--- started: $doneLine"

# Right after "Done" a slow runner can still be busy (spawn chunks, map and LOD threads) and drop the first
# RCON connection, so wait until RCON answers before checking anything.
$rconDeadline = (Get-Date).AddMinutes(3)
while ($true) {
    # The child's stderr must not become a terminating error under 'Stop' (Windows PowerShell 5.1 turns
    # redirected native stderr into error records), or the first dropped connection ends the test.
    $ErrorActionPreference = 'Continue'
    try { & $shell @shellArgs -File $script rcon 'list' 2>&1 | Out-Null; $code = $LASTEXITCODE }
    finally { $ErrorActionPreference = 'Stop' }
    if ($code -eq 0) { break }
    if ($proc.HasExited) {
        if (Test-Path $out) { Get-Content $out -Tail 30 }
        throw "The server stopped by itself after `"Done`" (its console output is above and in $out)"
    }
    if ((Get-Date) -gt $rconDeadline) { throw 'RCON did not answer within 3 minutes of "Done"' }
    Write-Host '    RCON not answering yet, retrying in 10 s'
    Start-Sleep -Seconds 10
}

try {
    # Paper shortens long replies with "...", so check the count and that nothing was left disabled.
    $enabled = (Invoke-Monkey @('rcon', 'datapack list enabled')) -join "`n"
    $count = if ($enabled -match 'There are (\d+) data pack') { [int]$Matches[1] } else { 0 }
    if ($count -lt $datapacks.Count + 1) { $failures.Add("only $count datapacks enabled: $enabled") }
    $available = (Invoke-Monkey @('rcon', 'datapack list available')) -join "`n"
    if ($available -match 'file/') { $failures.Add("datapacks present but not enabled: $available") }
    if ($isPaper) {
        # Fabric has no plugins command; its mods are checked in the log below.
        $plugins = (Invoke-Monkey @('rcon', 'plugins')) -join "`n"
        Write-Host $plugins
        if ($plugins -notmatch "Server Plugins \($($addOns.Count)\)") { $failures.Add('not every plugin loaded') }
    }
    $seed = (Invoke-Monkey @('rcon', 'seed')) -join ''
    if ($seed -notmatch [regex]::Escape("[$($manifest.world.seed)]")) { $failures.Add("world seed is not the pinned one: $seed") }
} finally {
    Write-Host '--- stop'
    Invoke-Monkey @('stop')
    if (-not $proc.WaitForExit(120000)) {
        # PowerShell 7 can kill java (a child of monkey.ps1) too; 5.1's .NET Framework can't.
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
