#Requires -Version 5.1
<#
.SYNOPSIS
    Installs, updates, starts, stops and backs up The Realms Minecraft server.

.DESCRIPTION
    Everything is downloaded from its official source (Adoptium, PaperMC or Fabric, Modrinth) and checked
    against the hashes pinned in manifest.json before it is used. Running "install" again is safe:
    files that are already correct are skipped, and files from an older manifest are replaced.

    This script only parses the command line; the work is done by Realms.psm1 next to it.

    Layout next to this folder:
        server\    the Minecraft server (world, plugins or mods, configs)
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
Import-Module (Join-Path $PSScriptRoot 'Realms.psm1') -Force

$ctx = New-RealmsContext -Root (Split-Path $PSScriptRoot -Parent) -RealmsDir $PSScriptRoot -NonInteractive:$NonInteractive
$install = @{ Context = $ctx; AcceptEula = $AcceptEula; Owner = $Owner; NoOwner = $NoOwner }

switch ($Command) {
    'start' {
        $java = Install-Server @install
        $ram = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
        Start-Server -Context $ctx -Java $java -MemoryGB (Get-MemoryGB -TotalBytes $ram -Requested $MemoryGB -EnvValue $env:REALMS_MEMORY_GB)
    }
    'install' { [void](Install-Server @install) }
    'stop' { Stop-Server -Context $ctx }
    'backup' { Backup-Server -Context $ctx }
    'add-player' { Add-Player -Context $ctx -Name $Name }
    'status' { Show-Status -Context $ctx }
    'rcon' { Invoke-Rcon -Context $ctx -Commands @($Name) | ForEach-Object { Write-Output $_ } }
}
