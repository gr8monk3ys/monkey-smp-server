#Requires -Version 5.1
<#
.SYNOPSIS
    Unit tests for package/realms/Realms.psm1 (Pester 5). No network, no Java, a few seconds.

.DESCRIPTION
    Every test builds a throwaway server package in TestDrive: tiny fixture jars and zips, a
    manifest (current schema) that pins their real hashes, and Defaults. Downloads go through a
    Fetch adapter that copies from a url -> file map, and player lookups through a fake profile
    adapter, so the module is exercised through its public interface only.

.EXAMPLE
    Invoke-Pester -Path tests/Realms.Tests.ps1 -Output Detailed
#>

BeforeDiscovery {
    $script:realManifestPath = Join-Path $PSScriptRoot '..\package\realms\manifest.json'
    $real = Get-Content -LiteralPath $script:realManifestPath -Raw | ConvertFrom-Json
    $script:realArtifacts = @(
        @{ Kind = 'java'; Entry = $real.java }
        @{ Kind = 'server'; Entry = $real.server }
    ) + @($real.plugins | Where-Object { $_ } | ForEach-Object { @{ Kind = 'plugin'; Entry = $_ } }) +
        @($real.mods | Where-Object { $_ } | ForEach-Object { @{ Kind = 'mod'; Entry = $_ } }) +
        @($real.datapacks | Where-Object { $_ } | ForEach-Object { @{ Kind = 'datapack'; Entry = $_ } })
    $script:realPatched = @(@($real.mods) + @($real.datapacks) | Where-Object { $_ -and $_.patch } | ForEach-Object { @{ Entry = $_ } })
}

BeforeAll {
    $script:RepoRoot = Split-Path $PSScriptRoot -Parent
    Import-Module (Join-Path $script:RepoRoot 'package\realms\Realms.psm1') -Force
    Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
    $script:Utf8 = New-Object System.Text.UTF8Encoding $false

    function Get-Sha512([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA512).Hash.ToLower() }

    function Get-FreePort {
        $l = New-Object Net.Sockets.TcpListener ([Net.IPAddress]::Loopback, 0)
        $l.Start()
        try { return $l.LocalEndpoint.Port } finally { $l.Stop() }
    }

    function New-Zip([string]$Path, [hashtable]$Files) {
        New-Item -ItemType Directory -Force -Path (Split-Path $Path -Parent) | Out-Null
        if (Test-Path -LiteralPath $Path) { Remove-Item -LiteralPath $Path -Force }
        $zip = [IO.Compression.ZipFile]::Open($Path, [IO.Compression.ZipArchiveMode]::Create)
        try {
            foreach ($name in $Files.Keys) {
                $s = $zip.CreateEntry($name).Open()
                try { $b = $script:Utf8.GetBytes([string]$Files[$name]); $s.Write($b, 0, $b.Length) } finally { $s.Dispose() }
            }
        } finally { $zip.Dispose() }
    }

    function Read-ZipEntry([string]$Path, [string]$Name) {
        $zip = [IO.Compression.ZipFile]::OpenRead($Path)
        try {
            $e = $zip.GetEntry($Name)
            if (-not $e) { return $null }
            $r = New-Object IO.StreamReader ($e.Open())
            try { return $r.ReadToEnd() } finally { $r.Dispose() }
        } finally { $zip.Dispose() }
    }

    function Write-Text([string]$Path, [string]$Text) {
        New-Item -ItemType Directory -Force -Path (Split-Path $Path -Parent) | Out-Null
        [IO.File]::WriteAllText($Path, $Text, $script:Utf8)
    }

    # A fixture world: upstream files, a server package (realms\ with defaults\ and patches\), and
    # adapters. $F.Fetched counts downloads per url; $F.Map can be edited to serve different bytes.
    function New-Fixture {
        $dir = Join-Path $TestDrive ([guid]::NewGuid().ToString('N').Substring(0, 8))
        $F = @{
            Dir      = $dir
            Upstream = Join-Path $dir 'upstream'
            Root     = Join-Path $dir 'pkg'
            Realms   = Join-Path $dir 'pkg\realms'
            Map      = @{}
            Fetched  = @{}
            Port     = Get-FreePort
        }
        $F.Server = Join-Path $F.Root 'server'
        $F.Packs = Join-Path $F.Server 'world\datapacks'
        $F.Plugins = Join-Path $F.Server 'plugins'
        $F.Mods = Join-Path $F.Server 'mods'
        New-Item -ItemType Directory -Force -Path $F.Upstream, $F.Realms | Out-Null
        Write-Text (Join-Path $F.Realms 'defaults\server.properties') (
            "#fixture`nlevel-name={{LEVEL_NAME}}`nlevel-seed={{SEED}}`nserver-port=$($F.Port)`n" +
            "enable-rcon=true`nrcon.port=$(Get-FreePort)`nrcon.password={{RCON_PASSWORD}}`n")
        Write-Text (Join-Path $F.Realms 'defaults\plugins\LuckPerms\config.yml') "storage-method: yaml`n"
        $map = $F.Map
        $fetched = $F.Fetched
        $F.Fetch = {
            param([string]$Url, [string]$OutFile)
            $fetched[$Url] = 1 + [int]$fetched[$Url]
            if (-not $map.ContainsKey($Url)) { throw "404 Not Found: $Url" }
            Copy-Item -LiteralPath $map[$Url] -Destination $OutFile -Force
        }.GetNewClosure()
        $F.Profile = {
            param([string]$Name)
            if ($Name -eq 'Nobody') { throw "no such player $Name" }
            @{ Name = 'Notch'; Uuid = '069a79f4-44e9-4726-a5be-fca90e38aaf5' }
        }
        $F.Java = New-Entry $F 'java.zip' @{ 'jdk-fixture/bin/java.exe' = 'not really java'; 'jdk-fixture/release' = 'x' }
        $F.Java.version = 'jdk-fixture'
        $F.Java | Add-Member -NotePropertyName vendor -NotePropertyValue 'Fixture JRE'
        $F.Paper = New-Entry $F 'paper-1.jar' @{ 'paper.txt' = 'paper build 1' }
        $F.Paper | Add-Member -NotePropertyName type -NotePropertyValue 'paper'
        $F.Paper | Add-Member -NotePropertyName build -NotePropertyValue 1
        $F.Fabric = New-Entry $F 'fabric-server-mc.1.0-loader.0.1.0-launcher.1.0.0.jar' @{ 'fabric.txt' = 'fabric launcher' }
        $F.Fabric | Add-Member -NotePropertyName type -NotePropertyValue 'fabric'
        $F.Fabric | Add-Member -NotePropertyName loader -NotePropertyValue '0.1.0'
        $F.Fabric | Add-Member -NotePropertyName installer -NotePropertyValue '1.0.0'
        return $F
    }

    # Writes an upstream zip/jar, serves it at a url and returns its manifest entry.
    function New-Entry($F, [string]$File, [hashtable]$Files, [string]$Slug) {
        if (-not $Slug) { $Slug = [IO.Path]::GetFileNameWithoutExtension($File) }
        $path = Join-Path $F.Upstream ([guid]::NewGuid().ToString('N') + '-' + $File)
        New-Zip $path $Files
        $url = "https://fixture.invalid/$([guid]::NewGuid().ToString('N'))/$File"
        $F.Map[$url] = $path
        return [pscustomobject]@{
            slug    = $Slug
            version = '1.0'
            file    = $File
            url     = $url
            size    = (Get-Item -LiteralPath $path).Length
            hashes  = [pscustomobject]@{ sha512 = Get-Sha512 $path }
        }
    }

    function New-Patch($F, [string]$Slug, [hashtable]$Files) {
        foreach ($k in $Files.Keys) { Write-Text (Join-Path $F.Realms "patches\$Slug\$k") $Files[$k] }
        return "patches/$Slug"
    }

    function Add-PatchTo($Entry, [string]$Path, [string]$Base) {
        if (-not $Base) { $Base = $Entry.hashes.sha512 }
        $Entry | Add-Member -NotePropertyName patch -NotePropertyValue ([pscustomobject]@{ path = $Path; base_sha512 = $Base }) -Force
        return $Entry
    }

    # A Paper manifest unless -Server is given (e.g. $F.Fabric).
    function New-Manifest($F, [object[]]$Plugins = @(), [object[]]$Datapacks = @(), [object[]]$Mods = @(), $Server, [string]$Version = '1.0.0') {
        if (-not $Server) { $Server = $F.Paper }
        $m = [pscustomobject]@{
            name      = 'Fixture Realms'
            version   = $Version
            minecraft = '1.0'
            java      = $F.Java
            server    = $Server
            world     = [pscustomobject]@{ level_name = 'world'; seed = '-12345' }
            plugins   = @($Plugins)
            mods      = @($Mods)
            datapacks = @($Datapacks)
        }
        # Round-trip through JSON so the types match a manifest read from disk.
        return ConvertTo-Json -InputObject $m -Depth 10 | ConvertFrom-Json
    }

    function New-Ctx($F, $Manifest) {
        New-RealmsContext -Root $F.Root -Manifest $Manifest -Fetch $F.Fetch -ProfileLookup $F.Profile -NonInteractive
    }

    function Install-Fixture($F, $Manifest, [hashtable]$Options = @{ NoOwner = $true }) {
        $ctx = New-Ctx $F $Manifest
        Install-Server -Context $ctx -AcceptEula @Options 6>$null
    }

    # Fabric Defaults in place of the Paper ones New-Fixture writes (LuckPerms config moves to config\).
    function Use-FabricDefaults($F) {
        Remove-Item -LiteralPath (Join-Path $F.Realms 'defaults\plugins') -Recurse -Force
        Write-Text (Join-Path $F.Realms 'defaults\config\luckperms\luckperms.conf') "storage-method = `"yaml`"`n"
    }

    function Get-State($F) { Get-Content -LiteralPath (Join-Path $F.Server '.realms-state.json') -Raw | ConvertFrom-Json }
}

Describe 'Install-Server' {
    BeforeEach {
        # Retries wait 5 and 10 seconds in production; not here.
        Mock Start-Sleep -ModuleName Realms {}
    }

    It 'downloads and verifies everything on a fresh install, then is a no-op' {
        $F = New-Fixture
        $plugin = New-Entry $F 'Foo-1.0.jar' @{ 'plugin.yml' = 'name: Foo' }
        $pack = New-Entry $F 'Pack.zip' @{ 'pack.mcmeta' = '{}' }
        $m = New-Manifest $F @($plugin) @($pack)

        $java = Install-Fixture $F $m
        $java | Should -Be (Join-Path $F.Root 'java\jdk-fixture\bin\java.exe')
        $java | Should -Exist
        Join-Path $F.Server 'paper.jar' | Should -Exist
        Join-Path $F.Plugins 'Foo-1.0.jar' | Should -Exist
        Join-Path $F.Packs 'Pack.zip' | Should -Exist
        Get-Sha512 (Join-Path $F.Plugins 'Foo-1.0.jar') | Should -Be $plugin.hashes.sha512
        Join-Path $F.Root 'downloads' | Should -Not -Exist
        Join-Path $F.Server 'eula.txt' | Should -FileContentMatch 'eula=true'
        $state = Get-State $F
        $state.version | Should -Be '1.0.0'
        ($state.plugins -join ',') | Should -Be 'Foo-1.0.jar'
        ($state.datapacks -join ',') | Should -Be 'Pack.zip'
        # One-element lists must stay JSON arrays on Windows PowerShell 5.1.
        Get-Content -LiteralPath (Join-Path $F.Server '.realms-state.json') -Raw | Should -Match '"plugins":\s*\['

        $F.Fetched.Clear()
        $stamp = (Get-Item (Join-Path $F.Plugins 'Foo-1.0.jar')).LastWriteTimeUtc
        $out = Install-Server -Context (New-Ctx $F $m) -NoOwner 6>&1 | Out-String
        $out | Should -Match 'Everything is up to date'
        $F.Fetched.Count | Should -Be 0
        (Get-Item (Join-Path $F.Plugins 'Foo-1.0.jar')).LastWriteTimeUtc | Should -Be $stamp
    }

    It 'installs upstream file names containing [ ] and is then a no-op' {
        $F = New-Fixture
        # Invoke-WebRequest -OutFile on 5.1 treats [ ] as wildcards; make the fake adapter just as strict.
        $inner = $F.Fetch
        $F.Fetch = {
            param([string]$Url, [string]$OutFile)
            if ($OutFile -match '[\[\]]') { throw "wildcard path $OutFile did not resolve to a file" }
            & $inner $Url $OutFile
        }.GetNewClosure()
        $plugin = New-Entry $F 'Foo [1.0].jar' @{ 'plugin.yml' = 'name: Foo' }
        $pack = New-Entry $F 'Player Corpses 3.7 [1.21.9+].zip' @{ 'pack.mcmeta' = '{}' }
        $patched = Add-PatchTo (New-Entry $F 'Lib [v2].zip' @{ 'pack.mcmeta' = 'old' }) (New-Patch $F 'lib' @{ 'pack.mcmeta' = 'new' })
        $m = New-Manifest $F @($plugin) @($pack, $patched)

        Install-Fixture $F $m | Out-Null
        Get-Sha512 (Join-Path $F.Plugins 'Foo [1.0].jar') | Should -Be $plugin.hashes.sha512
        Get-Sha512 (Join-Path $F.Packs 'Player Corpses 3.7 [1.21.9+].zip') | Should -Be $pack.hashes.sha512
        Read-ZipEntry (Join-Path $F.Packs 'Lib [v2].zip') 'pack.mcmeta' | Should -Be 'new'
        @(Get-ChildItem -LiteralPath $F.Packs -Filter '*.part').Count | Should -Be 0

        $F.Fetched.Clear()
        $out = Install-Server -Context (New-Ctx $F $m) -NoOwner 6>&1 | Out-String
        $out | Should -Match 'Everything is up to date'
        $F.Fetched.Count | Should -Be 0
    }

    It 'throws a hash error on a mismatched download and leaves no file behind' {
        $F = New-Fixture
        $plugin = New-Entry $F 'Bad.jar' @{ 'plugin.yml' = 'name: Bad' }
        $plugin.hashes.sha512 = 'ab' * 64
        $m = New-Manifest $F @($plugin)

        { Install-Fixture $F $m } | Should -Throw '*hash mismatch for Bad.jar*'
        $F.Fetched[$plugin.url] | Should -Be 3
        Join-Path $F.Plugins 'Bad.jar' | Should -Not -Exist
        Join-Path $F.Plugins 'Bad.jar.part' | Should -Not -Exist
    }

    It 'replaces a plugin whose file name changed on upgrade' {
        $F = New-Fixture
        $v1 = New-Entry $F 'Foo-1.0.jar' @{ 'plugin.yml' = 'version: 1' } 'foo'
        Install-Fixture $F (New-Manifest $F @($v1))
        $v2 = New-Entry $F 'Foo-2.0.jar' @{ 'plugin.yml' = 'version: 2' } 'foo'
        Install-Fixture $F (New-Manifest $F @($v2))

        Join-Path $F.Plugins 'Foo-1.0.jar' | Should -Not -Exist
        Join-Path $F.Plugins 'Foo-2.0.jar' | Should -Exist
        ((Get-State $F).plugins -join ',') | Should -Be 'Foo-2.0.jar'
    }

    It 'deletes a datapack dropped from the manifest but leaves files the host added' {
        $F = New-Fixture
        $a = New-Entry $F 'A.zip' @{ 'pack.mcmeta' = 'a' }
        $b = New-Entry $F 'B.zip' @{ 'pack.mcmeta' = 'b' }
        Install-Fixture $F (New-Manifest $F @() @($a, $b))
        Write-Text (Join-Path $F.Packs 'HostPack.zip') 'host'
        Write-Text (Join-Path $F.Plugins 'HostPlugin.jar') 'host'

        Install-Fixture $F (New-Manifest $F @() @($a))
        Join-Path $F.Packs 'A.zip' | Should -Exist
        Join-Path $F.Packs 'B.zip' | Should -Not -Exist
        Join-Path $F.Packs 'HostPack.zip' | Should -Exist
        Join-Path $F.Plugins 'HostPlugin.jar' | Should -Exist
        ((Get-State $F).datapacks -join ',') | Should -Be 'A.zip'
    }

    Context 'patched datapacks' {
        BeforeEach {
            $F = New-Fixture
            $F.Pack = New-Entry $F 'Effects.zip' @{ 'pack.mcmeta' = 'original'; 'data/x/fn.mcfunction' = 'say hi' }
            $F.Patch = New-Patch $F 'effects' @{ 'pack.mcmeta' = 'patched' }
            $F.Dest = Join-Path $F.Packs 'Effects.zip'
        }

        It 'replaces the patched files and keeps the rest' {
            Install-Fixture $F (New-Manifest $F @() @(Add-PatchTo $F.Pack $F.Patch))
            Read-ZipEntry $F.Dest 'pack.mcmeta' | Should -Be 'patched'
            Read-ZipEntry $F.Dest 'data/x/fn.mcfunction' | Should -Be 'say hi'
            (Get-State $F).patched.'Effects.zip'.sha256 | Should -Not -BeNullOrEmpty
            Join-Path $F.Root 'downloads' | Should -Not -Exist
        }

        It 'reuses the patched file while neither the upstream file nor the patch changed' {
            $m = New-Manifest $F @() @(Add-PatchTo $F.Pack $F.Patch)
            Install-Fixture $F $m
            $F.Fetched.Clear()
            $stamp = (Get-Item $F.Dest).LastWriteTimeUtc
            Install-Fixture $F $m
            $F.Fetched.Count | Should -Be 0
            (Get-Item $F.Dest).LastWriteTimeUtc | Should -Be $stamp
        }

        It 're-applies when the patch changes' {
            $m = New-Manifest $F @() @(Add-PatchTo $F.Pack $F.Patch)
            Install-Fixture $F $m
            $F.Fetched.Clear()
            Write-Text (Join-Path $F.Realms 'patches\effects\pack.mcmeta') 'patched again'
            Install-Fixture $F $m
            $F.Fetched[$F.Pack.url] | Should -Be 1
            Read-ZipEntry $F.Dest 'pack.mcmeta' | Should -Be 'patched again'
        }

        It 'throws when base_sha512 is not the upstream file the entry pins' {
            $m = New-Manifest $F @() @(Add-PatchTo $F.Pack $F.Patch ('cd' * 64))
            { Install-Fixture $F $m } | Should -Throw '*different upstream file*'
            $F.Dest | Should -Not -Exist
        }

        It 'throws when the downloaded file is not the patch base (sha256-only entry)' {
            $F.Pack.hashes = [pscustomobject]@{ sha256 = (Get-FileHash -LiteralPath $F.Map[$F.Pack.url] -Algorithm SHA256).Hash.ToLower() }
            $m = New-Manifest $F @() @(Add-PatchTo $F.Pack $F.Patch ('cd' * 64))
            { Install-Fixture $F $m } | Should -Throw '*base_sha512*'
            $F.Dest | Should -Not -Exist
            Join-Path $F.Root 'downloads\Effects.zip' | Should -Not -Exist
        }

        It 'throws when a patch adds a file the datapack does not have' {
            Write-Text (Join-Path $F.Realms 'patches\effects\data\x\new.json') '{}'
            { Install-Fixture $F (New-Manifest $F @() @(Add-PatchTo $F.Pack $F.Patch)) } |
                Should -Throw '*no matching file in Effects.zip: data/x/new.json*'
            $F.Dest | Should -Not -Exist
        }

        It 'rejects the old string patch shape with a clear message' {
            $F.Pack | Add-Member -NotePropertyName patch -NotePropertyValue $F.Patch -Force
            { Install-Fixture $F (New-Manifest $F @() @($F.Pack)) } | Should -Throw "*must be an object with 'path' and 'base_sha512'*"
        }
    }

    Context 'Defaults' {
        It 'copies only missing files and renders server.properties' {
            $F = New-Fixture
            Write-Text (Join-Path $F.Server 'plugins\LuckPerms\config.yml') 'host edit'
            Install-Fixture $F (New-Manifest $F)

            Join-Path $F.Server 'plugins\LuckPerms\config.yml' | Should -FileContentMatchExactly '^host edit$'
            $propsPath = Join-Path $F.Server 'server.properties'
            [IO.File]::ReadAllText($propsPath) | Should -Not -Match '\{\{'
            $props = Read-ServerProperties $propsPath
            $props['level-name'] | Should -Be 'world'
            $props['level-seed'] | Should -Be '-12345'
            $props['rcon.password'].Length | Should -Be 32
        }

        It 'never overwrites a server.properties the host already has' {
            $F = New-Fixture
            Write-Text (Join-Path $F.Server 'server.properties') "server-port=$($F.Port)`nmotd=mine`n"
            Install-Fixture $F (New-Manifest $F)
            (Read-ServerProperties (Join-Path $F.Server 'server.properties'))['motd'] | Should -Be 'mine'
        }

        It 'throws on a placeholder it cannot fill' {
            $F = New-Fixture
            Write-Text (Join-Path $F.Realms 'defaults\server.properties') "server-port=$($F.Port)`nmotd={{MOTD}}`n"
            { Install-Fixture $F (New-Manifest $F) } | Should -Throw '*{{MOTD}}*'
        }
    }

    Context 'Owner' {
        It 'whitelists and ops the owner and gives them the admin rank, once' {
            $F = New-Fixture
            Install-Fixture $F (New-Manifest $F) @{ Owner = 'notch' }
            $ctx = New-Ctx $F (New-Manifest $F)
            Add-Owner -Context $ctx -Name 'notch' 6>$null | Should -Be 'Notch'

            $white = @(Get-Content (Join-Path $F.Server 'whitelist.json') -Raw | ConvertFrom-Json)
            $white.Count | Should -Be 1
            $white[0].name | Should -Be 'Notch'
            $ops = @(Get-Content (Join-Path $F.Server 'ops.json') -Raw | ConvertFrom-Json)
            $ops.Count | Should -Be 1
            $ops[0].level | Should -Be 4
            $ops[0].uuid | Should -Be '069a79f4-44e9-4726-a5be-fca90e38aaf5'
            Join-Path $F.Server 'plugins\LuckPerms\yaml-storage\users\069a79f4-44e9-4726-a5be-fca90e38aaf5.yml' |
                Should -FileContentMatch '^primary-group: admin$'
            (Get-State $F).owner | Should -Be 'Notch'
        }

        It 'passes the profile lookup error through' {
            $F = New-Fixture
            { Add-Owner -Context (New-Ctx $F (New-Manifest $F)) -Name 'Nobody' } | Should -Throw '*no such player*'
        }

        It 'fails instead of prompting when non-interactive' {
            $F = New-Fixture
            $ctx = New-Ctx $F (New-Manifest $F)
            { Install-Server -Context $ctx -NoOwner 6>$null } | Should -Throw '*-NonInteractive was given*'
        }
    }
}

Describe 'Fabric servers' {
    BeforeEach {
        Mock Start-Sleep -ModuleName Realms {}
    }

    It 'installs the launcher as fabric-server-launch.jar and mods in mods\, then is a no-op' {
        $F = New-Fixture
        Use-FabricDefaults $F
        $mod = New-Entry $F 'Foo-mod [1.0].jar' @{ 'fabric.mod.json' = '{"id":"foo"}' }
        $pack = New-Entry $F 'Pack.zip' @{ 'pack.mcmeta' = '{}' }
        $m = New-Manifest $F @() @($pack) @($mod) $F.Fabric

        Install-Fixture $F $m | Out-Null
        Get-Sha512 (Join-Path $F.Server 'fabric-server-launch.jar') | Should -Be $F.Fabric.hashes.sha512
        Join-Path $F.Server 'paper.jar' | Should -Not -Exist
        Get-Sha512 (Join-Path $F.Mods 'Foo-mod [1.0].jar') | Should -Be $mod.hashes.sha512
        Join-Path $F.Packs 'Pack.zip' | Should -Exist
        $F.Plugins | Should -Not -Exist
        Join-Path $F.Server 'config\luckperms\luckperms.conf' | Should -Exist
        $state = Get-State $F
        $state.server_type | Should -Be 'fabric'
        ($state.mods -join ',') | Should -Be 'Foo-mod [1.0].jar'
        @($state.plugins).Count | Should -Be 0
        Get-Content -LiteralPath (Join-Path $F.Server '.realms-state.json') -Raw | Should -Match '"mods":\s*\['

        $F.Fetched.Clear()
        $out = Install-Server -Context (New-Ctx $F $m) -NoOwner 6>&1 | Out-String
        $out | Should -Match 'Everything is up to date'
        $F.Fetched.Count | Should -Be 0
    }

    It 'removes a dropped mod but never touches subfolders or files it does not manage' {
        $F = New-Fixture
        $a = New-Entry $F 'A.jar' @{ 'fabric.mod.json' = 'a' }
        $b = New-Entry $F 'B.jar' @{ 'fabric.mod.json' = 'b' }
        Install-Fixture $F (New-Manifest $F @() @() @($a, $b) $F.Fabric)
        Write-Text (Join-Path $F.Mods 'luckperms\yaml-storage\groups\admin.yml') 'name: admin'
        Write-Text (Join-Path $F.Mods 'HostMod.jar') 'host'

        Install-Fixture $F (New-Manifest $F @() @() @($a) $F.Fabric)
        Join-Path $F.Mods 'A.jar' | Should -Exist
        Join-Path $F.Mods 'B.jar' | Should -Not -Exist
        Join-Path $F.Mods 'HostMod.jar' | Should -Exist
        Join-Path $F.Mods 'luckperms\yaml-storage\groups\admin.yml' | Should -Exist
        ((Get-State $F).mods -join ',') | Should -Be 'A.jar'
    }

    It 'refuses plugins in a Fabric manifest and mods in a Paper one' {
        $F = New-Fixture
        $jar = New-Entry $F 'X.jar' @{ 'x' = 'x' }
        { Install-Fixture $F (New-Manifest $F @($jar) @() @() $F.Fabric) } | Should -Throw "*lists plugins, but a Fabric server can't load plugins*"
        { Install-Fixture $F (New-Manifest $F @() @() @($jar)) } | Should -Throw "*lists mods, but a Paper server can't load mods*"
        $F.Server | Should -Not -Exist
    }

    Context 'patched mods' {
        BeforeEach {
            $F = New-Fixture
            $F.Mod = New-Entry $F 'silvers-lib.jar' @{ 'fabric.mod.json' = 'original'; 'data/x/fn.mcfunction' = 'say hi' }
            $F.Patch = New-Patch $F 'silvers-lib' @{ 'fabric.mod.json' = 'patched' }
            $F.Dest = Join-Path $F.Mods 'silvers-lib.jar'
        }

        It 'replaces the patched files, keeps the rest, and is then a no-op' {
            $m = New-Manifest $F @() @() @(Add-PatchTo $F.Mod $F.Patch) $F.Fabric
            Install-Fixture $F $m | Out-Null
            Read-ZipEntry $F.Dest 'fabric.mod.json' | Should -Be 'patched'
            Read-ZipEntry $F.Dest 'data/x/fn.mcfunction' | Should -Be 'say hi'
            (Get-State $F).patched.'silvers-lib.jar'.sha256 | Should -Not -BeNullOrEmpty

            $F.Fetched.Clear()
            $stamp = (Get-Item $F.Dest).LastWriteTimeUtc
            Install-Fixture $F $m | Out-Null
            $F.Fetched.Count | Should -Be 0
            (Get-Item $F.Dest).LastWriteTimeUtc | Should -Be $stamp
        }

        It 'throws when base_sha512 is not the upstream file the entry pins' {
            $m = New-Manifest $F @() @() @(Add-PatchTo $F.Mod $F.Patch ('cd' * 64)) $F.Fabric
            { Install-Fixture $F $m } | Should -Throw '*different upstream file*'
            $F.Dest | Should -Not -Exist
        }

        It 'throws when a patch adds a file the mod does not have' {
            Write-Text (Join-Path $F.Realms 'patches\silvers-lib\data\x\new.json') '{}'
            { Install-Fixture $F (New-Manifest $F @() @() @(Add-PatchTo $F.Mod $F.Patch) $F.Fabric) } |
                Should -Throw '*no matching file in silvers-lib.jar: data/x/new.json*'
            $F.Dest | Should -Not -Exist
        }
    }

    It 'puts the Owner in the LuckPerms admin rank under mods\luckperms' {
        $F = New-Fixture
        Use-FabricDefaults $F
        $m = New-Manifest $F @() @() @() $F.Fabric
        Install-Fixture $F $m @{ Owner = 'notch' } | Out-Null
        Join-Path $F.Mods 'luckperms\yaml-storage\users\069a79f4-44e9-4726-a5be-fca90e38aaf5.yml' |
            Should -FileContentMatch '^primary-group: admin$'
        Join-Path $F.Server 'plugins\LuckPerms' | Should -Not -Exist
        (Get-State $F).owner | Should -Be 'Notch'
    }
}

Describe 'Upgrades and server type switches' {
    BeforeEach {
        Mock Start-Sleep -ModuleName Realms {}
    }

    It 'upgrades a 1.x Paper install (state without mods or server_type) with no re-downloads' {
        $F = New-Fixture
        $keep = New-Entry $F 'Keep.jar' @{ 'plugin.yml' = 'keep' }
        $old = New-Entry $F 'Old-1.jar' @{ 'plugin.yml' = 'v1' } 'old'
        $pack = Add-PatchTo (New-Entry $F 'Effects.zip' @{ 'pack.mcmeta' = 'original' }) (New-Patch $F 'effects' @{ 'pack.mcmeta' = 'patched' })
        Install-Fixture $F (New-Manifest $F @($keep, $old) @($pack)) | Out-Null
        # Rewrite the state the way 1.x wrote it, and drop 'mods' from the manifest like 1.x had.
        $s = Get-State $F
        $legacy = [ordered]@{ version = $s.version; java = $s.java; owner = $null; plugins = @($s.plugins)
            datapacks = @($s.datapacks); patched = $s.patched }
        Write-Text (Join-Path $F.Server '.realms-state.json') (ConvertTo-Json -InputObject $legacy -Depth 10)
        Write-Text (Join-Path $F.Server 'world\level.dat') 'a world'
        $F.Fetched.Clear()

        $new = New-Entry $F 'Old-2.jar' @{ 'plugin.yml' = 'v2' } 'old'
        $m = New-Manifest $F @($keep, $new) @($pack) -Version '1.2.0'
        $m.PSObject.Properties.Remove('mods')
        Install-Fixture $F $m | Out-Null

        $F.Fetched.Keys | Should -Be @($new.url)
        Join-Path $F.Plugins 'Old-1.jar' | Should -Not -Exist
        Join-Path $F.Plugins 'Old-2.jar' | Should -Exist
        Read-ZipEntry (Join-Path $F.Packs 'Effects.zip') 'pack.mcmeta' | Should -Be 'patched'
        $state = Get-State $F
        $state.version | Should -Be '1.2.0'
        $state.server_type | Should -Be 'paper'
        @($state.mods).Count | Should -Be 0
    }

    It 'stops and changes nothing when a <Was> folder with a world gets a <Now> release' -ForEach @(
        @{ Was = 'paper'; Now = 'fabric'; Legacy = $false }
        @{ Was = 'paper'; Now = 'fabric'; Legacy = $true }
        @{ Was = 'fabric'; Now = 'paper'; Legacy = $false }
    ) {
        $F = New-Fixture
        $jars = @{ paper = 'paper.jar'; fabric = 'fabric-server-launch.jar' }
        $plugin = New-Entry $F 'P.jar' @{ 'plugin.yml' = 'p' }
        $mod = New-Entry $F 'M.jar' @{ 'fabric.mod.json' = 'm' }
        $first = if ($Was -eq 'paper') { New-Manifest $F @($plugin) } else { New-Manifest $F @() @() @($mod) $F.Fabric }
        Install-Fixture $F $first | Out-Null
        $stateFile = Join-Path $F.Server '.realms-state.json'
        if ($Legacy) {
            $s = Get-State $F
            Write-Text $stateFile (ConvertTo-Json -InputObject ([ordered]@{ version = $s.version; java = $s.java; plugins = @($s.plugins); datapacks = @(); patched = @{} }))
        }
        Write-Text (Join-Path $F.Server 'world\level.dat') 'a world'
        $before = @(Get-ChildItem -LiteralPath $F.Root -Recurse -File | ForEach-Object { "$($_.FullName)=$($_.Length)" })
        $stateText = [IO.File]::ReadAllText($stateFile)
        $F.Fetched.Clear()

        $second = if ($Now -eq 'paper') { New-Manifest $F @($plugin) } else { New-Manifest $F @() @() @($mod) $F.Fabric }
        { Install-Fixture $F $second } | Should -Throw '*Unzip this release into a NEW, empty folder*'

        $F.Fetched.Count | Should -Be 0
        [IO.File]::ReadAllText($stateFile) | Should -Be $stateText
        @(Get-ChildItem -LiteralPath $F.Root -Recurse -File | ForEach-Object { "$($_.FullName)=$($_.Length)" }) | Should -Be $before
        Join-Path $F.Server $jars[$Was] | Should -Exist
        Join-Path $F.Server $jars[$Now] | Should -Not -Exist
    }

    It 'switches a folder that has no world yet, removing the old server jar and plugins' {
        $F = New-Fixture
        $plugin = New-Entry $F 'P.jar' @{ 'plugin.yml' = 'p' }
        $mod = New-Entry $F 'M.jar' @{ 'fabric.mod.json' = 'm' }
        $pack = New-Entry $F 'Pack.zip' @{ 'pack.mcmeta' = '{}' }
        Install-Fixture $F (New-Manifest $F @($plugin) @($pack)) | Out-Null
        Install-Fixture $F (New-Manifest $F @() @($pack) @($mod) $F.Fabric) | Out-Null

        Join-Path $F.Server 'paper.jar' | Should -Not -Exist
        Join-Path $F.Plugins 'P.jar' | Should -Not -Exist
        Join-Path $F.Server 'fabric-server-launch.jar' | Should -Exist
        Join-Path $F.Mods 'M.jar' | Should -Exist
        Join-Path $F.Packs 'Pack.zip' | Should -Exist
        (Get-State $F).server_type | Should -Be 'fabric'
    }

    It 'installs a Fabric release normally into an empty folder' {
        $F = New-Fixture
        Install-Fixture $F (New-Manifest $F @() @() @() $F.Fabric) | Out-Null
        Join-Path $F.Server 'fabric-server-launch.jar' | Should -Exist
        (Get-State $F).server_type | Should -Be 'fabric'
    }
}

Describe 'Server layout and launch' {
    It 'launches <Type> with -jar <Jar> <Arg>' -ForEach @(
        @{ Type = 'paper'; Jar = 'paper.jar'; Arg = '--nogui' }
        @{ Type = 'fabric'; Jar = 'fabric-server-launch.jar'; Arg = 'nogui' }
    ) {
        $m = [pscustomobject]@{ server = [pscustomobject]@{ type = $Type } }
        $a = @(Get-LaunchArguments -Manifest $m -MemoryGB 4)
        $a[0..1] | Should -Be @('-Xms4G', '-Xmx4G')
        $a[-3..-1] | Should -Be @('-jar', $Jar, $Arg)
        $a | Should -Contain '-XX:+UseG1GC'
    }

    It 'describes the server as <Want>' -ForEach @(
        @{ Server = @{ type = 'paper'; build = 74 }; Want = 'Paper build 74'; AddOns = 'plugins'; LuckPerms = 'plugins\LuckPerms\yaml-storage' }
        @{ Server = @{ type = 'Fabric'; loader = '0.19.5' }; Want = 'Fabric loader 0.19.5'; AddOns = 'mods'; LuckPerms = 'mods\luckperms\yaml-storage' }
    ) {
        $l = Get-ServerLayout -Manifest ([pscustomobject]@{ server = [pscustomobject]$Server })
        $l.Description | Should -Be $Want
        $l.AddOns | Should -Be $AddOns
        $l.LuckPerms | Should -Be $LuckPerms
    }

    It 'shows the Fabric loader and mod count in status' {
        $F = New-Fixture
        $mod = New-Entry $F 'M.jar' @{ 'fabric.mod.json' = 'm' }
        $out = Show-Status -Context (New-Ctx $F (New-Manifest $F @() @() @($mod) $F.Fabric)) 6>&1 | Out-String
        $out | Should -Match 'Fabric loader 0\.1\.0'
        $out | Should -Match 'Mods: 1'
    }

    It 'rejects an unknown server type <Type> clearly, before changing anything' -ForEach @(
        @{ Type = 'forge' }, @{ Type = '' }
    ) {
        $F = New-Fixture
        $F.Paper.type = $Type
        $m = New-Manifest $F
        { Get-LaunchArguments -Manifest $m -MemoryGB 2 } | Should -Throw "*server type '$Type'*only knows 'paper' and 'fabric'*"
        { Install-Fixture $F $m } | Should -Throw "*server type '$Type'*"
        $F.Server | Should -Not -Exist
    }
}

Describe 'Export-HostingBundle' {
    BeforeAll {
        # Entry name -> @{ Text; Mode (Unix permission bits); Host (zip "version made by" OS) }.
        function Read-ExportZip([string]$Path) {
            $out = @{}
            $zip = [IO.Compression.ZipFile]::OpenRead($Path)
            try {
                foreach ($e in $zip.Entries) {
                    $r = New-Object IO.StreamReader ($e.Open())
                    try { $text = $r.ReadToEnd() } finally { $r.Dispose() }
                    $mode = ([BitConverter]::ToUInt32([BitConverter]::GetBytes([int]$e.ExternalAttributes), 0) -shr 16) -band 511
                    $out[$e.FullName] = @{ Text = $text; Mode = $mode; Host = $null }
                }
            } finally { $zip.Dispose() }
            # The made-by OS is not exposed by .NET Framework: read it from the central directory.
            $b = [IO.File]::ReadAllBytes($Path)
            for ($i = 0; $i -lt $b.Length - 46; $i++) {
                if ($b[$i] -eq 0x50 -and $b[$i + 1] -eq 0x4b -and $b[$i + 2] -eq 1 -and $b[$i + 3] -eq 2) {
                    $name = [Text.Encoding]::UTF8.GetString($b, $i + 46, [BitConverter]::ToUInt16($b, $i + 28))
                    if ($out.ContainsKey($name)) { $out[$name].Host = $b[$i + 5] }
                }
            }
            return $out
        }

        function Find-Sh {
            $c = Get-Command sh.exe -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($c) { return $c.Source }
            foreach ($p in "$env:ProgramFiles\Git\bin\sh.exe", "$env:ProgramFiles\Git\usr\bin\sh.exe") { if (Test-Path -LiteralPath $p) { return $p } }
            return $null
        }

        # Installs a fixture of the given type with leftovers an export must skip, and exports it.
        function New-ExportFixture([string]$Type) {
            $F = New-Fixture
            $F.Java.version = 'jdk-21.0.5+11'
            $pack = New-Entry $F 'Pack [1].zip' @{ 'pack.mcmeta' = '{}' }
            if ($Type -eq 'fabric') {
                $F.AddOn = 'mods/M.jar'
                $F.M = New-Manifest $F @() @($pack) @(New-Entry $F 'M.jar' @{ 'fabric.mod.json' = 'm' }) $F.Fabric
                $F.Jar = 'fabric-server-launch.jar'
            } else {
                $F.AddOn = 'plugins/P.jar'
                $F.M = New-Manifest $F @(New-Entry $F 'P.jar' @{ 'plugin.yml' = 'p' }) @($pack)
                $F.Jar = 'paper.jar'
            }
            Install-Fixture $F $F.M | Out-Null
            foreach ($junk in 'logs\latest.log', 'crash-reports\c.txt', 'cache\x.bin', '.fabric\remapped.jar', 'libraries\lib.jar',
                'versions\mc.jar', 'bluemap\web\index.html', 'plugins\.paper-remapped\r.jar', 'world\session.lock', 'x.part') {
                Write-Text (Join-Path $F.Server $junk) 'junk'
            }
            Write-Text (Join-Path $F.Server 'world\level.dat') 'a world'
            Write-Text (Join-Path $F.Server 'config\keep.json') '{}'
            $F.Zip = Export-HostingBundle -Context (New-Ctx $F $F.M) 6>$null
            $F.Top = 'TheRealms-1.0.0-hosting/'
            return $F
        }
    }

    It 'packs a <Type> install with its jar at the top, without logs, caches or install state' -ForEach @(
        @{ Type = 'paper' }, @{ Type = 'fabric' }
    ) {
        $F = New-ExportFixture $Type
        $F.Zip | Should -Be (Join-Path $F.Root 'exports\TheRealms-1.0.0-hosting.zip')
        $z = Read-ExportZip $F.Zip
        @($z.Keys | Where-Object { -not $_.StartsWith($F.Top) }) | Should -BeNullOrEmpty
        foreach ($want in $F.Jar, $F.AddOn, 'world/datapacks/Pack [1].zip', 'world/level.dat', 'eula.txt', 'server.properties',
            'config/keep.json', 'start.sh', 'start.bat', 'docker-compose.yml', 'HOSTING.txt') {
            $z.Keys | Should -Contain ($F.Top + $want)
        }
        $skipped = @($z.Keys | Where-Object { $_ -match '/(logs|crash-reports|cache|\.fabric|libraries|versions|bluemap|plugins/\.paper-remapped)/|\.part$|session\.lock$|\.realms-state\.json$' })
        $skipped | Should -BeNullOrEmpty
        $z[$F.Top + 'eula.txt'].Text | Should -Match 'eula=true'
    }

    It 'writes a <Type> start.sh (LF, 0755, Unix) with the flags of Get-LaunchArguments' -ForEach @(
        @{ Type = 'paper' }, @{ Type = 'fabric' }
    ) {
        $F = New-ExportFixture $Type
        $z = Read-ExportZip $F.Zip
        $sh = $z[$F.Top + 'start.sh']
        $sh.Text | Should -Not -Match "`r"
        $sh.Text | Should -BeLike "#!/bin/sh`n*"
        $sh.Mode | Should -Be 493   # 0755
        $sh.Host | Should -Be 3     # made on Unix, so unzip applies the mode
        $sh.Text | Should -Match 'MEMORY_GB="\$\{MEMORY_GB:-10\}"'
        $sh.Text | Should -Match '-Xms"\$\{MEMORY_GB\}"G'
        $sh.Text | Should -Match '-Xmx"\$\{MEMORY_GB\}"G'
        foreach ($a in Get-LaunchArguments -Manifest $F.M -MemoryGB 4) {
            if ($a -notmatch '^-Xm[sx]') { $sh.Text | Should -Match ('(^|\s)' + [regex]::Escape($a) + '(\s|$)') }
        }
        $z[$F.Top + 'start.bat'].Text | Should -Match "-jar $([regex]::Escape($F.Jar))"
        $z[$F.Top + 'start.bat'].Text | Should -Match "-Xmx%MEMORY_GB%G"
        $z[$F.Top + 'start.bat'].Text.Replace("`r`n", '') | Should -Not -Match "`n"
        $z[$F.Top + 'HOSTING.txt'].Text | Should -Match ([regex]::Escape($F.Jar))
        $z[$F.Top + 'HOSTING.txt'].Text | Should -Match 'Java 21'
    }

    It 'runs start.sh with MEMORY_GB and exactly the arguments of Get-LaunchArguments' {
        $sh = Find-Sh
        if (-not $sh) { Set-ItResult -Skipped -Because 'no sh.exe (Git for Windows) on this machine'; return }
        $F = New-ExportFixture 'fabric'
        $dir = Join-Path $F.Dir 'unzipped'
        [IO.Compression.ZipFile]::ExtractToDirectory($F.Zip, $dir)
        $run = Join-Path $dir 'TheRealms-1.0.0-hosting'
        [IO.File]::WriteAllText((Join-Path $run 'fakejava'), "#!/bin/sh`nprintf '%s\n' `"`$@`"`n", $script:Utf8)
        Push-Location $run
        try {
            $seven = @(& $sh -c 'MEMORY_GB=7 JAVA=./fakejava sh ./start.sh')
            $default = @(& $sh -c 'JAVA=./fakejava sh ./start.sh')
            $null = & $sh -c 'MEMORY_GB=lots JAVA=./fakejava sh ./start.sh 2>/dev/null'
            $badExit = $LASTEXITCODE
        } finally { Pop-Location }
        $seven | Should -Be @(Get-LaunchArguments -Manifest $F.M -MemoryGB 7)
        $default | Should -Be @(Get-LaunchArguments -Manifest $F.M -MemoryGB 10)
        $badExit | Should -Be 1
    }

    It 'pins the Docker image to the manifest Java and maps the game, voice and map ports' {
        $F = New-ExportFixture 'paper'
        $yml = (Read-ExportZip $F.Zip)[$F.Top + 'docker-compose.yml'].Text
        $yml | Should -Not -Match "`r"
        $yml | Should -Match '(?m)^    image: eclipse-temurin:21-jre$'
        $yml | Should -Match '(?m)^    command: \["sh", "\./start\.sh"\]$'
        $yml | Should -Match ([regex]::Escape("`"$($F.Port):$($F.Port)/tcp`""))
        $yml | Should -Match '"24454:24454/udp"'
        $yml | Should -Match '"8100:8100/tcp"'
        $yml | Should -Match 'restart: unless-stopped'
    }

    It 'overwrites an earlier export and leaves no temporary file' {
        $F = New-ExportFixture 'paper'
        Write-Text (Join-Path $F.Server 'config\later.json') '{}'
        Export-HostingBundle -Context (New-Ctx $F $F.M) 6>$null | Out-Null
        @(Get-ChildItem -LiteralPath (Join-Path $F.Root 'exports') -Force | ForEach-Object { $_.Name }) | Should -Be @('TheRealms-1.0.0-hosting.zip')
        (Read-ExportZip $F.Zip).Keys | Should -Contain ($F.Top + 'config/later.json')
    }

    It 'refuses while the server is running' {
        $F = New-Fixture
        Install-Fixture $F (New-Manifest $F) | Out-Null
        Mock Test-ServerRunning -ModuleName Realms { $true }
        { Export-HostingBundle -Context (New-Ctx $F (New-Manifest $F)) } | Should -Throw '*server is running*'
        Join-Path $F.Root 'exports' | Should -Not -Exist
    }

    It 'refuses before anything is installed' {
        $F = New-Fixture
        { Export-HostingBundle -Context (New-Ctx $F (New-Manifest $F)) } | Should -Throw '*isn''t installed yet*'
    }
}

Describe 'Get-MemoryGB' {
    It 'maps <Gb> GB of RAM to <Want> GB' -ForEach @(
        @{ Gb = 4; Want = 3 }, @{ Gb = 8; Want = 3 }, @{ Gb = 8.5; Want = 3 }, @{ Gb = 12; Want = 4 },
        @{ Gb = 16; Want = 6 }, @{ Gb = 16.5; Want = 6 }, @{ Gb = 24; Want = 8 }, @{ Gb = 32; Want = 10 },
        @{ Gb = 64; Want = 10 }
    ) {
        Get-MemoryGB -TotalBytes ($Gb * 1GB) | Should -Be $Want
    }

    It 'prefers -Requested, then REALMS_MEMORY_GB' {
        Get-MemoryGB -TotalBytes 32GB -Requested 2 -EnvValue '8' | Should -Be 2
        Get-MemoryGB -TotalBytes 32GB -EnvValue '8' | Should -Be 8
    }
}

Describe 'Backup-Server' {
    It 'copies the server folder and keeps the newest 14 backups' {
        $F = New-Fixture
        Write-Text (Join-Path $F.Server 'server.properties') "server-port=$($F.Port)`n"
        Write-Text (Join-Path $F.Server 'world\level.dat') 'level'
        Write-Text (Join-Path $F.Server 'plugins\Foo.jar') 'jar'
        $backups = Join-Path $F.Root 'backups'
        foreach ($i in 0..14) { New-Item -ItemType Directory -Force -Path (Join-Path $backups ('2020-01-01_00-00-{0:D2}' -f $i)) | Out-Null }

        Backup-Server -Context (New-Ctx $F (New-Manifest $F)) 6>$null

        $left = @(Get-ChildItem -LiteralPath $backups -Directory | Sort-Object Name)
        $left.Count | Should -Be 14
        $left[0].Name | Should -Be '2020-01-01_00-00-02'
        $newest = $left[-1].FullName
        Join-Path $newest 'world\level.dat' | Should -Exist
        Join-Path $newest 'plugins\Foo.jar' | Should -Not -Exist
    }
}

Describe 'Invoke-Rcon' {
    BeforeAll {
        # A fake Minecraft RCON server: replies to each command in two packets (with a colour code),
        # then answers the marker packet, like the real one does. The first $Drops connections are
        # cut after the first command, like a server still busy right after "Done".
        $script:FakeRcon = {
            param($Listener, $Secret, [int]$Drops)
            $enc = New-Object System.Text.UTF8Encoding $false
            for ($conn = 0; ; $conn++) {
            $deadline = (Get-Date).AddSeconds(15)
            while (-not $Listener.Pending()) {
                if ((Get-Date) -gt $deadline) { return 'no client' }
                Start-Sleep -Milliseconds 20
            }
            $client = $Listener.AcceptTcpClient()
            $client.ReceiveTimeout = 10000
            $s = $client.GetStream()
            $readN = {
                param([int]$Count)
                $buf = New-Object byte[] $Count
                $off = 0
                while ($off -lt $Count) {
                    $n = $s.Read($buf, $off, $Count - $off)
                    if ($n -le 0) { throw 'closed' }
                    $off += $n
                }
                return , $buf
            }
            $recv = {
                $len = [BitConverter]::ToInt32((& $readN 4), 0)
                $d = & $readN $len
                @{ Id = [BitConverter]::ToInt32($d, 0); Type = [BitConverter]::ToInt32($d, 4); Body = $enc.GetString($d, 8, $len - 10) }
            }
            $sendP = {
                param([int]$Id, [int]$Type, [string]$Body)
                $b = $enc.GetBytes($Body)
                $buf = New-Object byte[] (14 + $b.Length)
                [BitConverter]::GetBytes([int](10 + $b.Length)).CopyTo($buf, 0)
                [BitConverter]::GetBytes($Id).CopyTo($buf, 4)
                [BitConverter]::GetBytes($Type).CopyTo($buf, 8)
                $b.CopyTo($buf, 12)
                $s.Write($buf, 0, $buf.Length)
            }
            try {
                $auth = & $recv
                if ($auth.Body -ne $Secret) { & $sendP -1 2 ''; return 'rejected' }
                & $sendP $auth.Id 2 ''
                if ($conn -lt $Drops) { [void](& $recv); continue }
                while ($true) {
                    try { $cmd = & $recv } catch { break }
                    $marker = & $recv
                    & $sendP $cmd.Id 0 "reply to $($cmd.Body) part1;"
                    & $sendP $cmd.Id 0 ([string][char]0xA7 + 'a part2')
                    & $sendP $marker.Id 0 'Unknown request 0'
                }
                return 'ok'
            } finally { $client.Close() }
            }
        }

        function Invoke-WithFakeRcon([string]$Secret, [string]$ClientSecret, [string[]]$Commands, [int]$Drops = 0) {
            $F = New-Fixture
            $listener = New-Object Net.Sockets.TcpListener ([Net.IPAddress]::Loopback, 0)
            $listener.Start()
            $ps = [PowerShell]::Create()
            try {
                Write-Text (Join-Path $F.Server 'server.properties') (
                    "server-port=$($F.Port)`nenable-rcon=true`nrcon.port=$($listener.LocalEndpoint.Port)`nrcon.password=$ClientSecret`n")
                [void]$ps.AddScript($script:FakeRcon).AddArgument($listener).AddArgument($Secret).AddArgument($Drops)
                $handle = $ps.BeginInvoke()
                try {
                    return Invoke-Rcon -Context (New-Ctx $F (New-Manifest $F)) -Commands $Commands
                } finally {
                    if (-not $handle.AsyncWaitHandle.WaitOne(15000)) { $ps.Stop() }
                }
            } finally {
                $listener.Stop()
                $ps.Dispose()
            }
        }
    }

    It 'joins multi-packet replies per command and strips colour codes' {
        $out = @(Invoke-WithFakeRcon 'pw' 'pw' @('list', 'seed'))
        $out.Count | Should -Be 2
        $out[0] | Should -Be 'reply to list part1; part2'
        $out[1] | Should -Be 'reply to seed part1; part2'
    }

    It 'reconnects when a busy server drops the connection' {
        Mock Start-Sleep -ModuleName Realms {}
        $out = @(Invoke-WithFakeRcon 'pw' 'pw' @('datapack list enabled') -Drops 2)
        $out | Should -Be @('reply to datapack list enabled part1; part2')
        Should -Invoke Start-Sleep -ModuleName Realms -Times 2 -Exactly
    }

    It 'gives up after five dropped connections' {
        Mock Start-Sleep -ModuleName Realms {}
        { Invoke-WithFakeRcon 'pw' 'pw' @('seed') -Drops 9 } | Should -Throw
        Should -Invoke Start-Sleep -ModuleName Realms -Times 4 -Exactly
    }

    It 'throws when the password is rejected' {
        { Invoke-WithFakeRcon 'pw' 'wrong' @('list') } | Should -Throw '*password was rejected*'
    }

    It 'refuses when RCON is turned off' {
        $F = New-Fixture
        Write-Text (Join-Path $F.Server 'server.properties') "enable-rcon=false`n"
        { Invoke-Rcon -Context (New-Ctx $F (New-Manifest $F)) -Commands 'list' } | Should -Throw '*RCON is turned off*'
    }
}

Describe 'server.properties' {
    It 'round-trips through Read-ServerProperties and Set-ServerProperty' {
        $path = Join-Path $TestDrive 'rt\server.properties'
        # A Java-escaped colour code as in the real Defaults (kept ASCII).
        $motd = 'motd=\u00a76The Realms = fun'
        Write-Text $path "#comment=not a key`r`n$motd`r`nserver-port=25565`r`nrcon.port=25575`r`n"

        $before = Read-ServerProperties $path
        $before.Keys.Count | Should -Be 3
        $before['motd'] | Should -Be $motd.Substring(5)

        Set-ServerProperty -Path $path -Name 'server-port' -Value '25566'
        Set-ServerProperty -Path $path -Name 'rcon.port' -Value '$1'
        Set-ServerProperty -Path $path -Name 'level-seed' -Value '42'

        $after = Read-ServerProperties $path
        $after['server-port'] | Should -Be '25566'
        $after['rcon.port'] | Should -Be '$1'
        $after['level-seed'] | Should -Be '42'
        $after['motd'] | Should -Be $before['motd']
        $text = [IO.File]::ReadAllText($path)
        $text | Should -BeLike "#comment=not a key`r`n$motd`r`n*"
        $text | Should -Match "level-seed=42`r`n$"
    }

    It 'reads a missing file as empty' {
        (Read-ServerProperties (Join-Path $TestDrive 'nope.properties')).Count | Should -Be 0
    }
}

Describe 'Expand-Template' {
    It 'fills every placeholder, including empty values and $ signs' {
        Expand-Template -Text "a={{A}}`nb={{B}}`nc={{A}}" -Values @{ A = '$1'; B = '' } | Should -Be "a=`$1`nb=`nc=`$1"
    }

    It 'throws naming the placeholders it could not fill' {
        { Expand-Template -Text 'x={{X}} y={{Y}}' -Values @{ X = '1' } } | Should -Throw '*{{Y}}*'
    }
}

Describe 'Real manifest contract' {
    It '<Kind> <Entry.file> has a file name and a usable hash' -ForEach $realArtifacts {
        $Entry.file | Should -Not -BeNullOrEmpty
        $Entry.file | Should -Not -Match '[\\/]'
        $Entry.url | Should -Match '^https://'
        [long]$Entry.size | Should -BeGreaterThan 0
        $h = Get-ExpectedHash $Entry
        $h.Algorithm | Should -BeIn @('SHA512', 'SHA256')
        $h.Value | Should -Match ('^[0-9a-f]{' + $(if ($h.Algorithm -eq 'SHA512') { 128 } else { 64 }) + '}$')
    }

    It 'has a server type this installer knows' {
        $l = Get-ServerLayout -Manifest (Get-Content -LiteralPath (Join-Path $RepoRoot 'package\realms\manifest.json') -Raw | ConvertFrom-Json)
        $l.Type | Should -BeIn @('paper', 'fabric')
    }

    It 'patched <Entry.file> pins its patch to the upstream file' -ForEach $realPatched {
        $Entry.patch | Should -Not -BeOfType [string]
        $Entry.patch.base_sha512 | Should -Be $Entry.hashes.sha512
        Join-Path $RepoRoot ('package\realms\' + $Entry.patch.path.Replace('/', '\')) | Should -Exist
    }
}
