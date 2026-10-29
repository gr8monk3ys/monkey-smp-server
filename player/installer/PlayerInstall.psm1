#Requires -Version 5.1
<#
.SYNOPSIS
    Monkey SMP player installer: puts the client pack into the official Minecraft Launcher.

.DESCRIPTION
    Does what the official Fabric installer and a modpack launcher would do, for players who only
    have the Minecraft Launcher:

        1. checks the launcher is installed (and warns if it is open)
        2. reads the client pack (.mrpack: modrinth.index.json + overrides/)
        3. places the Fabric version json in <MinecraftDir>\versions\<id>\
        4. downloads every client file into the game folder and checks its size and hash
        5. copies the pack's overrides (configs, options.txt) that don't exist yet
        6. adds or updates one "Monkey SMP" profile in launcher_profiles.json, keeping
           everything else in that file exactly as it was

    Running it again changes nothing unless the pack changed. Files a previous run placed and the
    new pack no longer has are removed; nothing else in the game folder is ever touched.

    Every public function takes one context object (New-PlayerContext). The context carries the
    folders and three adapters, which are the only seams to the outside world:

        Fetch       { param([string]$Url, [string]$OutFile) }  downloads one URL to one file.
        GetProcess  { param([string[]]$Name) }  returns the names of those processes that are running.
        Ask         { param([string]$Question) }  returns what the player typed.

    Importing this module has no side effects. Must stay plain ASCII and Windows PowerShell 5.1
    compatible (docs/adr/0003).
#>

# Module scope only: callers keep their own preference.
$ErrorActionPreference = 'Stop'

$script:UserAgent = 'gr8monk3ys/monkey-smp-server'
$script:Utf8 = New-Object System.Text.UTF8Encoding $false
# The key of our profile in launcher_profiles.json. Fixed, so updates replace it instead of adding more.
$script:ProfileKey = 'monkey-smp'
$script:StateFileName = '.monkey-client-state.json'
$script:BackupSuffix = '.monkey-smp-backup'
# The names before 2.10.0 (The Realms): an update moves the old game folder and drops the old profile.
$script:OldGameFolder = '.the-realms'
$script:OldStateFileName = '.realms-client-state.json'
$script:OldProfileKey = 'the-realms'
$script:OldBackupSuffix = '.the-realms-backup'
# The Microsoft Store / Xbox app launcher keeps its profiles in the second file. Both are updated if present.
$script:ProfileFiles = @('launcher_profiles.json', 'launcher_profiles_microsoft_store.json')
$script:LauncherProcesses = @('MinecraftLauncher', 'Minecraft')
$script:JvmFlags = '-XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 -XX:+UnlockExperimentalVMOptions ' +
    '-XX:+DisableExplicitGC -XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M -XX:G1ReservePercent=20'
# What modrinth.index.json may put in a version string that becomes a folder name.
$script:VersionPattern = '^[A-Za-z0-9][A-Za-z0-9._+-]*$'

# ================================================================ output

function Write-Step([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }
function Write-Ok([string]$Text) { Write-Host "    $Text" -ForegroundColor Green }
function Write-Note([string]$Text) { Write-Host "    $Text" -ForegroundColor Yellow }

function Read-Answer($Context, [string]$Question) {
    if ($Context.NonInteractive) { throw "Needs an answer but -NonInteractive was given: $Question" }
    return ([string](& $Context.Ask $Question)).Trim()
}

# ================================================================ JSON
# launcher_profiles.json belongs to the launcher, so it is parsed into plain dictionaries (which keep
# key order, empty objects and arrays) and written back with the same serializer. Windows PowerShell's
# own ConvertFrom-Json/ConvertTo-Json would reshape values it doesn't round-trip.

function New-JsonSerializer {
    Add-Type -AssemblyName System.Web.Extensions
    $s = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    $s.MaxJsonLength = [int]::MaxValue   # profile icons are data URIs and can be large
    $s.RecursionLimit = 1000
    return $s
}

function ConvertFrom-JsonText([string]$Text) {
    $value = (New-JsonSerializer).DeserializeObject($Text)
    return , $value
}

function ConvertTo-JsonText($Value) { return (New-JsonSerializer).Serialize($Value) }

function Test-JsonObject($Value) { return $Value -is [Collections.Generic.IDictionary[string, object]] }

# A field of a parsed JSON object, or $null if it (or the object) is missing. Wrap arrays in @().
function Get-Field($Object, [string]$Name) {
    if ((Test-JsonObject $Object) -and $Object.ContainsKey($Name)) { return $Object[$Name] }
    return $null
}

function Read-TextFile([string]$Path) { return [IO.File]::ReadAllText($Path, $script:Utf8) }

function Write-TextFile([string]$Path, [string]$Text) {
    New-Item -ItemType Directory -Force -Path (Split-Path $Path -Parent) | Out-Null
    [IO.File]::WriteAllText($Path, $Text, $script:Utf8)
}

# ================================================================ files

function Use-Zip { Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem }

function Get-Hash([string]$Path, [string]$Algorithm) {
    return (Get-FileHash -LiteralPath $Path -Algorithm $Algorithm).Hash.ToLower()
}

# File names come from upstream and may contain [ ] (e.g. "Clean Connected Glass [1.20-26.x].zip"), which
# PowerShell cmdlets treat as wildcards. Moves and copies go through .NET, which doesn't.
function Copy-FileExact([string]$From, [string]$To, [switch]$Move) {
    if ([IO.File]::Exists($To)) { [IO.File]::Delete($To) }
    if ($Move) { [IO.File]::Move($From, $To) } else { [IO.File]::Copy($From, $To) }
}

# A bracket-free temporary name next to $Path: the Fetch adapter may be a cmdlet that reads wildcards.
function New-PartPath([string]$Path) {
    return Join-Path (Split-Path $Path -Parent) (".download-" + [guid]::NewGuid().ToString('N') + '.part')
}

<#
.SYNOPSIS
    The full path of a pack-relative path ('mods/x.jar') inside $Root. Throws for anything that could
    land outside $Root: absolute paths, drive letters, '..' and other odd segments.
#>
function Resolve-GamePath {
    param([Parameter(Mandatory)] [string]$Root, [Parameter(Mandatory)] [AllowEmptyString()] [string]$RelativePath)
    $rel = $RelativePath.Replace('\', '/')
    $bad = (-not $rel) -or $rel.StartsWith('/') -or $rel.Contains(':')
    if (-not $bad) {
        foreach ($segment in $rel.Split('/')) {
            # Empty, '.', '..', '...' and names Windows would silently trim (trailing dot or space).
            if (-not $segment -or $segment -match '^\.+$' -or $segment -match '[. ]$') { $bad = $true }
        }
    }
    if ($bad) { throw "Unsafe path in the client pack: '$RelativePath'. The pack may be damaged; download it again." }
    $base = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    try { $full = [IO.Path]::GetFullPath([IO.Path]::Combine($base, $rel.Replace('/', '\'))) }
    catch { throw "Unsafe path in the client pack: '$RelativePath' ($($_.Exception.Message))." }
    if (-not $full.StartsWith($base + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe path in the client pack: '$RelativePath'. The pack may be damaged; download it again."
    }
    return $full
}

# ================================================================ adapters (production)

function Invoke-WebFetch {
    param([string]$Url, [string]$OutFile)
    $ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is very slow with the progress bar on 5.1
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $Url -OutFile $OutFile -UserAgent $script:UserAgent -UseBasicParsing -TimeoutSec 600
}

function Get-RunningProcessName {
    param([string[]]$Name)
    return @(Get-Process -Name $Name -ErrorAction SilentlyContinue | ForEach-Object { $_.ProcessName } | Select-Object -Unique)
}

function Read-HostAnswer {
    param([string]$Question)
    return Read-Host $Question
}

# ================================================================ context

<#
.SYNOPSIS
    Builds the context every other function takes: folders, the pack, the Fabric profile and adapters.
.PARAMETER MinecraftDir
    The Minecraft Launcher's data folder (normally %APPDATA%\.minecraft).
.PARAMETER GameDir
    The folder the profile plays from: mods, resource packs, shaders, configs, worlds, screenshots.
.PARAMETER Pack
    The client pack (.mrpack). Not needed for -Uninstall.
.PARAMETER FabricProfile
    The official Fabric launcher profile json for the pack's Minecraft and loader versions.
#>
function New-PlayerContext {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string]$MinecraftDir,
        [Parameter(Mandatory)] [string]$GameDir,
        [string]$Pack,
        [string]$FabricProfile,
        [scriptblock]$Fetch,
        [scriptblock]$GetProcess,
        [scriptblock]$Ask,
        [switch]$NonInteractive,
        [int]$RetryDelaySeconds = 5
    )
    if (-not $Fetch) { $Fetch = ${function:Invoke-WebFetch} }
    if (-not $GetProcess) { $GetProcess = ${function:Get-RunningProcessName} }
    if (-not $Ask) { $Ask = ${function:Read-HostAnswer} }
    $mc = [IO.Path]::GetFullPath($MinecraftDir).TrimEnd('\')
    $game = [IO.Path]::GetFullPath($GameDir).TrimEnd('\')
    if ($game -eq $mc) {
        throw "The game folder can't be the Minecraft Launcher's own folder ($mc). Pick a separate folder for Monkey SMP."
    }
    # Only the default game folder moves from the old default; a folder the player picked stays theirs.
    $oldGame = $null
    if ((Split-Path $game -Leaf) -eq '.monkey-smp') { $oldGame = Join-Path (Split-Path $game -Parent) $script:OldGameFolder }
    return [pscustomobject]@{
        MinecraftDir      = $mc
        GameDir           = $game
        OldGameDir        = $oldGame
        StateFile         = Join-Path $game $script:StateFileName
        Pack              = $Pack
        FabricProfile     = $FabricProfile
        Fetch             = $Fetch
        GetProcess        = $GetProcess
        Ask               = $Ask
        NonInteractive    = [bool]$NonInteractive
        RetryDelaySeconds = $RetryDelaySeconds
    }
}

<#
.SYNOPSIS
    Game memory in GB: the requested amount, else picked from the computer's RAM
    (8 GB or less: 3, up to 12 GB: 4, up to 16 GB: 6, more: 8).
#>
function Get-ClientMemoryGB {
    param([Parameter(Mandatory)] [double]$TotalBytes, [int]$Requested = 0)
    if ($Requested -gt 0) { return $Requested }
    # Windows reports a little less than the RAM printed on the box ("16 GB" is about 15.9).
    $total = $TotalBytes / 1GB
    if ($total -le 8.5) { return 3 }
    if ($total -le 12.5) { return 4 }
    if ($total -le 16.5) { return 6 }
    return 8
}

<#
.SYNOPSIS
    The one MonkeySMP-Client-*.mrpack in $Folder (where the player unzipped the download).
#>
function Find-ClientPack {
    param([Parameter(Mandatory)] [string]$Folder)
    $found = @(Get-ChildItem -LiteralPath $Folder -Filter 'MonkeySMP-Client-*.mrpack' -File -ErrorAction SilentlyContinue)
    if ($found.Count -eq 1) { return $found[0].FullName }
    if (-not $found.Count) {
        throw ("Couldn't find the client pack (MonkeySMP-Client-<version>.mrpack) in $Folder. Unzip the whole " +
            "MonkeySMP-Player download first (right-click it > Extract All), then run the installer from the unzipped folder.")
    }
    throw ("Found more than one client pack in ${Folder}: $(($found | ForEach-Object { $_.Name }) -join ', '). " +
        'Keep only the newest one, or unzip the new download into an empty folder.')
}

# ================================================================ client pack

<#
.SYNOPSIS
    Reads a client pack (.mrpack) without extracting it. Throws for anything that isn't a Fabric
    Minecraft pack or holds an unsafe path.
.OUTPUTS
    Path, Name, VersionId, Minecraft, Loader, Files (client files: Path, Size, Sha512, Sha1, Urls)
    and Overrides (Entry = name inside the zip, Path = relative path in the game folder).
#>
function Read-ClientPack {
    param([Parameter(Mandatory)] [string]$Path)
    if (-not [IO.File]::Exists($Path)) { throw "The client pack $Path is missing." }
    Use-Zip
    try { $zip = [IO.Compression.ZipFile]::OpenRead($Path) }
    catch { throw "The client pack $Path is damaged ($($_.Exception.Message)). Download it again." }
    $overrides = @()
    try {
        $entry = $zip.GetEntry('modrinth.index.json')
        if (-not $entry) { throw "$Path is not a Modrinth modpack (it has no modrinth.index.json)." }
        $reader = New-Object IO.StreamReader ($entry.Open(), $script:Utf8)
        try { $text = $reader.ReadToEnd() } finally { $reader.Dispose() }
        # client-overrides/ is applied after overrides/ in the format; with copy-if-missing that means it goes first.
        foreach ($prefix in 'client-overrides/', 'overrides/') {
            foreach ($e in $zip.Entries) {
                $name = $e.FullName.Replace('\', '/')
                if (-not $name.StartsWith($prefix) -or $name.EndsWith('/')) { continue }
                $rel = $name.Substring($prefix.Length)
                [void](Resolve-GamePath -Root 'C:\pack-check' -RelativePath $rel)
                $overrides += [pscustomobject]@{ Entry = $e.FullName; Path = $rel }
            }
        }
    } finally { $zip.Dispose() }

    try { $index = ConvertFrom-JsonText $text } catch { throw "modrinth.index.json in $Path is not valid JSON: $($_.Exception.Message)" }
    if (-not (Test-JsonObject $index) -or (Get-Field $index 'formatVersion') -ne 1 -or (Get-Field $index 'game') -ne 'minecraft') {
        throw "$Path is not a Minecraft modpack this installer understands (needs formatVersion 1, game minecraft)."
    }
    $deps = Get-Field $index 'dependencies'
    $mc = [string](Get-Field $deps 'minecraft')
    $loader = [string](Get-Field $deps 'fabric-loader')
    if (-not $mc -or -not $loader) { throw "$Path is not a Fabric modpack (its dependencies need minecraft and fabric-loader)." }
    foreach ($v in $mc, $loader) {
        if ($v -notmatch $script:VersionPattern) { throw "$Path has an unexpected version string: '$v'." }
    }

    $files = @()
    $seen = @{}
    foreach ($f in @(Get-Field $index 'files')) {
        $rel = [string](Get-Field $f 'path')
        [void](Resolve-GamePath -Root 'C:\pack-check' -RelativePath $rel)
        if ((Get-Field (Get-Field $f 'env') 'client') -eq 'unsupported') { continue }
        $key = $rel.Replace('\', '/').ToLower()
        if ($seen.ContainsKey($key)) { throw "$Path lists $rel twice." }
        $seen[$key] = $true
        $hashes = Get-Field $f 'hashes'
        $sha512 = [string](Get-Field $hashes 'sha512')
        $sha1 = [string](Get-Field $hashes 'sha1')
        if (-not $sha512 -and -not $sha1) { throw "$Path has no sha512 or sha1 for $rel." }
        $urls = @(@(Get-Field $f 'downloads') | Where-Object { ([string]$_) -match '^https://' } | ForEach-Object { [string]$_ })
        if (-not $urls.Count) { throw "$Path has no https download for $rel." }
        $size = Get-Field $f 'fileSize'
        if ($null -eq $size) { throw "$Path has no fileSize for $rel." }
        $files += [pscustomobject]@{
            Path   = $rel.Replace('\', '/')
            Size   = [long]$size
            Sha512 = $sha512.ToLower()
            Sha1   = $sha1.ToLower()
            Urls   = $urls
        }
    }
    return [pscustomobject]@{
        Path      = $Path
        Name      = [string](Get-Field $index 'name')
        VersionId = [string](Get-Field $index 'versionId')
        Minecraft = $mc
        Loader    = $loader
        Files     = $files
        Overrides = $overrides
    }
}

<#
.SYNOPSIS
    Reads the Fabric launcher profile json and checks it is the one for the pack's Minecraft and loader.
.OUTPUTS
    Id ('fabric-loader-0.19.5-26.3'), Path.
#>
function Read-FabricProfile {
    param([Parameter(Mandatory)] [string]$Path, [Parameter(Mandatory)] $Pack)
    if (-not $Path -or -not [IO.File]::Exists($Path)) {
        throw "The Fabric profile (installer\fabric-profile.json) is missing. Unzip the whole MonkeySMP-Player download again."
    }
    try { $json = ConvertFrom-JsonText (Read-TextFile $Path) } catch { throw "$Path is not valid JSON: $($_.Exception.Message)" }
    $want = "fabric-loader-$($Pack.Loader)-$($Pack.Minecraft)"
    $id = [string](Get-Field $json 'id')
    $parent = [string](Get-Field $json 'inheritsFrom')
    if ($id -ne $want -or $parent -ne $Pack.Minecraft) {
        throw ("The Fabric profile is for '$id' (Minecraft '$parent'), but the client pack needs '$want'. " +
            'The download is mixed up; get the MonkeySMP-Player zip again.')
    }
    return [pscustomobject]@{ Id = $id; Path = $Path }
}

# ================================================================ launcher

# The launcher profile files that exist. Throws the "install the launcher" message if there are none.
function Get-LauncherProfileFile($Context) {
    $found = @($script:ProfileFiles | ForEach-Object { Join-Path $Context.MinecraftDir $_ } | Where-Object { [IO.File]::Exists($_) })
    if (-not $found.Count) {
        throw ("Couldn't find the Minecraft Launcher's settings (launcher_profiles.json in $($Context.MinecraftDir)). " +
            'Install the Minecraft Launcher from minecraft.net, start it once, sign in, close it, then run this again.')
    }
    return $found
}

<#
.SYNOPSIS
    Waits until the Minecraft Launcher is closed: it rewrites launcher_profiles.json when it exits,
    which would undo the new profile. Never stops it. With -NonInteractive it only warns.
#>
function Wait-LauncherClosed {
    param([Parameter(Mandatory)] $Context)
    while ($true) {
        $running = @(& $Context.GetProcess $script:LauncherProcesses | Where-Object { $_ })
        if (-not $running.Count) { return }
        Write-Note 'The Minecraft Launcher is open. It saves its settings when it closes, which can undo this installer.'
        if ($Context.NonInteractive) {
            Write-Note 'Continuing anyway (-NonInteractive). Restart the launcher afterwards.'
            return
        }
        $a = Read-Answer $Context 'Close the Minecraft Launcher (all its windows), then press Enter. Or type SKIP to continue anyway'
        if ($a -match '^skip$') { return }
    }
}

# Every value of a launcher_profiles.json except our profile, serialized, so a change can be detected.
function Get-OtherSettings($Data, [string]$Key = $script:ProfileKey) {
    $snap = @{}
    foreach ($k in @($Data.Keys)) { if ($k -ne 'profiles') { $snap["setting $k"] = ConvertTo-JsonText $Data[$k] } }
    $profiles = Get-Field $Data 'profiles'
    if (Test-JsonObject $profiles) {
        foreach ($k in @($profiles.Keys)) { if ($k -ne $Key) { $snap["profile $k"] = ConvertTo-JsonText $profiles[$k] } }
    }
    return $snap
}

function Test-SameSettings([hashtable]$A, [hashtable]$B) {
    if ($A.Count -ne $B.Count) { return $false }
    foreach ($k in $A.Keys) { if (-not $B.ContainsKey($k) -or $B[$k] -cne $A[$k]) { return $false } }
    return $true
}

function Get-LauncherTimestamp { return (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'", [Globalization.CultureInfo]::InvariantCulture) }

<#
.SYNOPSIS
    Sets (or with -Remove, deletes) our profile in one launcher_profiles.json and keeps every other
    key exactly as it was. -Key picks another profile to remove (the one from before 2.10.0). The first change makes <file>.monkey-smp-backup. Returns $true if the file changed.
.PARAMETER Fields
    The profile fields to set. Other fields of an existing profile (e.g. a resolution the player set) are kept.
#>
function Edit-LauncherProfile {
    param([Parameter(Mandatory)] [string]$Path, [Collections.IDictionary]$Fields, [switch]$Remove,
        [string]$Key = $script:ProfileKey)
    if (-not $Remove -and -not $Fields) { throw 'Edit-LauncherProfile needs -Fields or -Remove.' }
    $original = Read-TextFile $Path
    try { $data = ConvertFrom-JsonText $original } catch { $data = $null }
    if (-not (Test-JsonObject $data)) {
        throw "$Path is damaged (not valid JSON). Start the Minecraft Launcher once so it repairs it, close it, then run this again."
    }
    $before = Get-OtherSettings $data $Key
    $profiles = Get-Field $data 'profiles'
    if ($null -eq $profiles) {
        if ($Remove) { return $false }
        $profiles = [Collections.Generic.Dictionary[string, object]]::new()
        $data['profiles'] = $profiles
    } elseif (-not (Test-JsonObject $profiles)) {
        throw "$Path has an unexpected format ('profiles' is not an object). Nothing was changed."
    }

    if ($Remove) {
        if (-not $profiles.ContainsKey($Key)) { return $false }
        [void]$profiles.Remove($Key)
    } else {
        $p = Get-Field $profiles $Key
        if (-not (Test-JsonObject $p)) { $p = [Collections.Generic.Dictionary[string, object]]::new() }
        $same = $true
        foreach ($k in $Fields.Keys) { if ((Get-Field $p $k) -cne $Fields[$k]) { $same = $false } }
        if ($same -and (Get-Field $p 'created') -and (Get-Field $p 'lastUsed')) { return $false }
        # [string]: the serializer can't walk PowerShell's wrapped objects (function output is wrapped).
        foreach ($k in $Fields.Keys) { $p[$k] = [string]$Fields[$k] }
        $now = [string](Get-LauncherTimestamp)
        if (-not (Get-Field $p 'created')) { $p['created'] = $now }
        # Newest lastUsed: the launcher (sorted by last played) shows it next to the Play button.
        $p['lastUsed'] = $now
        $profiles[$Key] = $p.psobject.BaseObject
    }

    $text = ConvertTo-JsonText $data
    if ($text -ceq $original) { return $false }
    # Re-parse what would be written: every other setting and profile must be unchanged.
    $check = ConvertFrom-JsonText $text
    if (-not (Test-SameSettings $before (Get-OtherSettings $check $Key))) {
        throw "Changing $Path would also change other launcher settings, so nothing was changed. Please report this."
    }
    $mine = Get-Field (Get-Field $check 'profiles') $Key
    if ($Remove -eq ($null -ne $mine)) { throw "Couldn't update the profile in $Path. Nothing was changed." }

    $backup = $Path + $script:BackupSuffix
    if (-not [IO.File]::Exists($backup)) { Copy-FileExact $Path $backup }
    $tmp = New-PartPath $Path
    try {
        Write-TextFile $tmp $text
        [IO.File]::Replace($tmp, $Path, [NullString]::Value)   # $null would arrive as ""
    } finally {
        if ([IO.File]::Exists($tmp)) { [IO.File]::Delete($tmp) }
    }
    return $true
}

<#
.SYNOPSIS
    The profile fields for the pack: name, version, game folder and memory.
#>
function Get-ProfileField {
    param([Parameter(Mandatory)] $Context, [Parameter(Mandatory)] $Pack, [Parameter(Mandatory)] [string]$VersionId, [Parameter(Mandatory)] [int]$MemoryGB)
    return [ordered]@{
        name          = (Get-ProfileName $Pack)
        type          = 'custom'
        lastVersionId = $VersionId
        gameDir       = $Context.GameDir
        javaArgs      = "-Xmx${MemoryGB}G -Xms${MemoryGB}G $script:JvmFlags"
        icon          = 'Grass'
    }
}

function Get-ProfileName($Pack) { return ("Monkey SMP $($Pack.VersionId)").Trim() }

# ================================================================ client files

function Test-ClientFile([string]$Path, $File) {
    if (-not [IO.File]::Exists($Path)) { return $false }
    if ((New-Object IO.FileInfo $Path).Length -ne $File.Size) { return $false }
    if ($File.Sha512) { return (Get-Hash $Path SHA512) -eq $File.Sha512 }
    return (Get-Hash $Path SHA1) -eq $File.Sha1
}

# Downloads one pack file to $Path unless the file there is already correct. Only a file with the
# right size and hash ever reaches $Path. Returns $true if it downloaded.
function Save-ClientFile($Context, $File, [string]$Path) {
    if (Test-ClientFile $Path $File) { return $false }
    New-Item -ItemType Directory -Force -Path (Split-Path $Path -Parent) | Out-Null
    $part = New-PartPath $Path
    $urls = @($File.Urls)
    for ($try = 1; $try -le 3; $try++) {
        $url = $urls[($try - 1) % $urls.Count]
        try {
            if ([IO.File]::Exists($part)) { [IO.File]::Delete($part) }
            $null = & $Context.Fetch $url $part
            if (-not [IO.File]::Exists($part)) { throw 'the download produced no file' }
            $got = (New-Object IO.FileInfo $part).Length
            if ($got -ne $File.Size) { throw "wrong size (expected $($File.Size) bytes, got $got)" }
            if ($File.Sha512) { $algo = 'SHA512'; $want = $File.Sha512 } else { $algo = 'SHA1'; $want = $File.Sha1 }
            $hash = Get-Hash $part $algo
            if ($hash -ne $want) { throw "hash mismatch (expected $want, got $hash)" }
            Copy-FileExact $part $Path -Move
            return $true
        } catch {
            if ([IO.File]::Exists($part)) { [IO.File]::Delete($part) }
            if ($try -eq 3) { throw "Could not download $($File.Path) from ${url}: $($_.Exception.Message)" }
            Write-Note "Download of $($File.Path) failed ($($_.Exception.Message)), retrying..."
            if ($Context.RetryDelaySeconds -gt 0) { Start-Sleep -Seconds ($Context.RetryDelaySeconds * $try) }
        }
    }
}

# Install state (.monkey-client-state.json in the game folder): the pack files the last run placed.
function Read-ClientState($Context) {
    if (-not [IO.File]::Exists($Context.StateFile)) { return @() }
    try { $s = ConvertFrom-JsonText (Read-TextFile $Context.StateFile) } catch { $s = $null }
    if (-not (Test-JsonObject $s)) {
        Write-Note "Ignoring a damaged $script:StateFileName (old mods may have to be removed by hand)."
        return @()
    }
    return @(@(Get-Field $s 'files') | ForEach-Object { [string]$_ } | Where-Object { $_ })
}

function Write-ClientState($Context, $Pack, [string[]]$Files) {
    # Plain .NET values only: the serializer can't walk PowerShell's wrapped objects.
    $state = [Collections.Generic.Dictionary[string, object]]::new()
    $state['pack'] = [string]$Pack.Name
    $state['version'] = [string]$Pack.VersionId
    $state['files'] = [string[]]@($Files | Where-Object { $_ } | Sort-Object -Unique)
    Write-TextFile $Context.StateFile (ConvertTo-JsonText $state)
}

<#
.SYNOPSIS
    Brings the game folder's pack files in line with the pack: downloads (and checks) every file that
    isn't already correct, then removes files an earlier run placed that the pack no longer has.
    Nothing else in the game folder is touched. Returns @{ Downloaded; Removed; Total }.
#>
function Sync-ClientFiles {
    param([Parameter(Mandatory)] $Context, [Parameter(Mandatory)] $Pack)
    $previous = @(Read-ClientState $Context)
    $wanted = @($Pack.Files | ForEach-Object { $_.Path })
    $wantedKeys = @{}
    foreach ($w in $wanted) { $wantedKeys[$w.ToLower()] = $true }
    # Until this run finishes, both old and new files count as ours, so an interrupted run can be cleaned up later.
    Write-ClientState $Context $Pack (@($previous) + @($wanted))

    $total = $wanted.Count
    $bytes = 0
    foreach ($f in $Pack.Files) { $bytes += $f.Size }
    Write-Step "Checking $total files ($([math]::Round($bytes / 1MB)) MB); missing ones are downloaded"
    $downloaded = 0
    $i = 0
    foreach ($f in $Pack.Files) {
        $i++
        $dest = Resolve-GamePath -Root $Context.GameDir -RelativePath $f.Path
        if (Save-ClientFile $Context $f $dest) {
            $downloaded++
            Write-Ok "[$i/$total] $($f.Path)"
        }
    }
    $removed = 0
    foreach ($old in $previous) {
        if ($wantedKeys.ContainsKey($old.ToLower())) { continue }
        try { $path = Resolve-GamePath -Root $Context.GameDir -RelativePath $old } catch { continue }
        if ([IO.File]::Exists($path)) {
            [IO.File]::Delete($path)
            Write-Note "removed old $old"
            $removed++
        }
    }
    Write-ClientState $Context $Pack $wanted
    Write-Ok "$total files ok ($downloaded downloaded, $removed old removed)."
    return [pscustomobject]@{ Downloaded = $downloaded; Removed = $removed; Total = $total }
}

<#
.SYNOPSIS
    Copies the pack's overrides (configs, options.txt, ...) into the game folder, but only files that
    don't exist yet: once a file exists, the player's version wins. Returns how many were copied.
#>
function Install-Overrides {
    param([Parameter(Mandatory)] $Context, [Parameter(Mandatory)] $Pack)
    $copied = 0
    if (-not @($Pack.Overrides).Count) { return 0 }
    Use-Zip
    $zip = [IO.Compression.ZipFile]::OpenRead($Pack.Path)
    try {
        foreach ($o in $Pack.Overrides) {
            $dest = Resolve-GamePath -Root $Context.GameDir -RelativePath $o.Path
            if ([IO.File]::Exists($dest)) { continue }
            New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
            $part = New-PartPath $dest
            try {
                $in = $zip.GetEntry($o.Entry).Open()
                try {
                    $out = [IO.File]::Create($part)
                    try { $in.CopyTo($out) } finally { $out.Dispose() }
                } finally { $in.Dispose() }
                Copy-FileExact $part $dest -Move
            } finally {
                if ([IO.File]::Exists($part)) { [IO.File]::Delete($part) }
            }
            $copied++
        }
    } finally { $zip.Dispose() }
    return $copied
}

# Places the Fabric version json where the launcher looks for versions (all the Fabric installer does there).
function Install-FabricVersion($Context, $Fabric) {
    $dest = Join-Path $Context.MinecraftDir "versions\$($Fabric.Id)\$($Fabric.Id).json"
    $bytes = [IO.File]::ReadAllBytes($Fabric.Path)
    if ([IO.File]::Exists($dest) -and [Convert]::ToBase64String([IO.File]::ReadAllBytes($dest)) -eq [Convert]::ToBase64String($bytes)) {
        return $false
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
    [IO.File]::WriteAllBytes($dest, $bytes)
    return $true
}

# ================================================================ install / uninstall

<#
.SYNOPSIS
    Moves the game folder from before 2.10.0 (%APPDATA%\.the-realms) to the new one, so an update keeps the
    player's worlds, screenshots and settings. Only when the new folder doesn't exist yet. Returns $true if it moved.
#>
function Move-OldGameFolder($Context) {
    $old = $Context.OldGameDir
    if (-not $old -or -not [IO.Directory]::Exists($old)) { return $false }
    if ([IO.Directory]::Exists($Context.GameDir)) {
        Write-Note "Both $old and $($Context.GameDir) exist; using the second. Move anything you want to keep across by hand."
        return $false
    }
    try {
        [IO.Directory]::Move($old, $Context.GameDir)
    } catch {
        throw "Couldn't move $old to $($Context.GameDir): $($_.Exception.Message) Close Minecraft (and anything else using files in that folder), then run this again."
    }
    $oldState = Join-Path $Context.GameDir $script:OldStateFileName
    if ([IO.File]::Exists($oldState)) { [IO.File]::Move($oldState, $Context.StateFile) }
    Write-Ok "Moved your game folder from $old to $($Context.GameDir) (Monkey SMP's new name)."
    return $true
}

<#
.SYNOPSIS
    Before 2.10.0 the launcher profile was 'the-realms'. It goes once the folder it plays from has moved (or is
    gone); a profile with a folder that is still there stays, with a note.
#>
function Remove-OldProfile($Context, [string]$File) {
    try { $data = ConvertFrom-JsonText (Read-TextFile $File) } catch { return }
    $old = Get-Field (Get-Field $data 'profiles') $script:OldProfileKey
    if (-not (Test-JsonObject $old)) { return }
    $dir = [string](Get-Field $old 'gameDir')
    if ($dir -and [IO.Directory]::Exists($dir)) {
        Write-Note "The old 'The Realms' profile still plays from $dir; delete it in the launcher once you've moved anything you want over."
        return
    }
    if (Edit-LauncherProfile -Path $File -Remove -Key $script:OldProfileKey) { Write-Ok "Removed the old profile from $File." }
}

<#
.SYNOPSIS
    Install or update: makes the launcher profile, the Fabric version and the game folder match the
    pack. Idempotent. Returns a summary (Downloaded, Removed, Total, OverridesCopied, VersionChanged,
    ProfileChanged, ProfileName, VersionId).
#>
function Install-Client {
    param([Parameter(Mandatory)] $Context, [Parameter(Mandatory)] [ValidateRange(1, 64)] [int]$MemoryGB)
    Write-Step 'Checking the Minecraft Launcher'
    $profileFiles = Get-LauncherProfileFile $Context
    Wait-LauncherClosed $Context
    Write-Ok "Found it in $($Context.MinecraftDir)"

    if (-not $Context.Pack) { throw 'No client pack was given.' }
    $pack = Read-ClientPack -Path $Context.Pack
    $fabric = Read-FabricProfile -Path $Context.FabricProfile -Pack $pack
    Write-Step "Installing $($pack.Name) $($pack.VersionId) (Minecraft $($pack.Minecraft), Fabric loader $($pack.Loader))"

    $versionChanged = Install-FabricVersion $Context $fabric
    if ($versionChanged) { Write-Ok "Fabric added to the launcher ($($fabric.Id))." } else { Write-Ok "Fabric is already in the launcher ($($fabric.Id))." }

    $null = Move-OldGameFolder $Context
    New-Item -ItemType Directory -Force -Path $Context.GameDir | Out-Null
    $sync = Sync-ClientFiles -Context $Context -Pack $pack

    Write-Step 'Copying settings that are not there yet'
    $copied = Install-Overrides -Context $Context -Pack $pack
    Write-Ok "$copied new settings file(s) copied (your own settings are never replaced)."

    Write-Step 'Adding Monkey SMP to the Minecraft Launcher'
    $fields = Get-ProfileField -Context $Context -Pack $pack -VersionId $fabric.Id -MemoryGB $MemoryGB
    $profileChanged = $false
    foreach ($file in $profileFiles) {
        # The first backup, made before the first install, keeps being the first backup under its new name.
        $oldBackup = $file + $script:OldBackupSuffix
        if ([IO.File]::Exists($oldBackup) -and -not [IO.File]::Exists($file + $script:BackupSuffix)) {
            [IO.File]::Move($oldBackup, $file + $script:BackupSuffix)
        }
        if (Edit-LauncherProfile -Path $file -Fields $fields) { $profileChanged = $true }
        Remove-OldProfile $Context $file
    }
    if ($profileChanged) { Write-Ok "Profile '$($fields.name)' saved ($MemoryGB GB memory)." } else { Write-Ok "Profile '$($fields.name)' is already up to date." }

    Write-Host ''
    Write-Host 'Done! To play:' -ForegroundColor Green
    Write-Host "  1. Open the Minecraft Launcher and sign in."
    Write-Host "  2. Pick '$($fields.name)' next to the Play button (or under Installations)."
    Write-Host '  3. Press Play. The first start takes a few minutes.'
    Write-Host '  4. In the game: Multiplayer > Add Server, and type the address your host gave you.'
    Write-Host "  Your mods, worlds and screenshots for Monkey SMP live in $($Context.GameDir)"
    return [pscustomobject]@{
        Downloaded      = $sync.Downloaded
        Removed         = $sync.Removed
        Total           = $sync.Total
        OverridesCopied = $copied
        VersionChanged  = $versionChanged
        ProfileChanged  = $profileChanged
        ProfileName     = $fields.name
        VersionId       = $fabric.Id
    }
}

<#
.SYNOPSIS
    Removes Monkey SMP profile from the launcher and, after a typed confirmation (none with
    -NonInteractive), the game folder. The Fabric version json stays: it is harmless and other
    profiles may use it. Returns @{ ProfileRemoved; GameDirRemoved }.
#>
function Uninstall-Client {
    param([Parameter(Mandatory)] $Context)
    $profileRemoved = $false
    $files = @($script:ProfileFiles | ForEach-Object { Join-Path $Context.MinecraftDir $_ } | Where-Object { [IO.File]::Exists($_) })
    if ($files.Count) {
        Wait-LauncherClosed $Context
        foreach ($file in $files) {
            if (Edit-LauncherProfile -Path $file -Remove) { $profileRemoved = $true }
            # The profile from before 2.10.0 is Monkey SMP's too.
            if (Edit-LauncherProfile -Path $file -Remove -Key $script:OldProfileKey) { $profileRemoved = $true }
        }
    }
    if ($profileRemoved) { Write-Ok 'Removed Monkey SMP from the Minecraft Launcher.' } else { Write-Ok 'The Minecraft Launcher has no Monkey SMP profile.' }
    Write-Note 'The Fabric version (in the launcher''s versions folder) stays; it is harmless and other profiles may use it.'

    $gameRemoved = $false
    if ([IO.Directory]::Exists($Context.GameDir)) {
        if (-not [IO.File]::Exists($Context.StateFile)) {
            Write-Note "Not deleting $($Context.GameDir): this installer didn't make it (no $script:StateFileName inside)."
        } else {
            $go = $Context.NonInteractive
            if (-not $go) {
                Write-Host ''
                Write-Host "Monkey SMP game folder is $($Context.GameDir)" -ForegroundColor White
                Write-Host 'Deleting it also deletes the worlds, screenshots and settings inside it.' -ForegroundColor White
                $a = Read-Answer $Context 'Type DELETE to delete it, or just press Enter to keep it'
                $go = $a -ceq 'DELETE'
            }
            if ($go) {
                [IO.Directory]::Delete($Context.GameDir, $true)
                $gameRemoved = $true
                Write-Ok "Deleted $($Context.GameDir)"
            } else {
                Write-Ok "Kept $($Context.GameDir)"
            }
        }
    }
    if ($Context.OldGameDir -and [IO.Directory]::Exists($Context.OldGameDir)) {
        Write-Note "Not deleting $($Context.OldGameDir), the game folder from before 2.10.0; delete it by hand if you don't need it."
    }
    return [pscustomobject]@{ ProfileRemoved = $profileRemoved; GameDirRemoved = $gameRemoved }
}
