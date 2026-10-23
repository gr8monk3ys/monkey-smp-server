#Requires -Version 5.1
<#
.SYNOPSIS
    Unit tests for player/installer/PlayerInstall.psm1 (Pester 5). No network, a few seconds.

.DESCRIPTION
    Every test builds a throwaway world in TestDrive: tiny upstream files, a client pack (.mrpack)
    that pins their real hashes, a Fabric profile json and a fake Minecraft Launcher folder whose
    launcher_profiles.json has the shape of a real one (fake values). Downloads go through a Fetch
    adapter that copies from a url -> file map, and the launcher process check and prompts through
    fake adapters, so the module is exercised through its public interface only. The real
    %APPDATA%\.minecraft is never touched.

.EXAMPLE
    Invoke-Pester -Path tests/Player.Tests.ps1 -Output Detailed
#>

BeforeAll {
    $script:RepoRoot = Split-Path $PSScriptRoot -Parent
    Import-Module (Join-Path $script:RepoRoot 'player\installer\PlayerInstall.psm1') -Force
    Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
    $script:Utf8 = New-Object System.Text.UTF8Encoding $false
    $script:Mc = '1.0'
    $script:Loader = '0.1.0'
    $script:FabricId = 'fabric-loader-0.1.0-1.0'

    function Get-FileSha([string]$Path, [string]$Algorithm = 'SHA512') { (Get-FileHash -LiteralPath $Path -Algorithm $Algorithm).Hash.ToLower() }

    function Write-Text([string]$Path, [string]$Text) {
        New-Item -ItemType Directory -Force -Path (Split-Path $Path -Parent) | Out-Null
        [IO.File]::WriteAllText($Path, $Text, $script:Utf8)
    }

    function Read-Text([string]$Path) { [IO.File]::ReadAllText($Path, $script:Utf8) }

    function New-Zip([string]$Path, [hashtable]$Files) {
        New-Item -ItemType Directory -Force -Path (Split-Path $Path -Parent) | Out-Null
        if ([IO.File]::Exists($Path)) { [IO.File]::Delete($Path) }
        $zip = [IO.Compression.ZipFile]::Open($Path, [IO.Compression.ZipArchiveMode]::Create)
        try {
            foreach ($name in $Files.Keys) {
                $s = $zip.CreateEntry($name).Open()
                try { $b = $script:Utf8.GetBytes([string]$Files[$name]); $s.Write($b, 0, $b.Length) } finally { $s.Dispose() }
            }
        } finally { $zip.Dispose() }
    }

    # A launcher_profiles.json shaped like the real one (minified, as the launcher writes it), with
    # a data-URI icon, a non-ASCII name, nested objects, an empty object and arrays.
    function Get-LauncherProfilesText {
        $e = [string][char]0xE9
        return '{"settings":{"enableAnalytics":true,"enableAdvanced":false,"keepLauncherOpen":false,"soundOn":false,' +
            '"showMenu":false,"enableSnapshots":false,"enableHistorical":false,"enableReleases":true,' +
            '"profileSorting":"ByLastPlayed","showGameLog":false,"crashAssistance":true},' +
            '"launcherVersion":{"format":21,"name":"","profilesFormat":2},"clientToken":"0123456789abcdef0123456789abcdef",' +
            '"profiles":{"0000000000000000000000000000aaaa":{"lastUsed":"1970-01-01T00:00:00.000Z","lastVersionId":"latest-snapshot",' +
            '"created":"1970-01-01T00:00:00.000Z","icon":"Crafting_Table","name":"","type":"latest-snapshot"},' +
            '"fabric-loader-26.3":{"lastUsed":"2026-10-05T00:20:50-0700","lastVersionId":"fabric-loader-0.19.5-26.3",' +
            '"created":"2026-10-05T00:20:50-0700","name":"fabric-loader-26.3",' +
            '"icon":"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",' +
            '"type":"custom"},"0000000000000000000000000000bbbb":{"lastUsed":"2021-03-20T00:41:45.927Z","lastVersionId":"latest-release",' +
            '"created":"1970-01-02T00:00:00.000Z","icon":"Grass","name":"Caf' + $e + ' world","type":"custom",' +
            '"gameDir":"C:\\Games\\cafe","javaArgs":"-Xmx2G","resolution":{"height":480,"width":854},"tags":[],"extra":{}}},' +
            '"emptyThing":{},"emptyList":[],"oneItem":[1.5]}'
    }

    # A fixture: upstream files served by a Fetch adapter, a fake launcher folder, a game folder,
    # a Fabric profile json. $F.Fetched counts downloads per url; $F.Running fakes running processes.
    function New-Fixture {
        $dir = Join-Path $TestDrive ([guid]::NewGuid().ToString('N').Substring(0, 8))
        $F = @{
            Dir       = $dir
            Upstream  = Join-Path $dir 'upstream'
            Minecraft = Join-Path $dir 'minecraft'
            Game      = Join-Path $dir 'game [x]'
            Fabric    = Join-Path $dir 'installer\fabric-profile.json'
            Map       = @{}
            Fetched   = @{}
            Running   = New-Object Collections.ArrayList
            Answers   = New-Object Collections.Queue
            Asked     = New-Object Collections.ArrayList
        }
        New-Item -ItemType Directory -Force -Path $F.Upstream, $F.Minecraft | Out-Null
        $F.Profiles = Join-Path $F.Minecraft 'launcher_profiles.json'
        Write-Text $F.Profiles (Get-LauncherProfilesText)
        Write-Text $F.Fabric (New-FabricProfileText $script:FabricId $script:Mc)
        $map = $F.Map
        $fetched = $F.Fetched
        $F.Fetch = {
            param([string]$Url, [string]$OutFile)
            $fetched[$Url] = 1 + [int]$fetched[$Url]
            if (-not $map.ContainsKey($Url)) { throw "404 Not Found: $Url" }
            [IO.File]::Copy($map[$Url], $OutFile, $true)
        }.GetNewClosure()
        $running = $F.Running
        $F.GetProcess = { param([string[]]$Name) @($running | Where-Object { $Name -contains $_ }) }.GetNewClosure()
        $answers = $F.Answers
        $asked = $F.Asked
        $F.Ask = {
            param([string]$Question)
            [void]$asked.Add($Question)
            if (-not $answers.Count) { throw "unexpected question: $Question" }
            $answers.Dequeue()
        }.GetNewClosure()
        return $F
    }

    function New-FabricProfileText([string]$Id, [string]$InheritsFrom) {
        return ('{"id":"' + $Id + '","inheritsFrom":"' + $InheritsFrom + '","releaseTime":"2026-10-04T15:06:22+0000",' +
            '"type":"release","mainClass":"net.fabricmc.loader.impl.launch.knot.KnotClient",' +
            '"arguments":{"game":[],"jvm":["-DFabricMcEmu= net.minecraft.client.main.Main "]},"libraries":[]}')
    }

    # Writes an upstream file, serves it at a url and returns its modrinth.index.json entry.
    function New-PackFile($F, [string]$Path, [string]$Content, [string]$Client = 'required', [switch]$NoSha512) {
        $up = Join-Path $F.Upstream ([guid]::NewGuid().ToString('N'))
        Write-Text $up $Content
        $url = "https://fixture.invalid/$([guid]::NewGuid().ToString('N'))/$([uri]::EscapeDataString((Split-Path $Path -Leaf)))"
        $F.Map[$url] = $up
        $hashes = [ordered]@{ sha1 = Get-FileSha $up 'SHA1' }
        if (-not $NoSha512) { $hashes.sha512 = Get-FileSha $up }
        return [ordered]@{
            path      = $Path
            hashes    = $hashes
            env       = [ordered]@{ client = $Client; server = 'unsupported' }
            downloads = @($url)
            fileSize  = (Get-Item -LiteralPath $up).Length
        }
    }

    # A client pack with the given index files and overrides (zip entry name -> text).
    function New-Pack($F, [object[]]$Files, [hashtable]$Overrides = @{}, [string]$Version = '1.0.0', [string]$Mc = $script:Mc, [string]$Loader = $script:Loader) {
        $index = [ordered]@{
            formatVersion = 1
            game          = 'minecraft'
            versionId     = $Version
            name          = 'Monkey SMP - Client'
            summary       = 'Fixture pack'
            files         = @($Files)
            dependencies  = [ordered]@{ minecraft = $Mc; 'fabric-loader' = $Loader }
        }
        $entries = @{ 'modrinth.index.json' = (ConvertTo-Json -InputObject $index -Depth 10) }
        foreach ($k in $Overrides.Keys) { $entries[$k] = $Overrides[$k] }
        $path = Join-Path $F.Dir "TheRealms-Client-$Version.mrpack"
        New-Zip $path $entries
        return $path
    }

    function New-Context($F, [string]$Pack, [switch]$Interactive) {
        return New-PlayerContext -MinecraftDir $F.Minecraft -GameDir $F.Game -Pack $Pack -FabricProfile $F.Fabric `
            -Fetch $F.Fetch -GetProcess $F.GetProcess -Ask $F.Ask -NonInteractive:(-not $Interactive) -RetryDelaySeconds 0
    }

    # The standard pack: two mods (one with [ ] in its name), a resource pack, a server-only mod,
    # and overrides with a config, options.txt and a shader preset.
    function New-StandardPack($F) {
        $F.ModA = New-PackFile $F 'mods/alpha-1.0.jar' 'alpha one'
        $F.ModB = New-PackFile $F 'mods/beta [fabric]-2.0.jar' 'beta two'
        $F.Res = New-PackFile $F 'resourcepacks/Fancy Pack [1.0].zip' 'pixels'
        $F.ServerOnly = New-PackFile $F 'mods/server-only.jar' 'server stuff' -Client 'unsupported'
        $F.Overrides = @{
            'overrides/config/alpha.toml'          = "speed = 1`n"
            'overrides/options.txt'                = "renderDistance:8`n"
            'overrides/shaderpacks/Shader.zip.txt' = "preset=high`n"
        }
        return New-Pack $F @($F.ModA, $F.ModB, $F.Res, $F.ServerOnly) $F.Overrides
    }

    function Get-Profiles([string]$Path) { (Read-Text $Path | ConvertFrom-Json).profiles }

    # Everything in a launcher_profiles.json except our profile, each value as compact JSON.
    function Get-OtherJson([string]$Path) {
        $o = Read-Text $Path | ConvertFrom-Json
        $out = [ordered]@{}
        foreach ($p in $o.PSObject.Properties) {
            if ($p.Name -ne 'profiles') { $out["setting $($p.Name)"] = ConvertTo-Json -InputObject $p.Value -Depth 50 -Compress }
        }
        foreach ($p in $o.profiles.PSObject.Properties) {
            if ($p.Name -ne 'the-realms') { $out["profile $($p.Name)"] = ConvertTo-Json -InputObject $p.Value -Depth 50 -Compress }
        }
        return $out
    }

    function Get-PartFile([string]$Dir) {
        if (-not (Test-Path -LiteralPath $Dir)) { return @() }
        return @(Get-ChildItem -LiteralPath $Dir -Recurse -Force -File -Filter '*.part')
    }
}

Describe 'Install-Client' {
    BeforeEach {
        $F = New-Fixture
        $script:pack = New-StandardPack $F
        $script:original = [IO.File]::ReadAllBytes($F.Profiles)
        $script:otherBefore = Get-OtherJson $F.Profiles
        $script:r = Install-Client -Context (New-Context $F $script:pack) -MemoryGB 4
    }

    Context 'fresh install' {
        It 'places the Fabric version json byte for byte' {
            $dest = Join-Path $F.Minecraft "versions\$script:FabricId\$script:FabricId.json"
            [IO.File]::ReadAllBytes($dest) | Should -Be ([IO.File]::ReadAllBytes($F.Fabric))
            $script:r.VersionChanged | Should -BeTrue
            $script:r.VersionId | Should -Be $script:FabricId
        }

        It 'downloads and verifies every client file, and skips server-only ones' {
            foreach ($file in $F.ModA, $F.ModB, $F.Res) {
                $p = Join-Path $F.Game $file.path.Replace('/', '\')
                [IO.File]::Exists($p) | Should -BeTrue
                Get-FileSha $p | Should -Be $file.hashes.sha512
            }
            [IO.File]::Exists((Join-Path $F.Game 'mods\server-only.jar')) | Should -BeFalse
            $F.Fetched[$F.ServerOnly.downloads[0]] | Should -BeNullOrEmpty
            $script:r.Downloaded | Should -Be 3
            $script:r.Total | Should -Be 3
            Get-PartFile $F.Game | Should -BeNullOrEmpty
        }

        It 'copies the overrides' {
            Read-Text (Join-Path $F.Game 'config\alpha.toml') | Should -Be "speed = 1`n"
            Read-Text (Join-Path $F.Game 'options.txt') | Should -Be "renderDistance:8`n"
            Read-Text (Join-Path $F.Game 'shaderpacks\Shader.zip.txt') | Should -Be "preset=high`n"
            $script:r.OverridesCopied | Should -Be 3
        }

        It 'records the installed files in the state file' {
            $s = Read-Text (Join-Path $F.Game '.realms-client-state.json') | ConvertFrom-Json
            @($s.files) | Should -Be @('mods/alpha-1.0.jar', 'mods/beta [fabric]-2.0.jar', 'resourcepacks/Fancy Pack [1.0].zip')
            $s.version | Should -Be '1.0.0'
        }

        It 'adds Monkey SMP profile' {
            $p = (Get-Profiles $F.Profiles).'the-realms'
            $p.name | Should -Be 'Monkey SMP 1.0.0'
            $p.type | Should -Be 'custom'
            $p.lastVersionId | Should -Be $script:FabricId
            $p.gameDir | Should -Be $F.Game
            $p.javaArgs | Should -BeLike '-Xmx4G -Xms4G -XX:+UseG1GC *-XX:G1ReservePercent=20'
            $p.icon | Should -Be 'Grass'
            $p.created | Should -Match '^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$'
            $p.lastUsed | Should -Be $p.created
            $script:r.ProfileChanged | Should -BeTrue
        }

        It 'keeps every other setting and profile exactly' {
            $after = Get-OtherJson $F.Profiles
            @($after.Keys) | Should -Be @($script:otherBefore.Keys)
            foreach ($k in $script:otherBefore.Keys) { $after[$k] | Should -BeExactly $script:otherBefore[$k] -Because $k }
            # The launcher's own formatting survives too: only our profile was appended.
            $text = Read-Text $F.Profiles
            $text.StartsWith((Get-LauncherProfilesText).Split('}')[0]) | Should -BeTrue
            $text | Should -BeLike ('*"name":"Caf' + [char]0xE9 + ' world"*')
            $text | Should -BeLike '*"emptyThing":{},"emptyList":`[`],"oneItem":`[1.5`]}'
            [IO.File]::ReadAllBytes($F.Profiles)[0..2] | Should -Not -Be @(0xEF, 0xBB, 0xBF)
        }

        It 'backs up the original launcher_profiles.json' {
            [IO.File]::ReadAllBytes("$($F.Profiles).the-realms-backup") | Should -Be $script:original
        }
    }

    Context 'second run' {
        It 'changes nothing' {
            $bytes = [IO.File]::ReadAllBytes($F.Profiles)
            $stamp = (Get-Item -LiteralPath $F.Profiles).LastWriteTimeUtc
            $fetches = ($F.Fetched.Values | Measure-Object -Sum).Sum
            $again = Install-Client -Context (New-Context $F $script:pack) -MemoryGB 4
            $again.Downloaded | Should -Be 0
            $again.Removed | Should -Be 0
            $again.OverridesCopied | Should -Be 0
            $again.VersionChanged | Should -BeFalse
            $again.ProfileChanged | Should -BeFalse
            ($F.Fetched.Values | Measure-Object -Sum).Sum | Should -Be $fetches
            [IO.File]::ReadAllBytes($F.Profiles) | Should -Be $bytes
            (Get-Item -LiteralPath $F.Profiles).LastWriteTimeUtc | Should -Be $stamp
        }

        It 'repairs a damaged file' {
            $p = Join-Path $F.Game 'mods\alpha-1.0.jar'
            [IO.File]::WriteAllText($p, 'tampered')
            (Install-Client -Context (New-Context $F $script:pack) -MemoryGB 4).Downloaded | Should -Be 1
            Get-FileSha $p | Should -Be $F.ModA.hashes.sha512
        }

        It 'updates only the memory when it changes' {
            $script:created = (Get-Profiles $F.Profiles).'the-realms'.created
            (Install-Client -Context (New-Context $F $script:pack) -MemoryGB 6).ProfileChanged | Should -BeTrue
            $p = (Get-Profiles $F.Profiles).'the-realms'
            $p.javaArgs | Should -BeLike '-Xmx6G -Xms6G *'
            $p.created | Should -Be $script:created
        }
    }

    Context 'update to a new pack' {
        BeforeEach {
            # The player's own files and changed settings.
            Write-Text (Join-Path $F.Game 'mods\my-own-mod.jar') 'mine'
            Write-Text (Join-Path $F.Game 'screenshots\a.png') 'png'
            Write-Text (Join-Path $F.Game 'config\alpha.toml') "speed = 9`n"
            $script:created = (Get-Profiles $F.Profiles).'the-realms'.created
            # alpha 1.0 -> 1.1 (renamed), beta dropped, a new config.
            $modA2 = New-PackFile $F 'mods/alpha-1.1.jar' 'alpha one point one'
            $overrides = @{
                'overrides/config/alpha.toml' = "speed = 2`n"
                'overrides/options.txt'       = "renderDistance:12`n"
                'overrides/config/new.toml'   = "fresh = true`n"
            }
            $pack2 = New-Pack $F @($modA2, $F.Res) $overrides '1.1.0'
            $script:r2 = Install-Client -Context (New-Context $F $pack2) -MemoryGB 4
        }

        It 'removes the old and renamed mods and installs the new one' {
            [IO.File]::Exists((Join-Path $F.Game 'mods\alpha-1.0.jar')) | Should -BeFalse
            [IO.File]::Exists((Join-Path $F.Game 'mods\beta [fabric]-2.0.jar')) | Should -BeFalse
            Get-FileSha (Join-Path $F.Game 'mods\alpha-1.1.jar') | Should -Be $modA2.hashes.sha512
            $script:r2.Removed | Should -Be 2
            $script:r2.Downloaded | Should -Be 1
            @((Read-Text (Join-Path $F.Game '.realms-client-state.json') | ConvertFrom-Json).files) |
                Should -Be @('mods/alpha-1.1.jar', 'resourcepacks/Fancy Pack [1.0].zip')
        }

        It "keeps the player's own files and settings" {
            Read-Text (Join-Path $F.Game 'mods\my-own-mod.jar') | Should -Be 'mine'
            Read-Text (Join-Path $F.Game 'screenshots\a.png') | Should -Be 'png'
            Read-Text (Join-Path $F.Game 'config\alpha.toml') | Should -Be "speed = 9`n"
            Read-Text (Join-Path $F.Game 'options.txt') | Should -Be "renderDistance:8`n"
            Read-Text (Join-Path $F.Game 'config\new.toml') | Should -Be "fresh = true`n"
            $script:r2.OverridesCopied | Should -Be 1
        }

        It 'renames the profile and keeps its created time and the first backup' {
            $p = (Get-Profiles $F.Profiles).'the-realms'
            $p.name | Should -Be 'Monkey SMP 1.1.0'
            $p.created | Should -Be $script:created
            [IO.File]::ReadAllBytes("$($F.Profiles).the-realms-backup") | Should -Be $script:original
            @((Get-Profiles $F.Profiles).PSObject.Properties).Count | Should -Be 4
        }
    }
}

Describe 'Downloads' {
    BeforeEach {
        $F = New-Fixture
        $script:bytesBefore = [IO.File]::ReadAllBytes($F.Profiles)
    }

    It 'rejects a file whose hash does not match and leaves nothing behind' {
        $good = New-PackFile $F 'mods/good.jar' 'good'
        $bad = New-PackFile $F 'mods/bad.jar' 'expected'
        Write-Text $F.Map[$bad.downloads[0]] 'evil!!!!'   # same length, different bytes
        $pack = New-Pack $F @($good, $bad)
        { Install-Client -Context (New-Context $F $pack) -MemoryGB 3 } | Should -Throw '*mods/bad.jar*hash mismatch*'
        [IO.File]::Exists((Join-Path $F.Game 'mods\bad.jar')) | Should -BeFalse
        Get-PartFile $F.Game | Should -BeNullOrEmpty
        $F.Fetched[$bad.downloads[0]] | Should -Be 3
        [IO.File]::ReadAllBytes($F.Profiles) | Should -Be $script:bytesBefore
    }

    It 'rejects a file of the wrong size' {
        $bad = New-PackFile $F 'mods/bad.jar' 'expected'
        Write-Text $F.Map[$bad.downloads[0]] 'longer than expected'
        $pack = New-Pack $F @($bad)
        { Install-Client -Context (New-Context $F $pack) -MemoryGB 3 } | Should -Throw '*wrong size*'
        [IO.File]::Exists((Join-Path $F.Game 'mods\bad.jar')) | Should -BeFalse
    }

    It 'retries a failed download, then tries the next mirror' {
        $file = New-PackFile $F 'mods/flaky.jar' 'flaky'
        $file.downloads = @('https://fixture.invalid/missing/flaky.jar') + @($file.downloads)
        $pack = New-Pack $F @($file)
        (Install-Client -Context (New-Context $F $pack) -MemoryGB 3).Downloaded | Should -Be 1
        $F.Fetched['https://fixture.invalid/missing/flaky.jar'] | Should -Be 1
    }

    It 'checks sha1 when the pack has no sha512' {
        $file = New-PackFile $F 'mods/old.jar' 'old style' -NoSha512
        $pack = New-Pack $F @($file)
        (Install-Client -Context (New-Context $F $pack) -MemoryGB 3).Downloaded | Should -Be 1
        Write-Text $F.Map[$file.downloads[0]] 'old stylx'
        [IO.File]::Delete((Join-Path $F.Game 'mods\old.jar'))
        { Install-Client -Context (New-Context $F $pack) -MemoryGB 3 } | Should -Throw '*hash mismatch*'
    }
}

Describe 'Unsafe packs' {
    BeforeEach {
        $F = New-Fixture
        $script:bytesBefore = [IO.File]::ReadAllBytes($F.Profiles)
    }

    It 'rejects <Path> in the file list' -TestCases @(
        @{ Path = '../evil.jar' }
        @{ Path = 'mods/../../evil.jar' }
        @{ Path = 'C:/Windows/evil.jar' }
        @{ Path = '/evil.jar' }
        @{ Path = '\\server\share\evil.jar' }
        @{ Path = 'mods/evil.jar:stream' }
        @{ Path = 'mods/./evil.jar' }
        @{ Path = 'mods/evil.' }
    ) {
        $file = New-PackFile $F $Path 'evil'
        $pack = New-Pack $F @($file)
        { Install-Client -Context (New-Context $F $pack) -MemoryGB 3 } | Should -Throw '*Unsafe path*'
        Test-Path -LiteralPath $F.Game | Should -BeFalse
        Test-Path -LiteralPath (Join-Path $F.Dir 'evil.jar') | Should -BeFalse
        [IO.File]::ReadAllBytes($F.Profiles) | Should -Be $script:bytesBefore
    }

    It 'rejects <Entry> in the overrides' -TestCases @(
        @{ Entry = 'overrides/../evil.txt' }
        @{ Entry = 'overrides/config/../../evil.txt' }
        @{ Entry = 'client-overrides/C:/evil.txt' }
    ) {
        $ok = New-PackFile $F 'mods/ok.jar' 'ok'
        $pack = New-Pack $F @($ok) @{ $Entry = 'evil' }
        { Install-Client -Context (New-Context $F $pack) -MemoryGB 3 } | Should -Throw '*Unsafe path*'
        Test-Path -LiteralPath $F.Game | Should -BeFalse
        Test-Path -LiteralPath (Join-Path $F.Dir 'evil.txt') | Should -BeFalse
    }

    It 'resolves normal paths inside the game folder' {
        Resolve-GamePath -Root 'C:\g [1]' -RelativePath 'resourcepacks/A [b] c.zip' | Should -Be 'C:\g [1]\resourcepacks\A [b] c.zip'
        Resolve-GamePath -Root 'C:\g\' -RelativePath 'config/x/y.json5' | Should -Be 'C:\g\config\x\y.json5'
    }

    It 'rejects a pack for another Minecraft or loader than the Fabric profile' {
        $pack = New-Pack $F @() -Loader '0.2.0'
        { Install-Client -Context (New-Context $F $pack) -MemoryGB 3 } | Should -Throw "*Fabric profile is for 'fabric-loader-0.1.0-1.0'*needs 'fabric-loader-0.2.0-1.0'*"
        Test-Path -LiteralPath (Join-Path $F.Minecraft 'versions') | Should -BeFalse
    }

    It 'rejects a Fabric profile that inherits from another Minecraft' {
        Write-Text $F.Fabric (New-FabricProfileText $script:FabricId '1.1')
        $pack = New-Pack $F @()
        { Install-Client -Context (New-Context $F $pack) -MemoryGB 3 } | Should -Throw '*Fabric profile*'
    }

    It 'rejects a missing Fabric profile' {
        [IO.File]::Delete($F.Fabric)
        $pack = New-Pack $F @()
        { Install-Client -Context (New-Context $F $pack) -MemoryGB 3 } | Should -Throw '*fabric-profile.json) is missing*'
    }

    It 'rejects a pack that is not a Fabric pack' {
        $path = Join-Path $F.Dir 'TheRealms-Client-9.mrpack'
        New-Zip $path @{ 'modrinth.index.json' = '{"formatVersion":1,"game":"minecraft","versionId":"9","files":[],"dependencies":{"minecraft":"1.0","forge":"1"}}' }
        { Read-ClientPack -Path $path } | Should -Throw '*not a Fabric modpack*'
        New-Zip $path @{ 'readme.txt' = 'hi' }
        { Read-ClientPack -Path $path } | Should -Throw '*no modrinth.index.json*'
    }
}

Describe 'Minecraft Launcher checks' {
    BeforeEach {
        $F = New-Fixture
        $script:pack = New-StandardPack $F
    }

    It 'explains how to get the launcher when its folder is missing' {
        Remove-Item -LiteralPath $F.Minecraft -Recurse -Force
        { Install-Client -Context (New-Context $F $script:pack) -MemoryGB 3 } | Should -Throw '*Install the Minecraft Launcher from minecraft.net, start it once, sign in, close it*'
        Test-Path -LiteralPath $F.Game | Should -BeFalse
    }

    It 'explains how to get the launcher when launcher_profiles.json is missing' {
        [IO.File]::Delete($F.Profiles)
        { Install-Client -Context (New-Context $F $script:pack) -MemoryGB 3 } | Should -Throw '*Install the Minecraft Launcher*'
    }

    It 'stops on a damaged launcher_profiles.json without changing it' {
        Write-Text $F.Profiles '{"profiles":{'
        { Install-Client -Context (New-Context $F $script:pack) -MemoryGB 3 } | Should -Throw '*damaged*'
        Read-Text $F.Profiles | Should -Be '{"profiles":{'
    }

    It 'creates the profiles object when the file has none' {
        Write-Text $F.Profiles '{"settings":{},"version":3}'
        [void](Install-Client -Context (New-Context $F $script:pack) -MemoryGB 3)
        $o = Read-Text $F.Profiles | ConvertFrom-Json
        $o.'profiles'.'the-realms'.lastVersionId | Should -Be $script:FabricId
        $o.version | Should -Be 3
    }

    It 'also updates the Microsoft Store launcher profiles' {
        $store = Join-Path $F.Minecraft 'launcher_profiles_microsoft_store.json'
        Write-Text $store '{"profiles":{"x":{"name":"x","type":"custom","lastVersionId":"1.0"}}}'
        [void](Install-Client -Context (New-Context $F $script:pack) -MemoryGB 3)
        (Get-Profiles $store).'the-realms'.name | Should -Be 'Monkey SMP 1.0.0'
        (Get-Profiles $store).x.name | Should -Be 'x'
        (Get-Profiles $F.Profiles).'the-realms'.name | Should -Be 'Monkey SMP 1.0.0'
    }

    It 'only warns about a running launcher with -NonInteractive' {
        [void]$F.Running.Add('MinecraftLauncher')
        [void](Install-Client -Context (New-Context $F $script:pack) -MemoryGB 3)
        $F.Asked.Count | Should -Be 0
        (Get-Profiles $F.Profiles).'the-realms' | Should -Not -BeNullOrEmpty
    }

    It 'asks the player to close the launcher and checks again' {
        [void]$F.Running.Add('Minecraft')
        $running = $F.Running
        # The player closes the launcher, then presses Enter.
        $ctx = New-Context $F $script:pack -Interactive
        $ctx.Ask = { param([string]$Question) [void]$F.Asked.Add($Question); $running.Clear(); '' }.GetNewClosure()
        [void](Install-Client -Context $ctx -MemoryGB 3)
        $F.Asked.Count | Should -Be 1
        $F.Asked[0] | Should -BeLike '*Close the Minecraft Launcher*'
    }

    It 'never lets the game folder be the launcher folder' {
        { New-PlayerContext -MinecraftDir $F.Minecraft -GameDir "$($F.Minecraft)\" } | Should -Throw "*can't be the Minecraft Launcher's own folder*"
    }
}

Describe 'Uninstall-Client' {
    BeforeEach {
        $F = New-Fixture
        $script:pack = New-StandardPack $F
        $script:original = [IO.File]::ReadAllBytes($F.Profiles)
        [void](Install-Client -Context (New-Context $F $script:pack) -MemoryGB 4)
    }

    It 'removes the profile and the game folder and keeps everything else' {
        $r = Uninstall-Client -Context (New-Context $F $null)
        $r.ProfileRemoved | Should -BeTrue
        $r.GameDirRemoved | Should -BeTrue
        Test-Path -LiteralPath $F.Game | Should -BeFalse
        # Install + uninstall gives back the launcher's file byte for byte.
        [IO.File]::ReadAllBytes($F.Profiles) | Should -Be $script:original
        [IO.File]::ReadAllBytes("$($F.Profiles).the-realms-backup") | Should -Be $script:original
        Test-Path -LiteralPath (Join-Path $F.Minecraft "versions\$script:FabricId\$script:FabricId.json") | Should -BeTrue
    }

    It 'keeps the game folder unless the player types DELETE' {
        $F.Answers.Enqueue('delete it')
        $r = Uninstall-Client -Context (New-Context $F $null -Interactive)
        $r.ProfileRemoved | Should -BeTrue
        $r.GameDirRemoved | Should -BeFalse
        Test-Path -LiteralPath (Join-Path $F.Game 'options.txt') | Should -BeTrue
        $F.Asked[0] | Should -BeLike '*Type DELETE*'
    }

    It 'deletes the game folder when the player types DELETE' {
        $F.Answers.Enqueue('DELETE')
        (Uninstall-Client -Context (New-Context $F $null -Interactive)).GameDirRemoved | Should -BeTrue
        Test-Path -LiteralPath $F.Game | Should -BeFalse
    }

    It 'never deletes a folder this installer did not make' {
        $other = Join-Path $F.Dir 'someone-elses'
        Write-Text (Join-Path $other 'precious.txt') 'keep'
        $ctx = New-PlayerContext -MinecraftDir $F.Minecraft -GameDir $other -GetProcess $F.GetProcess -NonInteractive
        (Uninstall-Client -Context $ctx).GameDirRemoved | Should -BeFalse
        Read-Text (Join-Path $other 'precious.txt') | Should -Be 'keep'
    }

    It 'is safe to run twice' {
        [void](Uninstall-Client -Context (New-Context $F $null))
        $r = Uninstall-Client -Context (New-Context $F $null)
        $r.ProfileRemoved | Should -BeFalse
        [IO.File]::ReadAllBytes($F.Profiles) | Should -Be $script:original
    }
}

Describe 'Get-ClientMemoryGB' {
    It '<Ram> GB of RAM gives <Want> GB' -TestCases @(
        @{ Ram = 4; Want = 3 }
        @{ Ram = 7.8; Want = 3 }
        @{ Ram = 8; Want = 3 }
        @{ Ram = 12; Want = 4 }
        @{ Ram = 15.9; Want = 6 }
        @{ Ram = 16; Want = 6 }
        @{ Ram = 32; Want = 8 }
    ) {
        Get-ClientMemoryGB -TotalBytes ($Ram * 1GB) | Should -Be $Want
    }

    It 'uses the requested amount' {
        Get-ClientMemoryGB -TotalBytes (32 * 1GB) -Requested 5 | Should -Be 5
    }
}

Describe 'Find-ClientPack' {
    BeforeEach { $dir = Join-Path $TestDrive ([guid]::NewGuid().ToString('N')); New-Item -ItemType Directory -Path $dir | Out-Null }

    It 'finds the one pack' {
        Write-Text (Join-Path $dir 'TheRealms-Client-2.0.0.mrpack') 'x'
        Find-ClientPack -Folder $dir | Should -Be (Join-Path $dir 'TheRealms-Client-2.0.0.mrpack')
    }

    It 'explains a missing pack' {
        { Find-ClientPack -Folder $dir } | Should -Throw '*Unzip the whole*'
    }

    It 'refuses to guess between two packs' {
        Write-Text (Join-Path $dir 'TheRealms-Client-2.0.0.mrpack') 'x'
        Write-Text (Join-Path $dir 'TheRealms-Client-2.1.0.mrpack') 'x'
        { Find-ClientPack -Folder $dir } | Should -Throw '*more than one*'
    }
}

Describe 'Player package files' {
    It '<Name> is plain ASCII' -TestCases @(
        Get-ChildItem -LiteralPath (Join-Path (Split-Path $PSScriptRoot -Parent) 'player') -Recurse -File |
            Where-Object { $_.Extension -in '.ps1', '.psm1', '.bat' } | ForEach-Object { @{ Name = $_.Name; Path = $_.FullName } }
    ) {
        @([IO.File]::ReadAllBytes($Path) | Where-Object { $_ -gt 127 }).Count | Should -Be 0
    }

    It 'the .bat runs the installer script next to it' {
        $bat = Read-Text (Join-Path $script:RepoRoot 'player\Install for Minecraft Launcher.bat')
        $bat | Should -BeLike '*powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\install-client.ps1"*'
        Test-Path -LiteralPath (Join-Path $script:RepoRoot 'player\installer\install-client.ps1') | Should -BeTrue
    }
}
