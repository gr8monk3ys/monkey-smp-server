#Requires -Version 5.1
<#
.SYNOPSIS
    The Realms installer and launcher: installs, updates, starts, stops and backs up the server.

.DESCRIPTION
    Every public function takes one context object (New-RealmsContext) instead of script globals.
    The context carries the folder layout, the parsed manifest and two adapters, which are the only
    seams to the outside world:

        Fetch          { param([string]$Url, [string]$OutFile) }  downloads one URL to one file.
                       Hash checks, retries and .part handling stay inside this module.
        ProfileLookup  { param([string]$Name) }  returns @{ Name; Uuid } or throws.

    Production uses the web adapters below; tests pass adapters that read local fixtures.
    Importing this module has no side effects: nothing is downloaded, written or changed until a
    function is called.

    Must stay plain ASCII and Windows PowerShell 5.1 compatible (docs/adr/0003).
#>

# Module scope only: callers keep their own preference.
$ErrorActionPreference = 'Stop'

$script:UserAgent = 'gr8monk3ys/the-realms-server'
$script:Utf8 = New-Object System.Text.UTF8Encoding $false
# Defaults that are rendered with Expand-Template instead of copied byte for byte.
$script:TemplateFiles = @('server.properties')
$script:KeepBackups = 14

# What each kind of server runs and where its add-ons live (relative to server\).
#   Jar        the file name the server entry is saved as, and what java -jar runs
#   Arguments  what follows the jar on the command line
#   AddOns     the manifest group it loads add-ons from ('plugins' or 'mods'); datapacks work on both
#   LuckPerms  the LuckPerms YAML storage folder (ranks in groups\, players in users\)
$script:ServerTypes = @{
    paper  = @{ Name = 'Paper'; Jar = 'paper.jar'; Arguments = @('--nogui'); AddOns = 'plugins'; LuckPerms = 'plugins\LuckPerms\yaml-storage' }
    fabric = @{ Name = 'Fabric'; Jar = 'fabric-server-launch.jar'; Arguments = @('nogui'); AddOns = 'mods'; LuckPerms = 'mods\luckperms\yaml-storage' }
}
# The groups of managed files in the manifest, and the word used for one of them in messages.
$script:Groups = [ordered]@{ plugins = 'plugin'; mods = 'mod'; datapacks = 'datapack' }

# ================================================================ output

function Write-Step([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }
function Write-Ok([string]$Text) { Write-Host "    $Text" -ForegroundColor Green }
function Write-Note([string]$Text) { Write-Host "    $Text" -ForegroundColor Yellow }

function Read-Answer($Context, [string]$Question) {
    if ($Context.NonInteractive) { throw "Needs an answer but -NonInteractive was given: $Question" }
    return (Read-Host $Question).Trim()
}

# ================================================================ files

function Write-TextFile([string]$Path, [string]$Text) {
    New-Item -ItemType Directory -Force -Path (Split-Path $Path -Parent) | Out-Null
    [IO.File]::WriteAllText($Path, $Text, $script:Utf8)
}

function Read-JsonFile([string]$Path, $Default) {
    if (-not (Test-Path -LiteralPath $Path)) { return $Default }
    $text = [IO.File]::ReadAllText($Path, $script:Utf8)
    if (-not $text.Trim()) { return $Default }
    return $text | ConvertFrom-Json
}

function Write-JsonFile([string]$Path, $Value) {
    Write-TextFile $Path (ConvertTo-Json -InputObject $Value -Depth 10)
}

# Files under $Dir with their path relative to it ('a/b.txt', forward slashes, as inside a zip).
function Get-RelativeFile([string]$Dir) {
    $base = (Get-Item -LiteralPath $Dir).FullName.TrimEnd('\')
    foreach ($f in Get-ChildItem -LiteralPath $base -Recurse -File | Sort-Object FullName) {
        [pscustomobject]@{ Rel = $f.FullName.Substring($base.Length + 1).Replace('\', '/'); FullName = $f.FullName }
    }
}

function Get-Hash([string]$Path, [string]$Algorithm) {
    return (Get-FileHash -LiteralPath $Path -Algorithm $Algorithm).Hash.ToLower()
}

function Use-Zip { Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem }

# ================================================================ adapters (production)

function Invoke-WebFetch {
    param([string]$Url, [string]$OutFile)
    $ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is very slow with the progress bar on 5.1
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $Url -OutFile $OutFile -UserAgent $script:UserAgent -UseBasicParsing -TimeoutSec 600
}

function Get-MojangProfile {
    param([string]$Name)
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    foreach ($url in "https://api.minecraftservices.com/minecraft/profile/lookup/name/$Name",
                     "https://api.mojang.com/users/profiles/minecraft/$Name") {
        try {
            $p = Invoke-RestMethod -Uri $url -UserAgent $script:UserAgent -TimeoutSec 20
            if ($p.id) {
                $u = $p.id
                $uuid = '{0}-{1}-{2}-{3}-{4}' -f $u.Substring(0, 8), $u.Substring(8, 4), $u.Substring(12, 4), $u.Substring(16, 4), $u.Substring(20)
                return @{ Name = $p.name; Uuid = $uuid }
            }
        } catch { Write-Verbose "Profile lookup via $url failed: $_" }   # try the next API
    }
    throw "Couldn't find a Minecraft Java account named '$Name'. Check the spelling (it's the in-game name)."
}

# ================================================================ context

<#
.SYNOPSIS
    Builds the context every other function takes: folders, manifest and adapters.
.PARAMETER Root
    The unzipped server package folder. server\, java\, backups\ and downloads\ live under it.
.PARAMETER RealmsDir
    The folder holding manifest.json, defaults\ and patches\. Defaults to Root\realms.
.PARAMETER Manifest
    The parsed manifest. Defaults to RealmsDir\manifest.json.
#>
function New-RealmsContext {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string]$Root,
        [string]$RealmsDir,
        $Manifest,
        [scriptblock]$Fetch,
        [scriptblock]$ProfileLookup,
        [switch]$NonInteractive
    )
    $Root = (Resolve-Path -LiteralPath $Root).ProviderPath
    if (-not $RealmsDir) { $RealmsDir = Join-Path $Root 'realms' }
    $RealmsDir = (Resolve-Path -LiteralPath $RealmsDir).ProviderPath
    if (-not $Manifest) {
        $Manifest = Read-JsonFile (Join-Path $RealmsDir 'manifest.json') $null
        if (-not $Manifest) { throw "manifest.json is missing or empty in $RealmsDir" }
    }
    if (-not $Fetch) { $Fetch = ${function:Invoke-WebFetch} }
    if (-not $ProfileLookup) { $ProfileLookup = ${function:Get-MojangProfile} }
    $serverDir = Join-Path $Root 'server'
    return [pscustomobject]@{
        Root           = $Root
        RealmsDir      = $RealmsDir
        ServerDir      = $serverDir
        JavaDir        = Join-Path $Root 'java'
        BackupDir      = Join-Path $Root 'backups'
        DownloadDir    = Join-Path $Root 'downloads'
        StateFile      = Join-Path $serverDir '.realms-state.json'
        Manifest       = $Manifest
        Fetch          = $Fetch
        ProfileLookup  = $ProfileLookup
        NonInteractive = [bool]$NonInteractive
    }
}

# The world folder name. Always the manifest's, so the datapack folder and server.properties agree.
function Get-LevelName($Context) {
    $name = [string]$Context.Manifest.world.level_name
    if (-not $name) { throw 'manifest.json has no world.level_name' }
    return $name
}

<#
.SYNOPSIS
    What the manifest's server type runs and where its files go. Throws on an unknown type.
.OUTPUTS
    Type ('paper' | 'fabric'), Name, Jar, Arguments, AddOns ('plugins' | 'mods'),
    LuckPerms (YAML storage folder relative to server\) and Description ('Paper build 74', 'Fabric loader 0.19.5').
#>
function Get-ServerLayout {
    param([Parameter(Mandatory)] $Manifest)
    $server = $Manifest.server
    $type = ([string]$server.type).ToLower()
    if (-not $type -or -not $script:ServerTypes.ContainsKey($type)) {
        throw "manifest.json has server type '$($server.type)', but this installer only knows 'paper' and 'fabric'. Download the latest release of The Realms."
    }
    $t = $script:ServerTypes[$type]
    $description = if ($type -eq 'paper') { "Paper build $($server.build)" } else { "Fabric loader $($server.loader)" }
    return [pscustomobject]@{
        Type        = $type
        Name        = $t.Name
        Jar         = $t.Jar
        Arguments   = @($t.Arguments)
        AddOns      = $t.AddOns
        LuckPerms   = $t.LuckPerms
        Description = $description
    }
}

# The folder a group of managed files goes in. Folders are fixed per group; the server type only
# decides which groups may have entries.
function Get-GroupFolder($Context, [string]$Group) {
    switch ($Group) {
        'plugins' { return Join-Path $Context.ServerDir 'plugins' }
        'mods' { return Join-Path $Context.ServerDir 'mods' }
        'datapacks' { return Join-Path $Context.ServerDir "$(Get-LevelName $Context)\datapacks" }
    }
    throw "Unknown group of files: $Group"
}

# ================================================================ artifacts

<#
.SYNOPSIS
    The hash a manifest entry must match: @{ Algorithm = 'SHA512' | 'SHA256'; Value = <lowercase hex> }.
#>
function Get-ExpectedHash {
    param([Parameter(Mandatory)] $Entry)
    foreach ($algo in 'sha512', 'sha256') {
        $value = $Entry.hashes.$algo
        if ($value) { return @{ Algorithm = $algo.ToUpper(); Value = ([string]$value).ToLower() } }
    }
    throw "No sha512/sha256 for $($Entry.file) in manifest.json"
}

# File names come from upstream and may contain [ ] (e.g. "Player Corpses 3.7 [1.21.9+].zip"), which
# PowerShell cmdlets treat as wildcards. Moves and copies of artifacts go through .NET, which doesn't.
function Copy-FileExact([string]$From, [string]$To, [switch]$Move) {
    if ([IO.File]::Exists($To)) { [IO.File]::Delete($To) }
    if ($Move) { [IO.File]::Move($From, $To) } else { [IO.File]::Copy($From, $To) }
}

function Test-Artifact([string]$Path, $Entry) {
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    if ((Get-Item -LiteralPath $Path).Length -ne [long]$Entry.size) { return $false }
    $want = Get-ExpectedHash $Entry
    return (Get-Hash $Path $want.Algorithm) -eq $want.Value
}

# Downloads $Entry.url to $Path through the Fetch adapter unless the file there already matches.
# Only a file that matches the pinned hash ever reaches $Path. Returns $true if it downloaded.
function Save-Artifact($Context, $Entry, [string]$Path) {
    if (Test-Artifact $Path $Entry) { return $false }
    New-Item -ItemType Directory -Force -Path (Split-Path $Path -Parent) | Out-Null
    # A bracket-free temporary name: the Fetch adapter may be a cmdlet that reads wildcards.
    $part = Join-Path (Split-Path $Path -Parent) (".download-" + [guid]::NewGuid().ToString('N') + '.part')
    $want = Get-ExpectedHash $Entry
    for ($try = 1; $try -le 3; $try++) {
        try {
            Remove-Item -LiteralPath $part -Force -ErrorAction SilentlyContinue
            $null = & $Context.Fetch $Entry.url $part
            if (-not (Test-Path -LiteralPath $part)) { throw 'the download produced no file' }
            $got = Get-Hash $part $want.Algorithm
            if ($got -ne $want.Value) { throw "hash mismatch for $($Entry.file) (expected $($want.Value), got $got)" }
            Copy-FileExact $part $Path -Move
            return $true
        } catch {
            Remove-Item -LiteralPath $part -Force -ErrorAction SilentlyContinue
            if ($try -eq 3) { throw "Could not download $($Entry.file) from $($Entry.url): $_" }
            Write-Note "Download of $($Entry.file) failed ($_), retrying..."
            Start-Sleep -Seconds (5 * $try)
        }
    }
}

# ================================================================ patches

function Get-PatchId([string]$Dir) {
    $sb = New-Object System.Text.StringBuilder
    foreach ($f in Get-RelativeFile $Dir) { [void]$sb.Append("$($f.Rel)=$(Get-Hash $f.FullName SHA256);") }
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $hash = $sha.ComputeHash($script:Utf8.GetBytes($sb.ToString())) } finally { $sha.Dispose() }
    return ([BitConverter]::ToString($hash) -replace '-', '').ToLower()
}

# Replaces files inside a zip with the files from a patch folder (same relative paths).
# A patch only replaces: a patch file with no matching zip entry is an error, and nothing is changed.
function Invoke-ZipPatch([string]$Zip, [string]$Dir, [string]$Name) {
    Use-Zip
    $files = @(Get-RelativeFile $Dir)
    $archive = [IO.Compression.ZipFile]::Open($Zip, [IO.Compression.ZipArchiveMode]::Update)
    try {
        $missing = @($files | Where-Object { -not $archive.GetEntry($_.Rel) } | ForEach-Object { $_.Rel })
        if ($missing.Count) {
            throw "Patch file(s) with no matching file in ${Name}: $($missing -join ', '). A patch may only replace files that already exist in the file it patches."
        }
        foreach ($f in $files) {
            $archive.GetEntry($f.Rel).Delete()
            $out = $archive.CreateEntry($f.Rel).Open()
            try { $bytes = [IO.File]::ReadAllBytes($f.FullName); $out.Write($bytes, 0, $bytes.Length) } finally { $out.Dispose() }
        }
    } finally { $archive.Dispose() }
}

# Puts the patched version of $Entry at $Path. The file on disk differs from the download, so the
# install state remembers what was produced ($Previous = @{ id; sha256 }) and reuses it while
# neither the upstream file nor the patch changed. Returns @{ Changed; Record }.
function Install-PatchedArtifact($Context, $Entry, [string]$Path, $Previous) {
    $patch = $Entry.patch
    if ($patch -is [string] -or -not $patch.path -or -not $patch.base_sha512) {
        throw "$($Entry.file): 'patch' in manifest.json must be an object with 'path' and 'base_sha512'."
    }
    $base = ([string]$patch.base_sha512).ToLower()
    if ($Entry.hashes.sha512 -and ([string]$Entry.hashes.sha512).ToLower() -ne $base) {
        throw "Patch $($patch.path) was made against a different upstream file than $($Entry.file) (its base_sha512 is not the entry's sha512)."
    }
    $patchDir = Join-Path $Context.RealmsDir ([string]$patch.path).Replace('/', '\')
    if (-not (Test-Path -LiteralPath $patchDir -PathType Container)) { throw "Patch folder $($patch.path) is missing." }

    $id = "$((Get-ExpectedHash $Entry).Value):$(Get-PatchId $patchDir)"
    if ($Previous -and $Previous.id -eq $id -and (Test-Path -LiteralPath $Path) -and (Get-Hash $Path SHA256) -eq $Previous.sha256) {
        return @{ Changed = $false; Record = $Previous }
    }

    $raw = Join-Path $Context.DownloadDir $Entry.file
    $work = "$raw.patching"
    [void](Save-Artifact $Context $Entry $raw)
    try {
        $got = Get-Hash $raw SHA512
        if ($got -ne $base) {
            throw "Patch $($patch.path) was made against a different upstream file than $($Entry.file) (base_sha512 $base, downloaded file $got)."
        }
        Copy-FileExact $raw $work
        Invoke-ZipPatch $work $patchDir $Entry.file
        New-Item -ItemType Directory -Force -Path (Split-Path $Path -Parent) | Out-Null
        Copy-FileExact $work $Path -Move
    } finally {
        Remove-Item -LiteralPath $raw, $work -Force -ErrorAction SilentlyContinue
    }
    return @{ Changed = $true; Record = @{ id = $id; sha256 = (Get-Hash $Path SHA256) } }
}

# ================================================================ managed files

# Reconciles one folder of managed files with the manifest: downloads (and patches) every wanted
# entry that isn't already correct, and removes files a previous install placed there that are no
# longer wanted. Only those exact file names are ever touched: files the host (or a mod) added and
# subfolders (e.g. mods\luckperms) are left alone.
# Returns @{ Changed = <count>; Managed = <file names now managed>; Patched = @{ file = record } }.
function Sync-ManagedFiles {
    param(
        $Context,
        [ValidateSet('plugin', 'mod', 'datapack')] [string]$Kind,
        [object[]]$Entries,
        [string]$Folder,
        [object[]]$Previous,
        $PreviousPatched
    )
    $label = $Kind.PadRight(8)
    $changed = 0
    $patched = @{}
    $wanted = @($Entries | Where-Object { $_ })
    foreach ($e in $wanted) {
        $dest = Join-Path $Folder $e.file
        if ($e.patch) {
            $prev = if ($PreviousPatched) { $PreviousPatched.($e.file) } else { $null }
            $r = Install-PatchedArtifact $Context $e $dest $prev
            $patched[$e.file] = $r.Record
            if ($r.Changed) { Write-Ok "$label $($e.slug) $($e.version) (patched)"; $changed++ }
        } elseif (Save-Artifact $Context $e $dest) {
            Write-Ok "$label $($e.slug) $($e.version)"
            $changed++
        }
    }
    $managed = @($wanted | ForEach-Object { [string]$_.file })
    foreach ($old in @($Previous)) {
        if ($old -and $managed -notcontains $old) {
            Remove-Item -LiteralPath (Join-Path $Folder $old) -Force -ErrorAction SilentlyContinue
            Write-Note "removed old $Kind $old"
        }
    }
    return [pscustomobject]@{ Changed = $changed; Managed = $managed; Patched = $patched }
}

# Install state (.realms-state.json): what the last install placed, so the next one can reconcile.
function Read-InstallState($Context) {
    $s = Read-JsonFile $Context.StateFile $null
    if (-not $s) { $s = [pscustomobject]@{} }
    return $s
}

function Write-InstallState($Context, [hashtable]$State) {
    Write-JsonFile $Context.StateFile $State
}

# The server type already installed in this folder, or $null for a fresh folder. State files from
# 1.x have no server_type: every 1.x release was Paper. Without a state file the server jar tells.
function Get-InstalledServerType($Context, $State) {
    if ($State.server_type) { return ([string]$State.server_type).ToLower() }
    if ($State.version) { return 'paper' }
    foreach ($type in @($script:ServerTypes.Keys | Sort-Object)) {
        if (Test-Path -LiteralPath (Join-Path $Context.ServerDir $script:ServerTypes[$type].Jar)) { return $type }
    }
    return $null
}

# True once the server has made a world: its folder holds more than the datapacks an install puts there.
function Test-WorldExists($Context) {
    $name = (Read-ServerProperties (Join-Path $Context.ServerDir 'server.properties'))['level-name']
    if (-not $name) { $name = Get-LevelName $Context }
    $dir = Join-Path $Context.ServerDir $name
    if (-not (Test-Path -LiteralPath $dir -PathType Container)) { return $false }
    return [bool](Get-ChildItem -LiteralPath $dir -Force | Where-Object { $_.Name -ne 'datapacks' } | Select-Object -First 1)
}

# A world can't move between a Paper and a Fabric server, so a release of the other type never
# installs over a folder with a world in it: it stops before changing anything.
# Returns the type that was installed before ($null for a fresh folder).
function Assert-SameServerType($Context, $Layout, $State) {
    $was = Get-InstalledServerType $Context $State
    if (-not $was -or $was -eq $Layout.Type) { return $was }
    if (Test-WorldExists $Context) {
        $old = if ($script:ServerTypes.ContainsKey($was)) { $script:ServerTypes[$was].Name } else { $was }
        throw ("This folder already has a $old server with a world in it, but this release of The Realms is a " +
            "$($Layout.Name) server. A world can't be moved from one to the other, so nothing was changed. " +
            "Unzip this release into a NEW, empty folder and start it from there. To keep playing the old " +
            "world, unzip the release you had before into this folder again.")
    }
    return $was
}

# ================================================================ server.properties and templates

<#
.SYNOPSIS
    Parses a server.properties file into a hashtable (raw values, comments skipped). Missing file = empty.
#>
function Read-ServerProperties {
    param([Parameter(Mandatory)] [string]$Path)
    $map = @{}
    if (Test-Path -LiteralPath $Path) {
        foreach ($line in [IO.File]::ReadAllLines($Path, $script:Utf8)) {
            if ($line -match '^\s*([^#!][^=]*)=(.*)$') { $map[$Matches[1].Trim()] = $Matches[2] }
        }
    }
    return $map
}

<#
.SYNOPSIS
    Sets one key in a server.properties file, keeping every other line (and comment) as it was.
#>
function Set-ServerProperty {
    param([Parameter(Mandatory)] [string]$Path, [Parameter(Mandatory)] [string]$Name, [AllowEmptyString()] [string]$Value)
    $text = if (Test-Path -LiteralPath $Path) { [IO.File]::ReadAllText($Path, $script:Utf8) } else { '' }
    $pattern = '(?m)^[ \t]*' + [regex]::Escape($Name) + '[ \t]*=[^\r\n]*'
    $line = "$Name=$Value"
    $regex = New-Object System.Text.RegularExpressions.Regex $pattern
    if ($regex.IsMatch($text)) {
        # A MatchEvaluator, so '$' in the value is taken literally.
        $text = $regex.Replace($text, { $line }, 1)
    } else {
        $nl = if ($text -match "`r`n") { "`r`n" } else { "`n" }
        if ($text -and -not $text.EndsWith("`n")) { $text += $nl }
        $text += "$line$nl"
    }
    Write-TextFile $Path $text
}

<#
.SYNOPSIS
    Replaces every {{NAME}} in a template with $Values[NAME]. Throws if any placeholder is left.
#>
function Expand-Template {
    param([Parameter(Mandatory)] [AllowEmptyString()] [string]$Text, [Parameter(Mandatory)] [hashtable]$Values)
    $out = $Text
    # String.Replace is literal, so values may contain '$' (unlike -replace).
    foreach ($key in $Values.Keys) { $out = $out.Replace("{{$key}}", [string]$Values[$key]) }
    $left = @([regex]::Matches($out, '\{\{.*?\}\}') | ForEach-Object { $_.Value } | Select-Object -Unique)
    if ($left.Count) { throw "Unresolved placeholder(s) in template: $($left -join ', ')" }
    return $out
}

function New-RconPassword {
    $bytes = New-Object byte[] 24
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([Convert]::ToBase64String($bytes)) -replace '[+/=]', 'x'
}

# Copies Defaults into the server folder, but only files that don't exist yet: the host's version wins.
function Install-Defaults($Context) {
    $defaults = Join-Path $Context.RealmsDir 'defaults'
    if (-not (Test-Path -LiteralPath $defaults)) { return }
    $values = @{
        RCON_PASSWORD = New-RconPassword
        SEED          = [string]$Context.Manifest.world.seed
        LEVEL_NAME    = Get-LevelName $Context
    }
    foreach ($f in Get-RelativeFile $defaults) {
        $dest = Join-Path $Context.ServerDir $f.Rel.Replace('/', '\')
        if (Test-Path -LiteralPath $dest) { continue }
        if ($script:TemplateFiles -contains $f.Rel) {
            Write-TextFile $dest (Expand-Template ([IO.File]::ReadAllText($f.FullName, $script:Utf8)) $values)
        } else {
            New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
            Copy-Item -LiteralPath $f.FullName -Destination $dest
        }
    }
}

function Test-ServerRunning($Context) {
    $props = Join-Path $Context.ServerDir 'server.properties'
    # Without server.properties this folder's server has never been set up, so it can't be running
    # (and another server on the default port must not block a first install).
    if (-not (Test-Path -LiteralPath $props)) { return $false }
    $p = (Read-ServerProperties $props)['server-port']
    $port = if ($p) { [int]$p } else { 25565 }
    $client = New-Object Net.Sockets.TcpClient
    try { return $client.ConnectAsync('127.0.0.1', $port).Wait(1000) } catch { return $false } finally { $client.Close() }
}

# ================================================================ RCON (talk to a running server)

function Invoke-RconSession([string]$HostName, [int]$Port, [string]$Secret, [string[]]$Commands) {
    $client = New-Object Net.Sockets.TcpClient
    $client.Connect($HostName, $Port)
    $stream = $client.GetStream()
    $stream.ReadTimeout = 15000
    $utf8 = $script:Utf8

    $send = {
        param([int]$Id, [int]$Type, [string]$Body)
        $bytes = $utf8.GetBytes($Body)
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
        return @{ Id = [BitConverter]::ToInt32($data, 0); Body = $utf8.GetString($data, 8, $len - 10) }
    }

    try {
        & $send 1 3 $Secret
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

<#
.SYNOPSIS
    Runs console commands on the running server over RCON (settings from server.properties).
    Returns one reply string per command, colour codes removed.
#>
function Invoke-Rcon {
    param([Parameter(Mandatory)] $Context, [Parameter(Mandatory)] [string[]]$Commands)
    $props = Read-ServerProperties (Join-Path $Context.ServerDir 'server.properties')
    if ($props['enable-rcon'] -ne 'true' -or -not $props['rcon.password']) { throw 'RCON is turned off in server.properties.' }
    # A server that is still warming up can drop or refuse a connection for a few seconds after
    # "Done". Reconnect and resend; every command the scripts send (stop, whitelist add, save-*) is
    # safe to repeat. A rejected password is never retried.
    for ($attempt = 1; ; $attempt++) {
        try {
            return Invoke-RconSession '127.0.0.1' ([int]$props['rcon.port']) $props['rcon.password'] $Commands
        } catch {
            # A drop shows up as a clean close, a reset (IOException) or a refused connect (SocketException).
            $transient = $false
            for ($e = $_.Exception; $e; $e = $e.InnerException) {
                if ($e.Message -like '*RCON connection closed*' -or $e -is [IO.IOException] -or $e -is [Net.Sockets.SocketException]) {
                    $transient = $true
                }
            }
            if (-not $transient -or $attempt -ge 5) { throw }
            Start-Sleep -Seconds 3
        }
    }
}

# ================================================================ players

function Get-PlayerProfile($Context, [string]$PlayerName) {
    $p = & $Context.ProfileLookup $PlayerName
    if (-not $p -or -not $p.Name -or -not $p.Uuid) { throw "Couldn't find a Minecraft Java account named '$PlayerName'." }
    return $p
}

function Add-ToList($Context, [string]$File, [hashtable]$Entry) {
    $path = Join-Path $Context.ServerDir $File
    $list = @(Read-JsonFile $path @()) | Where-Object { $_ -and $_.uuid -ne $Entry.uuid }
    Write-JsonFile $path (@($list) + [pscustomobject]$Entry)
}

<#
.SYNOPSIS
    Makes a player the Owner: whitelist, op level 4 and the LuckPerms admin rank. Returns their name.
#>
function Add-Owner {
    param([Parameter(Mandatory)] $Context, [Parameter(Mandatory)] [string]$Name)
    $p = Get-PlayerProfile $Context $Name
    Add-ToList $Context 'whitelist.json' @{ uuid = $p.Uuid; name = $p.Name }
    Add-ToList $Context 'ops.json' @{ uuid = $p.Uuid; name = $p.Name; level = 4; bypassesPlayerLimit = $true }
    # LuckPerms (YAML storage): put the owner in the admin group.
    $storage = (Get-ServerLayout -Manifest $Context.Manifest).LuckPerms
    $lp = Join-Path $Context.ServerDir "$storage\users\$($p.Uuid).yml"
    if (-not (Test-Path -LiteralPath $lp)) {
        Write-TextFile $lp "uuid: $($p.Uuid)`nname: $($p.Name.ToLower())`nprimary-group: admin`nparents:`n- admin`n"
    }
    Write-Ok "$($p.Name) is the server admin (op + admin rank) and is on the whitelist."
    return $p.Name
}

<#
.SYNOPSIS
    Lets a player join: whitelists them over RCON if the server runs, else in whitelist.json.
#>
function Add-Player {
    param([Parameter(Mandatory)] $Context, [string]$Name)
    if (-not $Name) { $Name = Read-Answer $Context "Friend's Minecraft username" }
    if (Test-ServerRunning $Context) {
        Invoke-Rcon $Context @("whitelist add $Name") | ForEach-Object { Write-Ok $_ }
    } else {
        $p = Get-PlayerProfile $Context $Name
        Add-ToList $Context 'whitelist.json' @{ uuid = $p.Uuid; name = $p.Name }
        Write-Ok "$($p.Name) can now join."
    }
}

# ================================================================ install

function Install-Java($Context) {
    $java = $Context.Manifest.java
    $home_ = Join-Path $Context.JavaDir $java.version
    $exe = Join-Path $home_ 'bin\java.exe'
    if (Test-Path -LiteralPath $exe) { return $exe }
    Write-Step "Downloading Java ($($java.vendor) $($java.version), $([math]::Round($java.size / 1MB)) MB)"
    $zip = Join-Path $Context.DownloadDir $java.file
    [void](Save-Artifact $Context $java $zip)
    Use-Zip
    $tmp = Join-Path $Context.JavaDir '.extract'
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    [IO.Compression.ZipFile]::ExtractToDirectory($zip, $tmp)
    $inner = Get-ChildItem -LiteralPath $tmp -Directory | Select-Object -First 1
    Remove-Item -LiteralPath $home_ -Recurse -Force -ErrorAction SilentlyContinue
    Move-Item -LiteralPath $inner.FullName -Destination $home_
    Remove-Item -LiteralPath $tmp, $zip -Recurse -Force
    # Old Java versions from earlier manifests.
    Get-ChildItem -LiteralPath $Context.JavaDir -Directory | Where-Object { $_.Name -ne $java.version } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Ok 'Java ready.'
    return $exe
}

function Confirm-Eula($Context, [bool]$AcceptEula) {
    $path = Join-Path $Context.ServerDir 'eula.txt'
    if ((Test-Path -LiteralPath $path) -and ([IO.File]::ReadAllText($path) -match 'eula\s*=\s*true')) { return }
    if (-not $AcceptEula) {
        Write-Host ''
        Write-Host 'Minecraft servers require you to agree to the Minecraft EULA:' -ForegroundColor White
        Write-Host '    https://aka.ms/MinecraftEULA' -ForegroundColor White
        $a = Read-Answer $Context 'Do you agree to it? Type YES and press Enter'
        if ($a -notmatch '^(y|yes)$') { throw 'The server cannot run unless you agree to the Minecraft EULA.' }
    }
    Write-TextFile $path "# Agreed via The Realms installer on $(Get-Date -Format s)`neula=true`n"
}

<#
.SYNOPSIS
    Install: brings the server folder in line with the manifest. Idempotent. Returns the java.exe path.
#>
function Install-Server {
    param([Parameter(Mandatory)] $Context, [switch]$AcceptEula, [string]$Owner, [switch]$NoOwner)
    if (Test-ServerRunning $Context) { throw 'The server is running. Stop it first (type "stop" in its window, or run Stop Server).' }
    $m = $Context.Manifest
    $server = $Context.ServerDir
    $layout = Get-ServerLayout -Manifest $m
    foreach ($group in $script:Groups.Keys) {
        if ($group -ne 'datapacks' -and $group -ne $layout.AddOns -and @($m.$group | Where-Object { $_ }).Count) {
            throw "manifest.json lists $group, but a $($layout.Name) server can't load $group (only $($layout.AddOns))."
        }
    }
    $state = Read-InstallState $Context
    $was = Assert-SameServerType $Context $layout $state
    New-Item -ItemType Directory -Force -Path $server | Out-Null
    $firstInstall = -not $state.version

    Confirm-Eula $Context ([bool]$AcceptEula)
    $java = Install-Java $Context

    Write-Step "Checking server files for $($m.name) $($m.version) (Minecraft $($m.minecraft), $($layout.Name))"
    $n = 0
    if ($was -and $was -ne $layout.Type -and $script:ServerTypes.ContainsKey($was)) {
        # No world yet, so the switch is safe; the old server jar is ours to remove.
        $oldJar = $script:ServerTypes[$was].Jar
        if ($oldJar -ne $layout.Jar) { Remove-Item -LiteralPath (Join-Path $server $oldJar) -Force -ErrorAction SilentlyContinue }
        Write-Note "switched this folder from $($script:ServerTypes[$was].Name) to $($layout.Name)"
    }
    if (Save-Artifact $Context $m.server (Join-Path $server $layout.Jar)) { Write-Ok $layout.Description; $n++ }
    $synced = [ordered]@{}
    foreach ($group in $script:Groups.Keys) {
        $synced[$group] = Sync-ManagedFiles -Context $Context -Kind $script:Groups[$group] -Entries $m.$group `
            -Folder (Get-GroupFolder $Context $group) -Previous $state.$group -PreviousPatched $state.patched
        $n += $synced[$group].Changed
    }
    if ($n -eq 0) { Write-Ok 'Everything is up to date.' }

    Install-Defaults $Context

    $ownerName = $state.owner
    if (-not $ownerName -and -not $NoOwner) {
        $who = $Owner
        if (-not $who -and -not $Context.NonInteractive) {
            Write-Host ''
            $who = Read-Answer $Context 'What is YOUR Minecraft username? (you will be the admin; press Enter to skip)'
        }
        if ($who) { $ownerName = Add-Owner $Context $who }
    }

    # 1.x state files have this shape minus server_type and mods, and read back as a Paper install.
    $patched = @{}
    foreach ($r in $synced.Values) { foreach ($k in $r.Patched.Keys) { $patched[$k] = $r.Patched[$k] } }
    Write-InstallState $Context @{
        version     = $m.version
        server_type = $layout.Type
        java        = $java
        owner       = $ownerName
        plugins     = @($synced.plugins.Managed)
        mods        = @($synced.mods.Managed)
        datapacks   = @($synced.datapacks.Managed)
        patched     = $patched
    }
    Remove-Item -LiteralPath $Context.DownloadDir -Recurse -Force -ErrorAction SilentlyContinue
    if ($firstInstall) { Write-Ok 'Install finished.' }
    return $java
}

# ================================================================ start / stop / backup / status

<#
.SYNOPSIS
    Server memory in GB: -Requested if set, else -EnvValue (REALMS_MEMORY_GB), else picked from total RAM.
#>
function Get-MemoryGB {
    param([Parameter(Mandatory)] [double]$TotalBytes, [int]$Requested = 0, [string]$EnvValue)
    if ($Requested -gt 0) { return $Requested }
    if ($EnvValue) { return [int]$EnvValue }
    # 25 players on this pack peaked at about 4.3 GB in use, so 8 GB is plenty (the heap is committed up front,
    # so more only takes RAM from everything else). Smaller PCs get less so Windows (and a game) still fit.
    $total = $TotalBytes / 1GB
    if ($total -le 8.5) { return 3 }
    if ($total -le 12.5) { return 4 }
    if ($total -le 16.5) { return 5 }
    if ($total -le 24.5) { return 6 }
    return 8
}

<#
.SYNOPSIS
    The java command line (everything after java.exe) that runs the manifest's server with -MemoryGB of memory.
#>
function Get-LaunchArguments {
    param([Parameter(Mandatory)] $Manifest, [Parameter(Mandatory)] [int]$MemoryGB)
    $layout = Get-ServerLayout -Manifest $Manifest
    $gb = $MemoryGB
    # Aikar's G1 flags (https://docs.papermc.io/paper/aikars-flags); they suit a Fabric server too.
    return @("-Xms${gb}G", "-Xmx${gb}G", '-XX:+UseG1GC', '-XX:+ParallelRefProcEnabled', '-XX:MaxGCPauseMillis=200',
        '-XX:+UnlockExperimentalVMOptions', '-XX:+DisableExplicitGC', '-XX:+AlwaysPreTouch', '-XX:G1NewSizePercent=30',
        '-XX:G1MaxNewSizePercent=40', '-XX:G1HeapRegionSize=8M', '-XX:G1ReservePercent=20', '-XX:G1HeapWastePercent=5',
        '-XX:G1MixedGCCountTarget=4', '-XX:InitiatingHeapOccupancyPercent=15', '-XX:G1MixedGCLiveThresholdPercent=90',
        '-XX:G1RSetUpdatingPauseTimePercent=5', '-XX:SurvivorRatio=32', '-XX:+PerfDisableSharedMem',
        '-XX:MaxTenuringThreshold=1', '-Dusing.aikars.flags=https://mcflags.emc.gs', '-Daikars.new.flags=true',
        '-jar', $layout.Jar) + $layout.Arguments
}

<#
.SYNOPSIS
    Runs the server in this window until it stops. Throws if it exits with an error.
#>
function Start-Server {
    param([Parameter(Mandatory)] $Context, [Parameter(Mandatory)] [string]$Java, [Parameter(Mandatory)] [int]$MemoryGB)
    $gb = $MemoryGB
    $jvm = Get-LaunchArguments -Manifest $Context.Manifest -MemoryGB $gb
    Write-Host ''
    Write-Step "Starting The Realms with $gb GB of memory"
    Write-Host '    Friends join at the address shown by playit.gg (see READ ME FIRST.txt).' -ForegroundColor White
    Write-Host '    To stop the server safely, type  stop  here and press Enter.' -ForegroundColor White
    Write-Host '    (Closing this window without "stop" can lose the last few minutes of the world.)' -ForegroundColor White
    Write-Host ''
    Push-Location $Context.ServerDir
    try { & $Java @jvm; $code = $LASTEXITCODE } finally { Pop-Location }
    if ($code -ne 0) { throw "The server stopped with an error (exit code $code). See the messages above, or server\logs\latest.log." }
    Write-Step 'Server stopped.'
}

<#
.SYNOPSIS
    Stops the running server over RCON and waits (up to 2 minutes) for it to go away.
#>
function Stop-Server {
    param([Parameter(Mandatory)] $Context)
    if (-not (Test-ServerRunning $Context)) { Write-Ok 'The server is not running.'; return }
    [void](Invoke-Rcon $Context @('stop'))
    for ($i = 0; $i -lt 60 -and (Test-ServerRunning $Context); $i++) { Start-Sleep -Seconds 2 }
    Write-Ok 'Server stopped.'
}

<#
.SYNOPSIS
    Copies the world, configs and plugin or mod data to backups\<timestamp> and keeps the newest 14.
#>
function Backup-Server {
    param([Parameter(Mandatory)] $Context)
    $server = $Context.ServerDir
    if (-not (Test-Path -LiteralPath $server)) { throw 'Nothing to back up yet - the server has never been installed.' }
    $running = Test-ServerRunning $Context
    $stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
    $dest = Join-Path $Context.BackupDir $stamp
    Write-Step "Backing up to backups\$stamp"
    if ($running) { [void](Invoke-Rcon $Context @('save-off', 'save-all flush')); Start-Sleep -Seconds 3 }
    try {
        # Worlds, configs and plugin or mod data. Skips things the installer can re-download or the server rebuilds.
        & robocopy $server $dest /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP `
            /XD (Join-Path $server 'libraries') (Join-Path $server 'versions') (Join-Path $server 'cache') `
                (Join-Path $server 'logs') (Join-Path $server 'bluemap') (Join-Path $server 'plugins\.paper-remapped') `
                (Join-Path $server '.fabric') `
            /XF '*.jar' 'session.lock' | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy failed with exit code $LASTEXITCODE" }
    } finally {
        if ($running) { [void](Invoke-Rcon $Context @('save-on')) }
    }
    Get-ChildItem -LiteralPath $Context.BackupDir -Directory | Sort-Object Name -Descending |
        Select-Object -Skip $script:KeepBackups | Remove-Item -Recurse -Force
    $size = (Get-ChildItem -LiteralPath $dest -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
    Write-Ok ("Backup done ({0:N0} MB)." -f $size)
}

<#
.SYNOPSIS
    Prints the release, install state and whether the server is running.
#>
function Show-Status {
    param([Parameter(Mandatory)] $Context)
    $m = $Context.Manifest
    $layout = Get-ServerLayout -Manifest $m
    $state = Read-InstallState $Context
    $addOns = if ($layout.AddOns -eq 'mods') { 'Mods' } else { 'Plugins' }
    $addOnCount = @($m.($layout.AddOns) | Where-Object { $_ }).Count
    Write-Host "$($m.name) $($m.version) - Minecraft $($m.minecraft), $($layout.Description)"
    Write-Host "Installed: $(if ($state.version) { $state.version } else { 'no' })    Admin: $($state.owner)"
    Write-Host "Running:   $(Test-ServerRunning $Context)    ${addOns}: $addOnCount    Datapacks: $(@($m.datapacks | Where-Object { $_ }).Count)"
}

# ================================================================ hosting export

# What an online host doesn't need from server\: logs, caches and files the server re-downloads or
# rebuilds, plus the install state (it describes this PC's folder). Folder names are top level.
$script:ExportSkipDirs = @('logs', 'crash-reports', 'cache', '.fabric', 'libraries', 'versions', 'bluemap', 'plugins/.paper-remapped')
$script:ExportSkipFiles = @('.realms-state.json')
$script:ExportSkipPatterns = @('*.part', 'session.lock')
# Ports a host has to open besides the game port: Simple Voice Chat (UDP) and the BlueMap web map.
$script:VoicePort = 24454
$script:MapPort = 8100

# The Java feature release the manifest pins ('jdk-25.0.4.1+1' -> 25), for picking a JRE on a host.
function Get-JavaMajor($Manifest) {
    $v = [string]$Manifest.java.version
    if ($v -notmatch '(\d+)') { throw "Can't tell the Java version from manifest.json java.version '$v'." }
    return [int]$Matches[1]
}

# A word for a POSIX sh command line, quoted only when it has to be.
function ConvertTo-ShWord([string]$Word) {
    if ($Word -match '^[A-Za-z0-9_./:=+@%,-]+$') { return $Word }
    return "'" + $Word.Replace("'", "'\''") + "'"
}

# The launch command with the memory left to the start script: Get-LaunchArguments stays the one
# place that knows the flags, jar and arguments. -Memory replaces the "<n>G" in -Xms/-Xmx.
function Get-HostingLaunchArguments($Manifest, [string]$Memory) {
    $probe = 987654
    $out = @()
    $replaced = 0
    foreach ($a in Get-LaunchArguments -Manifest $Manifest -MemoryGB $probe) {
        if ($a -eq "-Xms${probe}G" -or $a -eq "-Xmx${probe}G") { $out += $a.Substring(0, 4) + $Memory + 'G'; $replaced++ }
        else { $out += $a }
    }
    if ($replaced -ne 2) { throw 'Get-LaunchArguments no longer sets -Xms and -Xmx; update the hosting export.' }
    return $out
}

function New-StartSh($Manifest) {
    $layout = Get-ServerLayout -Manifest $Manifest
    $lines = @('#!/bin/sh',
        "# Starts $($Manifest.name) $($Manifest.version) ($($layout.Description), Minecraft $($Manifest.minecraft)).",
        '# Memory in GB comes from MEMORY_GB (default 6); the java to use from JAVA (default: java on the PATH).',
        '# Made by "Prepare for Hosting". See HOSTING.txt.',
        'cd "$(dirname "$0")" || exit 1',
        'MEMORY_GB="${MEMORY_GB:-6}"',
        'case "$MEMORY_GB" in',
        "    ''|*[!0-9]*) echo `"MEMORY_GB must be a whole number of gigabytes, not '`$MEMORY_GB'`" >&2; exit 1 ;;",
        'esac',
        'exec "${JAVA:-java}" \')
    $sentinel = '@MEMORY@'
    $words = @(Get-HostingLaunchArguments $Manifest $sentinel | ForEach-Object {
            if ($_.Contains($sentinel)) { $_.Replace($sentinel, '"${MEMORY_GB}"') } else { ConvertTo-ShWord $_ }
        })
    for ($i = 0; $i -lt $words.Count; $i++) {
        $lines += '    ' + $words[$i] + $(if ($i -lt $words.Count - 1) { ' \' } else { '' })
    }
    return ($lines -join "`n") + "`n"
}

function New-StartBat($Manifest) {
    $layout = Get-ServerLayout -Manifest $Manifest
    $cmd = (Get-HostingLaunchArguments $Manifest '%MEMORY_GB%') -join ' '
    $lines = @('@echo off',
        "rem Starts $($Manifest.name) $($Manifest.version) ($($layout.Description)) on a Windows server.",
        'rem Memory in GB comes from MEMORY_GB (default 6). Needs Java on the PATH. See HOSTING.txt.',
        'setlocal',
        'cd /d "%~dp0"',
        'if "%MEMORY_GB%"=="" set MEMORY_GB=6',
        "java $cmd",
        'if errorlevel 1 pause')
    return ($lines -join "`r`n") + "`r`n"
}

function New-DockerCompose($Manifest, [int]$GamePort) {
    $java = Get-JavaMajor $Manifest
    $lines = @(
        "# $($Manifest.name) $($Manifest.version) on Docker. Start: docker compose up -d   (see HOSTING.txt)",
        'services:',
        '  realms:',
        "    image: eclipse-temurin:$java-jre",
        '    working_dir: /data',
        '    volumes:',
        '      - .:/data',
        '    command: ["sh", "./start.sh"]',
        '    environment:',
        '      MEMORY_GB: "6"',
        '    ports:',
        "      - `"${GamePort}:${GamePort}/tcp`"",
        "      - `"$($script:VoicePort):$($script:VoicePort)/udp`"",
        "      - `"$($script:MapPort):$($script:MapPort)/tcp`"",
        '    restart: unless-stopped',
        '    stdin_open: true',
        '    tty: true')
    return ($lines -join "`n") + "`n"
}

function New-HostingGuide($Manifest, [int]$GamePort, [string]$Folder) {
    $layout = Get-ServerLayout -Manifest $Manifest
    $java = Get-JavaMajor $Manifest
    $voiceConfig = if ($layout.Type -eq 'fabric') { 'config/voicechat/voicechat-server.properties' } else { 'plugins/voicechat/voicechat-server.properties' }
    $text = @"
$($Manifest.name.ToUpper()) $($Manifest.version) - RUNNING THE SERVER ON AN ONLINE HOST
=====================================================================

This zip is your own copy of The Realms server, made by "Prepare for Hosting" on your PC:
$($layout.Name) ($($layout.Description)) for Minecraft $($Manifest.minecraft), with its $($layout.AddOns),
datapacks and settings. Upload it to an online Minecraft host or to your own server
and players can join without your PC being on.

  Server jar:   $($layout.Jar)
  Java:         $java
  Game port:    $GamePort (TCP)
  Voice chat:   $($script:VoicePort) (UDP, for Simple Voice Chat)
  Web map:      $($script:MapPort) (TCP, BlueMap; optional)

Unzipping gives a folder "$Folder". Upload what is INSIDE it, so that
$($layout.Jar) ends up in the server's main (root) folder.

The Minecraft EULA is already accepted in eula.txt (you agreed to it when you prepared
this zip). The RCON password is in server.properties (rcon.password): change it to a new
long random one before you go online.


1. A MINECRAFT HOSTING COMPANY (Shockbyte, Apex, BisectHosting, any Pterodactyl panel)
---------------------------------------------------------------------------------------
  a) Create a server of type "$($layout.Name)" or "Custom JAR".
     Pick Java $java if the panel asks for a Java version (or a "Java $java" Docker image).
  b) Stop it, and delete the files the panel put there (keep nothing).
  c) Upload the zip with the panel's file manager (or SFTP) and extract it. Move the
     contents of "$Folder" up into the main folder if the panel kept the folder.
  d) Set the server jar / startup file to:  $($layout.Jar)
     (A panel that downloads its own jar for you would replace the pinned one - use "Custom JAR".)
  e) Set the memory (RAM): 6 GB or more (8 GB for a big group). For more than about 10
     players the CPU matters more than RAM: pick a plan that names a current CPU
     (for example Ryzen 7000 or 9000 series), not an older Xeon.
  f) Start it. The first start downloads a few more files and takes a few minutes.
     It is ready when the console says  Done (...)! For help, type "help"
  g) Voice chat needs UDP port $($script:VoicePort). If the host gives you a second port instead,
     put that number after  port=  in  $voiceConfig
     and restart. Without it everything else still works.
  The panel usually sets the game port itself; players join at the address the panel shows.


2. YOUR OWN LINUX SERVER (VPS) WITH DOCKER
------------------------------------------
  a) Install Docker:  https://docs.docker.com/engine/install/
  b) Upload the zip, then:   unzip $Folder.zip   and   cd $Folder
  c) Start:            docker compose up -d
     Watch the log:    docker compose logs -f        (Ctrl+C stops watching, not the server)
     Type commands:    docker compose attach realms  (leave with Ctrl+P then Ctrl+Q)
     Stop:             docker compose stop
  d) Memory: change MEMORY_GB in docker-compose.yml (default 6 GB; use 8 for a big
     group; give the VPS about 2 GB more RAM than that, and a fast CPU for more than ~10 players).
  It restarts by itself after a reboot until you stop it.


3. YOUR OWN LINUX SERVER (VPS) WITHOUT DOCKER
---------------------------------------------
  a) Install Java $java, for example:   sudo apt install openjdk-$java-jre-headless
     (or Eclipse Temurin $java from https://adoptium.net)
  b) Upload the zip, then:   unzip $Folder.zip   and   cd $Folder
  c) Start it inside screen or tmux so it keeps running when you log out:
        screen -S realms
        MEMORY_GB=6 sh start.sh
     Leave screen with Ctrl+A then D; come back with  screen -r realms
  d) Stop: type  stop  in the server console.
  On a Windows server, install Java $java and double-click start.bat instead.


4. FIREWALL (VPS)
-----------------
  Allow $GamePort/tcp (the game), $($script:VoicePort)/udp (voice chat) and, if you want the web map,
  $($script:MapPort)/tcp. For example with ufw:
     sudo ufw allow $GamePort/tcp
     sudo ufw allow $($script:VoicePort)/udp
     sudo ufw allow $($script:MapPort)/tcp


5. BACKUPS
----------
  Stop the server, then copy the world folders (world, world_nether, world_the_end if they
  exist) and the $($layout.AddOns) and config folders somewhere safe. Most hosting panels also have
  a Backups button.
"@
    return $text.Replace("`r`n", "`n").Replace("`n", "`r`n")
}

function Test-ExportSkip([string]$Rel) {
    foreach ($d in $script:ExportSkipDirs) { if ($Rel.StartsWith("$d/", [StringComparison]::OrdinalIgnoreCase)) { return $true } }
    if ($script:ExportSkipFiles -contains $Rel) { return $true }
    $leaf = $Rel.Substring($Rel.LastIndexOf('/') + 1)
    foreach ($p in $script:ExportSkipPatterns) { if ($leaf -like $p) { return $true } }
    return $false
}

function Add-ZipText($Archive, [string]$Name, [string]$Text, [int]$UnixMode = 0) {
    $entry = $Archive.CreateEntry($Name, [IO.Compression.CompressionLevel]::Optimal)
    # Regular file + permission bits in the high 16 bits, the way Info-ZIP stores them.
    if ($UnixMode) { $entry.ExternalAttributes = [BitConverter]::ToInt32([BitConverter]::GetBytes([uint32]((0x8000 -bor $UnixMode) * 65536)), 0) }
    $s = $entry.Open()
    try { $b = $script:Utf8.GetBytes($Text); $s.Write($b, 0, $b.Length) } finally { $s.Dispose() }
}

# .NET on Windows marks every zip entry as made on Windows, and unzip then ignores the Unix
# permission bits. Marks the entries that carry Unix permissions as made on Unix instead.
function Set-ZipUnixHost([string]$Path) {
    $fs = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite)
    try {
        $r = New-Object IO.BinaryReader $fs
        # End of central directory: at least 22 bytes from the end, after a comment of up to 64 KB.
        $tail = [int][Math]::Min($fs.Length, 22 + 65535)
        $fs.Position = $fs.Length - $tail
        $buf = $r.ReadBytes($tail)
        $eocd = -1
        for ($i = $buf.Length - 22; $i -ge 0; $i--) {
            if ($buf[$i] -eq 0x50 -and $buf[$i + 1] -eq 0x4b -and $buf[$i + 2] -eq 5 -and $buf[$i + 3] -eq 6) { $eocd = $i; break }
        }
        if ($eocd -lt 0) { throw 'no end of central directory' }
        $count = [BitConverter]::ToUInt16($buf, $eocd + 10)
        $start = [BitConverter]::ToUInt32($buf, $eocd + 16)
        # A zip64 archive (over 4 GB or 65535 files) keeps these elsewhere; leave it as it is.
        if ($start -eq [uint32]::MaxValue -or $count -eq [uint16]::MaxValue) { return }
        $pos = [long]$start
        for ($n = 0; $n -lt $count; $n++) {
            $fs.Position = $pos
            $h = $r.ReadBytes(46)
            if ([BitConverter]::ToUInt32($h, 0) -ne 0x02014b50) { throw 'bad central directory entry' }
            if ([BitConverter]::ToUInt32($h, 38) -shr 16) {
                $fs.Position = $pos + 5
                $fs.WriteByte(3)   # 3 = Unix
            }
            $pos += 46 + [BitConverter]::ToUInt16($h, 28) + [BitConverter]::ToUInt16($h, 30) + [BitConverter]::ToUInt16($h, 32)
        }
    } finally { $fs.Dispose() }
}

<#
.SYNOPSIS
    Writes exports\TheRealms-<version>-hosting.zip: the installed server folder plus start.sh,
    start.bat, docker-compose.yml and HOSTING.txt, ready to upload to an online host. Returns its path.
.DESCRIPTION
    Run Install-Server first: the export packs what this PC installed (nothing third-party is
    redistributed by the release itself, see docs/adr/0002). Overwrites an earlier export.
#>
function Export-HostingBundle {
    param([Parameter(Mandatory)] $Context)
    if (Test-ServerRunning $Context) { throw 'The server is running. Stop it first (type "stop" in its window, or run Stop Server).' }
    $m = $Context.Manifest
    $layout = Get-ServerLayout -Manifest $m
    $server = $Context.ServerDir
    if (-not (Test-Path -LiteralPath (Join-Path $server $layout.Jar))) {
        throw "The server isn't installed yet ($($layout.Jar) is missing). Run the install first."
    }
    $folder = "TheRealms-$($m.version)-hosting"
    $exports = Join-Path $Context.Root 'exports'
    New-Item -ItemType Directory -Force -Path $exports | Out-Null
    $zipPath = Join-Path $exports "$folder.zip"
    $part = Join-Path $exports (".export-" + [guid]::NewGuid().ToString('N') + '.part')
    $p = (Read-ServerProperties (Join-Path $server 'server.properties'))['server-port']
    $gamePort = if ($p -match '^\d+$') { [int]$p } else { 25565 }

    Write-Step "Packing the server for an online host ($folder.zip)"
    Use-Zip
    $base = (Get-Item -LiteralPath $server).FullName.TrimEnd('\')
    try {
        $archive = [IO.Compression.ZipFile]::Open($part, [IO.Compression.ZipArchiveMode]::Create)
        try {
            foreach ($f in Get-ChildItem -LiteralPath $base -Recurse -File -Force | Sort-Object FullName) {
                $rel = $f.FullName.Substring($base.Length + 1).Replace('\', '/')
                if (Test-ExportSkip $rel) { continue }
                [void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $f.FullName, "$folder/$rel",
                    [IO.Compression.CompressionLevel]::Optimal)
            }
            Add-ZipText $archive "$folder/start.sh" (New-StartSh $m) 493   # 0755
            Add-ZipText $archive "$folder/start.bat" (New-StartBat $m)
            Add-ZipText $archive "$folder/docker-compose.yml" (New-DockerCompose $m $gamePort)
            Add-ZipText $archive "$folder/HOSTING.txt" (New-HostingGuide $m $gamePort $folder)
        } finally { $archive.Dispose() }
        Set-ZipUnixHost $part
        Copy-FileExact $part $zipPath -Move
    } finally {
        Remove-Item -LiteralPath $part -Force -ErrorAction SilentlyContinue
    }
    Write-Ok ("Made {0} ({1:N0} MB)." -f $zipPath, ((Get-Item -LiteralPath $zipPath).Length / 1MB))
    Write-Ok "Read HOSTING.txt inside the zip for how to upload and start it on a host."
    return $zipPath
}

Export-ModuleMember -Function @(
    'New-RealmsContext'
    'Install-Server'
    'Start-Server'
    'Stop-Server'
    'Backup-Server'
    'Show-Status'
    'Add-Player'
    'Add-Owner'
    'Invoke-Rcon'
    'Get-MemoryGB'
    'Get-LaunchArguments'
    'Get-ServerLayout'
    'Export-HostingBundle'
    'Get-ExpectedHash'
    'Read-ServerProperties'
    'Set-ServerProperty'
    'Expand-Template'
)
