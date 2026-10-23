@echo off
rem Adds Monkey SMP (Fabric, mods, resource packs, shaders) to the official Minecraft Launcher.
title Monkey SMP - Install for Minecraft Launcher
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\install-client.ps1"
if errorlevel 1 (
  echo.
  echo Something went wrong - see the message above. READ ME.txt has help.
)
echo.
pause
