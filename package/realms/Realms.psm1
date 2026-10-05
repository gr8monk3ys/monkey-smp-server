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
    $part = "$Path.part"
    $want = Get-ExpectedHash $Entry
    for ($try = 1; $try -le 3; $try++) {
        try {
            Remove-Item -LiteralPath $part -Force -ErrorAction SilentlyContinue
            $null = & $Context.Fetch $Entry.url $part
            if (-not (Test-Path -LiteralPath $part)) { throw 'the download produced no file' }
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
            throw "Patch file(s) with no matching file in ${Name}: $($missing -join ', '). A patch may only replace files that already exist in the datapack."
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
        throw "Datapack $($Entry.file): 'patch' in manifest.json must be an object with 'path' and 'base_sha512'."
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
        Copy-Item -LiteralPath $raw -Destination $work -Force
        Invoke-ZipPatch $work $patchDir $Entry.file
        New-Item -ItemType Directory -Force -Path (Split-Path $Path -Parent) | Out-Null
        Move-Item -LiteralPath $work -Destination $Path -Force
    } finally {
        Remove-Item -LiteralPath $raw, $work -Force -ErrorAction SilentlyContinue
    }
    return @{ Changed = $true; Record = @{ id = $id; sha256 = (Get-Hash $Path SHA256) } }
}

# ================================================================ managed files

# Reconciles one folder of managed files with the manifest: downloads (and patches) every wanted
# entry that isn't already correct, and removes files a previous install placed there that are no
# longer wanted. Files the host added (never in $Previous) are left alone.
# Returns @{ Changed = <count>; Managed = <file names now managed>; Patched = @{ file = record } }.
function Sync-ManagedFiles {
    param(
        $Context,
        [ValidateSet('plugin', 'datapack')] [string]$Kind,
        [object[]]$Entries,
        [string]$Folder,
        [object[]]$Previous,
        $PreviousPatched
    )
    $label = if ($Kind -eq 'plugin') { 'plugin ' } else { $Kind }
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
    return Invoke-RconSession '127.0.0.1' ([int]$props['rcon.port']) $props['rcon.password'] $Commands
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
    $lp = Join-Path $Context.ServerDir "plugins\LuckPerms\yaml-storage\users\$($p.Uuid).yml"
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
    New-Item -ItemType Directory -Force -Path $server | Out-Null
    $state = Read-InstallState $Context
    $firstInstall = -not $state.version

    Confirm-Eula $Context ([bool]$AcceptEula)
    $java = Install-Java $Context

    Write-Step "Checking server files for $($m.name) $($m.version) (Minecraft $($m.minecraft))"
    $n = 0
    if (Save-Artifact $Context $m.server (Join-Path $server 'paper.jar')) { Write-Ok "Paper build $($m.server.build)"; $n++ }
    $plugins = Sync-ManagedFiles -Context $Context -Kind plugin -Entries $m.plugins -Folder (Join-Path $server 'plugins') `
        -Previous $state.plugins -PreviousPatched $state.patched
    $packs = Sync-ManagedFiles -Context $Context -Kind datapack -Entries $m.datapacks `
        -Folder (Join-Path $server "$(Get-LevelName $Context)\datapacks") -Previous $state.datapacks -PreviousPatched $state.patched
    $n += $plugins.Changed + $packs.Changed
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

    $patched = @{}
    foreach ($r in $plugins, $packs) { foreach ($k in $r.Patched.Keys) { $patched[$k] = $r.Patched[$k] } }
    Write-InstallState $Context @{
        version   = $m.version
        java      = $java
        owner     = $ownerName
        plugins   = @($plugins.Managed)
        datapacks = @($packs.Managed)
        patched   = $patched
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
    $total = $TotalBytes / 1GB
    if ($total -le 8.5) { return 3 }
    if ($total -le 12.5) { return 4 }
    if ($total -le 16.5) { return 5 }
    return 6
}

<#
.SYNOPSIS
    Runs the server in this window until it stops. Throws if it exits with an error.
#>
function Start-Server {
    param([Parameter(Mandatory)] $Context, [Parameter(Mandatory)] [string]$Java, [Parameter(Mandatory)] [int]$MemoryGB)
    $gb = $MemoryGB
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
    Copies the world, configs and plugin data to backups\<timestamp> and keeps the newest 14.
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
        # Worlds, configs and plugin data. Skips things the installer can re-download or the server rebuilds.
        & robocopy $server $dest /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP `
            /XD (Join-Path $server 'libraries') (Join-Path $server 'versions') (Join-Path $server 'cache') `
                (Join-Path $server 'logs') (Join-Path $server 'bluemap') (Join-Path $server 'plugins\.paper-remapped') `
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
    $state = Read-InstallState $Context
    Write-Host "$($m.name) $($m.version) - Minecraft $($m.minecraft), Paper build $($m.server.build)"
    Write-Host "Installed: $(if ($state.version) { $state.version } else { 'no' })    Admin: $($state.owner)"
    Write-Host "Running:   $(Test-ServerRunning $Context)    Plugins: $(@($m.plugins).Count)    Datapacks: $(@($m.datapacks).Count)"
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
    'Get-ExpectedHash'
    'Read-ServerProperties'
    'Set-ServerProperty'
    'Expand-Template'
)
