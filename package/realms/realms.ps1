#Requires -Version 5.1
<#
.SYNOPSIS
    Installs, updates, starts, stops and backs up The Realms Minecraft server.

.DESCRIPTION
    Everything is downloaded from its official source (Adoptium, PaperMC, Modrinth) and checked
    against the hashes pinned in manifest.json before it is used. Running "install" again is safe:
    files that are already correct are skipped, and files from an older manifest are replaced.

    Layout next to this folder:
        server\    the Minecraft server (world, plugins, configs)
        java\      the Java runtime the server uses
        backups\   world backups made by "backup"

.EXAMPLE
    .\realms.ps1 start
    .\realms.ps1 install -AcceptEula -Owner Notch -NonInteractive
    .\realms.ps1 add-player Steve
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'install', 'stop', 'backup', 'add-player', 'status', 'rcon')]
    [string]$Command = 'start',

    [Parameter(Position = 1)]
    [string]$Name,

    # Agree to the Minecraft EULA without asking (https://aka.ms/MinecraftEULA).
    [switch]$AcceptEula,

    # Minecraft username to make admin on first install.
    [string]$Owner,

    # Don't set up an admin (and don't ask for one).
    [switch]$NoOwner,

    # Never prompt; fail instead.
    [switch]$NonInteractive,

    # Server memory in GB. 0 = pick from the computer's RAM. Also read from REALMS_MEMORY_GB.
    [int]$MemoryGB = 0
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is very slow with the progress bar on 5.1
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem

$RealmsDir = $PSScriptRoot
$Root = Split-Path $RealmsDir -Parent
$ServerDir = Join-Path $Root 'server'
$JavaDir = Join-Path $Root 'java'
$BackupDir = Join-Path $Root 'backups'
$DownloadDir = Join-Path $Root 'downloads'
$StateFile = Join-Path $ServerDir '.realms-state.json'
$UserAgent = 'gr8monk3ys/the-realms-server'
$Utf8 = New-Object System.Text.UTF8Encoding $false
$Manifest = [IO.File]::ReadAllText((Join-Path $RealmsDir 'manifest.json'), $Utf8) | ConvertFrom-Json

# ---------------------------------------------------------------- output

function Write-Step([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }
function Write-Ok([string]$Text) { Write-Host "    $Text" -ForegroundColor Green }
function Write-Note([string]$Text) { Write-Host "    $Text" -ForegroundColor Yellow }

function Read-Answer([string]$Question) {
    if ($NonInteractive) { throw "Needs an answer but -NonInteractive was given: $Question" }
    return (Read-Host $Question).Trim()
}

# ---------------------------------------------------------------- files

function Write-TextFile([string]$Path, [string]$Text) {
    New-Item -ItemType Directory -Force -Path (Split-Path $Path -Parent) | Out-Null
    [IO.File]::WriteAllText($Path, $Text, $Utf8)
}

function Read-JsonFile([string]$Path, $Default) {
    if (-not (Test-Path -LiteralPath $Path)) { return $Default }
    $text = [IO.File]::ReadAllText($Path, $Utf8)
    if (-not $text.Trim()) { return $Default }
    return $text | ConvertFrom-Json
}

function Write-JsonFile([string]$Path, $Value) {
    Write-TextFile $Path (ConvertTo-Json -InputObject $Value -Depth 10)
}

function Get-ExpectedHash($Entry) {
    foreach ($algo in 'sha512', 'sha256') {
        $value = $Entry.hashes.$algo
        if ($value) { return @{ Algorithm = $algo.ToUpper(); Value = $value.ToLower() } }
    }
    throw "No sha512/sha256 for $($Entry.file) in manifest.json"
}

function Get-Hash([string]$Path, [string]$Algorithm) {
    return (Get-FileHash -LiteralPath $Path -Algorithm $Algorithm).Hash.ToLower()
}

function Test-Artifact([string]$Path, $Entry) {
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    if ((Get-Item -LiteralPath $Path).Length -ne [long]$Entry.size) { return $false }
    $want = Get-ExpectedHash $Entry
    return (Get-Hash $Path $want.Algorithm) -eq $want.Value
}

# Downloads $Entry.url to $Path unless the file there already matches. Returns $true if it downloaded.
function Save-Artifact($Entry, [string]$Path) {
    if (Test-Artifact $Path $Entry) { return $false }
    New-Item -ItemType Directory -Force -Path (Split-Path $Path -Parent) | Out-Null
    $part = "$Path.part"
    $want = Get-ExpectedHash $Entry
    for ($try = 1; $try -le 3; $try++) {
        try {
            Invoke-WebRequest -Uri $Entry.url -OutFile $part -UserAgent $UserAgent -UseBasicParsing -TimeoutSec 600
            $got = Get-Hash $part $want.Algorithm
            if ($got -ne $want.Value) { throw "hash mismatch for $($Entry.file) (expected $($want.Value), got $got)" }
            Move-Item -LiteralPath $part -Destination $Path -Force
            return $true
        } catch {
            Remove-Item -LiteralPath $part -Force -ErrorAction SilentlyContinue
            if ($try -eq 3) { throw "Could not download $($Entry.file) from $($Entry.url): $_" }
            Write-Note "Download of $($Entry.file) failed ($_), retrying..."
            Start-Sleep -Seconds (5 * $try)
        }
    }
}

# ---------------------------------------------------------------- server.properties

function Read-Properties {
    $map = @{}
    $path = Join-Path $ServerDir 'server.properties'
    if (Test-Path -LiteralPath $path) {
        foreach ($line in [IO.File]::ReadAllLines($path, $Utf8)) {
            if ($line -match '^\s*([^#!][^=]*)=(.*)$') { $map[$Matches[1].Trim()] = $Matches[2] }
        }
    }
    return $map
}

function Get-ServerPort { $p = (Read-Properties)['server-port']; if ($p) { [int]$p } else { 25565 } }

function Test-ServerRunning {
    $client = New-Object Net.Sockets.TcpClient
    try { return $client.ConnectAsync('127.0.0.1', (Get-ServerPort)).Wait(1000) } catch { return $false } finally { $client.Close() }
}

# ---------------------------------------------------------------- RCON (talk to a running server)

function Invoke-Rcon([string[]]$Commands) {
    $props = Read-Properties
    if ($props['enable-rcon'] -ne 'true' -or -not $props['rcon.password']) { throw 'RCON is turned off in server.properties.' }
    $client = New-Object Net.Sockets.TcpClient
    $client.Connect('127.0.0.1', [int]$props['rcon.port'])
    $stream = $client.GetStream()
    $stream.ReadTimeout = 15000

    $send = {
        param([int]$Id, [int]$Type, [string]$Body)
        $bytes = $Utf8.GetBytes($Body)
        $buf = New-Object byte[] (14 + $bytes.Length)
        [BitConverter]::GetBytes([int](10 + $bytes.Length)).CopyTo($buf, 0)
        [BitConverter]::GetBytes($Id).CopyTo($buf, 4)
        [BitConverter]::GetBytes($Type).CopyTo($buf, 8)
        $bytes.CopyTo($buf, 12)
        $stream.Write($buf, 0, $buf.Length)
    }
    $readExactly = {
        param([int]$Count)
        $buf = New-Object byte[] $Count
        $off = 0
        while ($off -lt $Count) {
            $n = $stream.Read($buf, $off, $Count - $off)
            if ($n -le 0) { throw 'RCON connection closed' }
            $off += $n
        }
        return , $buf
    }
    $receive = {
        $len = [BitConverter]::ToInt32((& $readExactly 4), 0)
        $data = & $readExactly $len
        return @{ Id = [BitConverter]::ToInt32($data, 0); Body = $Utf8.GetString($data, 8, $len - 10) }
    }

    try {
        & $send 1 3 $props['rcon.password']
        if ((& $receive).Id -eq -1) { throw 'RCON password was rejected.' }
        # Long replies arrive split over several packets. Minecraft answers an unknown packet type
        # with a single reply, so a marker packet after each command shows where its reply ends.
        $out = @()
        $id = 10
        foreach ($c in $Commands) {
            & $send $id 2 $c
            & $send ($id + 1) 0 ''
            $body = ''
            while ($true) {
                $packet = & $receive
                if ($packet.Id -ne $id) { break }
                $body += $packet.Body
            }
            $out += ($body -replace '\xA7.', '')   # strip colour codes
            $id += 2
        }
        return $out
    } finally { $client.Close() }
}

# ---------------------------------------------------------------- players

function Get-Profile([string]$PlayerName) {
    foreach ($url in "https://api.minecraftservices.com/minecraft/profile/lookup/name/$PlayerName",
                     "https://api.mojang.com/users/profiles/minecraft/$PlayerName") {
        try {
            $p = Invoke-RestMethod -Uri $url -UserAgent $UserAgent -TimeoutSec 20
            if ($p.id) {
                $u = $p.id
                $uuid = '{0}-{1}-{2}-{3}-{4}' -f $u.Substring(0, 8), $u.Substring(8, 4), $u.Substring(12, 4), $u.Substring(16, 4), $u.Substring(20)
                return @{ Name = $p.name; Uuid = $uuid }
            }
        } catch { }
    }
    throw "Couldn't find a Minecraft Java account named '$PlayerName'. Check the spelling (it's the in-game name)."
}

function Add-ToList([string]$File, [hashtable]$Entry) {
    $path = Join-Path $ServerDir $File
    $list = @(Read-JsonFile $path @()) | Where-Object { $_ -and $_.uuid -ne $Entry.uuid }
    Write-JsonFile $path (@($list) + [pscustomobject]$Entry)
}

function Add-Owner([string]$PlayerName) {
    $p = Get-Profile $PlayerName
    Add-ToList 'whitelist.json' @{ uuid = $p.Uuid; name = $p.Name }
    Add-ToList 'ops.json' @{ uuid = $p.Uuid; name = $p.Name; level = 4; bypassesPlayerLimit = $true }
    # LuckPerms (YAML storage): put the owner in the admin group.
    $lp = Join-Path $ServerDir "plugins\LuckPerms\yaml-storage\users\$($p.Uuid).yml"
    if (-not (Test-Path -LiteralPath $lp)) {
        Write-TextFile $lp "uuid: $($p.Uuid)`nname: $($p.Name.ToLower())`nprimary-group: admin`nparents:`n- admin`n"
    }
    Write-Ok "$($p.Name) is the server admin (op + admin rank) and is on the whitelist."
    return $p.Name
}

# ---------------------------------------------------------------- install

function Get-State {
    $s = Read-JsonFile $StateFile $null
    if (-not $s) { $s = [pscustomobject]@{} }
    return $s
}

function Get-PatchId([string]$Dir) {
    $sb = New-Object System.Text.StringBuilder
    foreach ($f in Get-ChildItem -LiteralPath $Dir -Recurse -File | Sort-Object FullName) {
        $rel = $f.FullName.Substring($Dir.Length + 1).Replace('\', '/')
        [void]$sb.Append("$rel=$(Get-Hash $f.FullName SHA256);")
    }
    $bytes = $Utf8.GetBytes($sb.ToString())
    $sha = [Security.Cryptography.SHA256]::Create()
    return ([BitConverter]::ToString($sha.ComputeHash($bytes)) -replace '-', '').ToLower()
}

# Overwrites files inside a zip with the files from a patch folder (same relative paths).
function Invoke-ZipPatch([string]$Zip, [string]$Dir) {
    $archive = [IO.Compression.ZipFile]::Open($Zip, [IO.Compression.ZipArchiveMode]::Update)
    try {
        foreach ($f in Get-ChildItem -LiteralPath $Dir -Recurse -File) {
            $rel = $f.FullName.Substring($Dir.Length + 1).Replace('\', '/')
            $old = $archive.GetEntry($rel)
            if ($old) { $old.Delete() }
            $entry = $archive.CreateEntry($rel)
            $out = $entry.Open()
            try { $bytes = [IO.File]::ReadAllBytes($f.FullName); $out.Write($bytes, 0, $bytes.Length) } finally { $out.Dispose() }
        }
    } finally { $archive.Dispose() }
}

function Install-Java {
    $home_ = Join-Path $JavaDir $Manifest.java.version
    $exe = Join-Path $home_ 'bin\java.exe'
    if (Test-Path -LiteralPath $exe) { return $exe }
    Write-Step "Downloading Java ($($Manifest.java.vendor) $($Manifest.java.version), $([math]::Round($Manifest.java.size / 1MB)) MB)"
    $zip = Join-Path $DownloadDir $Manifest.java.file
    [void](Save-Artifact $Manifest.java $zip)
    $tmp = Join-Path $JavaDir '.extract'
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    [IO.Compression.ZipFile]::ExtractToDirectory($zip, $tmp)
    $inner = Get-ChildItem -LiteralPath $tmp -Directory | Select-Object -First 1
    Remove-Item -LiteralPath $home_ -Recurse -Force -ErrorAction SilentlyContinue
    Move-Item -LiteralPath $inner.FullName -Destination $home_
    Remove-Item -LiteralPath $tmp, $zip -Recurse -Force
    # Old Java versions from earlier manifests.
    Get-ChildItem -LiteralPath $JavaDir -Directory | Where-Object { $_.Name -ne $Manifest.java.version } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Ok 'Java ready.'
    return $exe
}

function Confirm-Eula {
    $path = Join-Path $ServerDir 'eula.txt'
    if ((Test-Path -LiteralPath $path) -and ([IO.File]::ReadAllText($path) -match 'eula\s*=\s*true')) { return }
    if (-not $AcceptEula) {
        Write-Host ''
        Write-Host 'Minecraft servers require you to agree to the Minecraft EULA:' -ForegroundColor White
        Write-Host '    https://aka.ms/MinecraftEULA' -ForegroundColor White
        $a = Read-Answer 'Do you agree to it? Type YES and press Enter'
        if ($a -notmatch '^(y|yes)$') { throw 'The server cannot run unless you agree to the Minecraft EULA.' }
    }
    Write-TextFile $path "# Agreed via The Realms installer on $(Get-Date -Format s)`neula=true`n"
}

function Install-Defaults {
    $defaults = Join-Path $RealmsDir 'defaults'
    foreach ($f in Get-ChildItem -LiteralPath $defaults -Recurse -File) {
        $rel = $f.FullName.Substring($defaults.Length + 1)
        $dest = Join-Path $ServerDir $rel
        if (Test-Path -LiteralPath $dest) { continue }
        if ($rel -eq 'server.properties') {
            $bytes = New-Object byte[] 24
            [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
            $pw = ([Convert]::ToBase64String($bytes)) -replace '[+/=]', 'x'
            $text = [IO.File]::ReadAllText($f.FullName, $Utf8).
                Replace('{{RCON_PASSWORD}}', $pw).
                Replace('{{SEED}}', [string]$Manifest.world.seed).
                Replace('{{LEVEL_NAME}}', $Manifest.world.level_name)
            Write-TextFile $dest $text
        } else {
            New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
            Copy-Item -LiteralPath $f.FullName -Destination $dest
        }
    }
}

function Install-Server {
    if (Test-ServerRunning) { throw 'The server is running. Stop it first (type "stop" in its window, or run Stop Server).' }
    New-Item -ItemType Directory -Force -Path $ServerDir | Out-Null
    $state = Get-State
    $firstInstall = -not $state.version

    Confirm-Eula
    $java = Install-Java

    Write-Step "Checking server files for $($Manifest.name) $($Manifest.version) (Minecraft $($Manifest.minecraft))"
    $n = 0
    if (Save-Artifact $Manifest.server (Join-Path $ServerDir 'paper.jar')) { Write-Ok "Paper build $($Manifest.server.build)"; $n++ }

    $pluginDir = Join-Path $ServerDir 'plugins'
    foreach ($p in $Manifest.plugins) {
        if (Save-Artifact $p (Join-Path $pluginDir $p.file)) { Write-Ok "plugin  $($p.slug) $($p.version)"; $n++ }
    }
    $keep = @($Manifest.plugins | ForEach-Object { $_.file })
    foreach ($old in @($state.plugins)) {
        if ($old -and $keep -notcontains $old) { Remove-Item -LiteralPath (Join-Path $pluginDir $old) -Force -ErrorAction SilentlyContinue; Write-Note "removed old plugin $old" }
    }

    $packDir = Join-Path $ServerDir "$($Manifest.world.level_name)\datapacks"
    $patched = @{}
    foreach ($d in $Manifest.datapacks) {
        $dest = Join-Path $packDir $d.file
        if (-not $d.patch) {
            if (Save-Artifact $d $dest) { Write-Ok "datapack $($d.slug) $($d.version)"; $n++ }
            continue
        }
        # Patched packs: the file on disk differs from the download, so remember what we produced.
        $patchDir = Join-Path $RealmsDir $d.patch.Replace('/', '\')
        $id = "$((Get-ExpectedHash $d).Value):$(Get-PatchId $patchDir)"
        $prev = if ($state.patched) { $state.patched.($d.file) } else { $null }
        if ($prev -and $prev.id -eq $id -and (Test-Path -LiteralPath $dest) -and (Get-Hash $dest SHA256) -eq $prev.sha256) {
            $patched[$d.file] = $prev
            continue
        }
        $raw = Join-Path $DownloadDir $d.file
        [void](Save-Artifact $d $raw)
        New-Item -ItemType Directory -Force -Path $packDir | Out-Null
        Copy-Item -LiteralPath $raw -Destination $dest -Force
        Invoke-ZipPatch $dest $patchDir
        Remove-Item -LiteralPath $raw -Force
        $patched[$d.file] = @{ id = $id; sha256 = (Get-Hash $dest SHA256) }
        Write-Ok "datapack $($d.slug) $($d.version) (patched)"
        $n++
    }
    $keep = @($Manifest.datapacks | ForEach-Object { $_.file })
    foreach ($old in @($state.datapacks)) {
        if ($old -and $keep -notcontains $old) { Remove-Item -LiteralPath (Join-Path $packDir $old) -Force -ErrorAction SilentlyContinue; Write-Note "removed old datapack $old" }
    }
    if ($n -eq 0) { Write-Ok 'Everything is up to date.' }

    Install-Defaults

    $ownerName = $state.owner
    if (-not $ownerName -and -not $NoOwner) {
        $who = $Owner
        if (-not $who -and -not $NonInteractive) {
            Write-Host ''
            $who = Read-Answer 'What is YOUR Minecraft username? (you will be the admin; press Enter to skip)'
        }
        if ($who) { $ownerName = Add-Owner $who }
    }

    Write-JsonFile $StateFile @{
        version = $Manifest.version
        java = $java
        owner = $ownerName
        plugins = $Manifest.plugins | ForEach-Object { $_.file }
        datapacks = $Manifest.datapacks | ForEach-Object { $_.file }
        patched = $patched
    }
    Remove-Item -LiteralPath $DownloadDir -Recurse -Force -ErrorAction SilentlyContinue
    if ($firstInstall) { Write-Ok 'Install finished.' }
    return $java
}

# ---------------------------------------------------------------- start / stop / backup

function Get-MemoryGB {
    if ($MemoryGB -gt 0) { return $MemoryGB }
    if ($env:REALMS_MEMORY_GB) { return [int]$env:REALMS_MEMORY_GB }
    $total = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB
    if ($total -le 8.5) { return 3 }
    if ($total -le 12.5) { return 4 }
    if ($total -le 16.5) { return 5 }
    return 6
}

function Start-Server {
    $java = Install-Server
    $gb = Get-MemoryGB
    # Aikar's G1 flags (https://docs.papermc.io/paper/aikars-flags).
    $jvm = @("-Xms${gb}G", "-Xmx${gb}G", '-XX:+UseG1GC', '-XX:+ParallelRefProcEnabled', '-XX:MaxGCPauseMillis=200',
        '-XX:+UnlockExperimentalVMOptions', '-XX:+DisableExplicitGC', '-XX:+AlwaysPreTouch', '-XX:G1NewSizePercent=30',
        '-XX:G1MaxNewSizePercent=40', '-XX:G1HeapRegionSize=8M', '-XX:G1ReservePercent=20', '-XX:G1HeapWastePercent=5',
        '-XX:G1MixedGCCountTarget=4', '-XX:InitiatingHeapOccupancyPercent=15', '-XX:G1MixedGCLiveThresholdPercent=90',
        '-XX:G1RSetUpdatingPauseTimePercent=5', '-XX:SurvivorRatio=32', '-XX:+PerfDisableSharedMem',
        '-XX:MaxTenuringThreshold=1', '-Dusing.aikars.flags=https://mcflags.emc.gs', '-Daikars.new.flags=true',
        '-jar', 'paper.jar', '--nogui')
    Write-Host ''
    Write-Step "Starting The Realms with $gb GB of memory"
    Write-Host '    Friends join at the address shown by playit.gg (see READ ME FIRST.txt).' -ForegroundColor White
    Write-Host '    To stop the server safely, type  stop  here and press Enter.' -ForegroundColor White
    Write-Host '    (Closing this window without "stop" can lose the last few minutes of the world.)' -ForegroundColor White
    Write-Host ''
    Push-Location $ServerDir
    try { & $java @jvm; $code = $LASTEXITCODE } finally { Pop-Location }
    if ($code -ne 0) { throw "The server stopped with an error (exit code $code). See the messages above, or server\logs\latest.log." }
    Write-Step 'Server stopped.'
}

function Stop-Server {
    if (-not (Test-ServerRunning)) { Write-Ok 'The server is not running.'; return }
    [void](Invoke-Rcon @('stop'))
    for ($i = 0; $i -lt 60 -and (Test-ServerRunning); $i++) { Start-Sleep -Seconds 2 }
    Write-Ok 'Server stopped.'
}

function Backup-Server {
    if (-not (Test-Path -LiteralPath $ServerDir)) { throw 'Nothing to back up yet - the server has never been installed.' }
    $running = Test-ServerRunning
    $stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
    $dest = Join-Path $BackupDir $stamp
    Write-Step "Backing up to backups\$stamp"
    if ($running) { [void](Invoke-Rcon @('save-off', 'save-all flush')); Start-Sleep -Seconds 3 }
    try {
        # Worlds, configs and plugin data. Skips things the installer can re-download or the server rebuilds.
        & robocopy $ServerDir $dest /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP `
            /XD (Join-Path $ServerDir 'libraries') (Join-Path $ServerDir 'versions') (Join-Path $ServerDir 'cache') `
                (Join-Path $ServerDir 'logs') (Join-Path $ServerDir 'bluemap') (Join-Path $ServerDir 'plugins\.paper-remapped') `
            /XF '*.jar' 'session.lock' | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy failed with exit code $LASTEXITCODE" }
    } finally {
        if ($running) { [void](Invoke-Rcon @('save-on')) }
    }
    # Keep the newest 14 backups.
    Get-ChildItem -LiteralPath $BackupDir -Directory | Sort-Object Name -Descending | Select-Object -Skip 14 |
        Remove-Item -Recurse -Force
    $size = (Get-ChildItem -LiteralPath $dest -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
    Write-Ok ("Backup done ({0:N0} MB)." -f $size)
}

function Add-Player([string]$PlayerName) {
    if (-not $PlayerName) { $PlayerName = Read-Answer "Friend's Minecraft username" }
    if (Test-ServerRunning) {
        Invoke-Rcon @("whitelist add $PlayerName") | ForEach-Object { Write-Ok $_ }
    } else {
        $p = Get-Profile $PlayerName
        Add-ToList 'whitelist.json' @{ uuid = $p.Uuid; name = $p.Name }
        Write-Ok "$($p.Name) can now join."
    }
}

function Show-Status {
    $state = Get-State
    Write-Host "$($Manifest.name) $($Manifest.version) - Minecraft $($Manifest.minecraft), Paper build $($Manifest.server.build)"
    Write-Host "Installed: $(if ($state.version) { $state.version } else { 'no' })    Admin: $($state.owner)"
    Write-Host "Running:   $(Test-ServerRunning)    Plugins: $(@($Manifest.plugins).Count)    Datapacks: $(@($Manifest.datapacks).Count)"
}

switch ($Command) {
    'start' { Start-Server }
    'install' { [void](Install-Server) }
    'stop' { Stop-Server }
    'backup' { Backup-Server }
    'add-player' { Add-Player $Name }
    'status' { Show-Status }
    'rcon' { Invoke-Rcon @($Name) | ForEach-Object { Write-Output $_ } }
}
