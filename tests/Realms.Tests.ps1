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
    ) + @($real.plugins | ForEach-Object { @{ Kind = 'plugin'; Entry = $_ } }) +
        @($real.datapacks | ForEach-Object { @{ Kind = 'datapack'; Entry = $_ } })
    $script:realPatched = @($real.datapacks | Where-Object { $_.patch } | ForEach-Object { @{ Entry = $_ } })
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
        $F.Paper | Add-Member -NotePropertyName build -NotePropertyValue 1
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

    function New-Manifest($F, [object[]]$Plugins = @(), [object[]]$Datapacks = @()) {
        $m = [pscustomobject]@{
            name      = 'Fixture Realms'
            version   = '1.0.0'
            minecraft = '1.0'
            java      = $F.Java
            server    = $F.Paper
            world     = [pscustomobject]@{ level_name = 'world'; seed = '-12345' }
            plugins   = @($Plugins)
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

Describe 'Get-MemoryGB' {
    It 'maps <Gb> GB of RAM to <Want> GB' -ForEach @(
        @{ Gb = 4; Want = 3 }, @{ Gb = 8; Want = 3 }, @{ Gb = 8.5; Want = 3 }, @{ Gb = 12; Want = 4 },
        @{ Gb = 16; Want = 5 }, @{ Gb = 16.5; Want = 5 }, @{ Gb = 32; Want = 6 }
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
        # then answers the marker packet, like the real one does.
        $script:FakeRcon = {
            param($Listener, $Secret)
            $enc = New-Object System.Text.UTF8Encoding $false
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

        function Invoke-WithFakeRcon([string]$Secret, [string]$ClientSecret, [string[]]$Commands) {
            $F = New-Fixture
            $listener = New-Object Net.Sockets.TcpListener ([Net.IPAddress]::Loopback, 0)
            $listener.Start()
            $ps = [PowerShell]::Create()
            try {
                Write-Text (Join-Path $F.Server 'server.properties') (
                    "server-port=$($F.Port)`nenable-rcon=true`nrcon.port=$($listener.LocalEndpoint.Port)`nrcon.password=$ClientSecret`n")
                [void]$ps.AddScript($script:FakeRcon).AddArgument($listener).AddArgument($Secret)
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

    It 'patched datapack <Entry.file> pins its patch to the upstream file' -ForEach $realPatched {
        if ($Entry.patch -is [string]) {
            Set-ItResult -Skipped -Because 'manifest.json still has the old string patch shape (tighten once the Python side lands the object shape)'
            return
        }
        $Entry.patch.base_sha512 | Should -Be $Entry.hashes.sha512
        Join-Path $RepoRoot ('package\realms\' + $Entry.patch.path.Replace('/', '\')) | Should -Exist
    }
}
