#Requires -Version 5.1
<#
.SYNOPSIS
    Installs (or updates, or removes) Monkey SMP client pack in the official Minecraft Launcher.

.DESCRIPTION
    Adds a "Monkey SMP" profile to the Minecraft Launcher that plays Fabric with the pack's mods,
    resource packs and shaders from its own game folder. Every file is downloaded from its official
    source (Modrinth) and checked against the hash in the pack before it is used. Running it again
    is safe: files that are already correct are skipped and mods the new pack dropped are removed.
    The player's own files (worlds, screenshots, extra packs, changed settings) are never touched.

    This script only parses the command line; the work is done by PlayerInstall.psm1 next to it.
    It expects to sit in the unzipped TheRealms-Player folder:
        Install for Minecraft Launcher.bat
        TheRealms-Client-<version>.mrpack
        installer\install-client.ps1, PlayerInstall.psm1, fabric-profile.json

.EXAMPLE
    .\install-client.ps1
    .\install-client.ps1 -MemoryGB 6
    .\install-client.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    # The Minecraft Launcher's data folder.
    [string]$MinecraftDir = (Join-Path $env:APPDATA '.minecraft'),

    # The folder Monkey SMP plays from (mods, worlds, screenshots). Fixed, so updates reuse it.
    [string]$GameDir = (Join-Path $env:APPDATA '.the-realms'),

    # Game memory in GB. 0 = pick from the computer's RAM.
    [ValidateRange(0, 64)]
    [int]$MemoryGB = 0,

    # Never prompt: warn instead of waiting for the launcher to close, and uninstall without asking.
    [switch]$NonInteractive,

    # The client pack to install. Default: the one TheRealms-Client-*.mrpack next to the .bat.
    [string]$Pack,

    # Remove the profile (and, after asking, the game folder) instead of installing.
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'PlayerInstall.psm1') -Force

try {
    if (-not $Pack -and -not $Uninstall) { $Pack = Find-ClientPack -Folder (Split-Path $PSScriptRoot -Parent) }
    $ctx = New-PlayerContext -MinecraftDir $MinecraftDir -GameDir $GameDir -Pack $Pack `
        -FabricProfile (Join-Path $PSScriptRoot 'fabric-profile.json') -NonInteractive:$NonInteractive
    if ($Uninstall) {
        [void](Uninstall-Client -Context $ctx)
    } else {
        $ram = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
        [void](Install-Client -Context $ctx -MemoryGB (Get-ClientMemoryGB -TotalBytes $ram -Requested $MemoryGB))
    }
} catch {
    # A plain message for players instead of PowerShell's error dump.
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
