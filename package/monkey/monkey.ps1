#Requires -Version 5.1
<#
.SYNOPSIS
    Installs, updates, starts, stops and backs up Monkey SMP Minecraft server.

.DESCRIPTION
    Everything is downloaded from its official source (Adoptium, PaperMC or Fabric, Modrinth) and checked
    against the hashes pinned in manifest.json before it is used. Running "install" again is safe:
    files that are already correct are skipped, and files from an older manifest are replaced.

    This script only parses the command line; the work is done by Monkey.psm1 next to it.
    It runs on Windows PowerShell 5.1 (the .bat files) and on PowerShell 7.2+ on Linux and macOS
    (monkey.sh, which the .sh launchers call, finds or installs one).

    Layout next to this folder:
        server\    the Minecraft server (world, plugins or mods, configs)
        java\      the Java runtime the server uses (one folder per platform, e.g. java\linux-x64)
        pwsh\      PowerShell for monkey.sh on Linux and macOS (not used on Windows)
        backups\   world backups made by "backup"
        exports\   zips made by "export-host" for running the server on an online host

.EXAMPLE
    .\monkey.ps1 start
    .\monkey.ps1 install -AcceptEula -Owner Notch -NonInteractive
    .\monkey.ps1 add-player Steve
    .\monkey.ps1 export-host -NonInteractive -NoOwner
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'install', 'stop', 'backup', 'add-player', 'status', 'rcon', 'export-host')]
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

    # Server memory in GB. 0 = pick from the computer's RAM (a container's memory limit on Linux).
    # Also read from MONKEY_MEMORY_GB.
    [int]$MemoryGB = 0,

    # start only: install, then write how to run the server to this file instead of running it
    # (monkey.sh then runs java itself; see Start-Server in Monkey.psm1).
    [string]$LaunchFile
)

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'Monkey.psm1') -Force

$ctx = New-MonkeyContext -Root (Split-Path $PSScriptRoot -Parent) -MonkeyDir $PSScriptRoot -NonInteractive:$NonInteractive
$install = @{ Context = $ctx; AcceptEula = $AcceptEula; Owner = $Owner; NoOwner = $NoOwner }

switch ($Command) {
    'start' {
        $java = Install-Server @install
        $ram = Get-TotalMemoryBytes
        $gb = Get-MemoryGB -TotalBytes $ram -Requested $MemoryGB -EnvValue $env:MONKEY_MEMORY_GB
        Start-Server -Context $ctx -Java $java -MemoryGB $gb -LaunchFile $LaunchFile
    }
    'install' { [void](Install-Server @install) }
    'export-host' {
        # Installs (or updates) here first, then packs the result for an online host. Never starts the server.
        [void](Install-Server @install)
        [void](Export-HostingBundle -Context $ctx)
    }
    'stop' { Stop-Server -Context $ctx }
    'backup' { Backup-Server -Context $ctx }
    'add-player' { Add-Player -Context $ctx -Name $Name }
    'status' { Show-Status -Context $ctx }
    'rcon' { Invoke-Rcon -Context $ctx -Commands @($Name) | ForEach-Object { Write-Output $_ } }
}
