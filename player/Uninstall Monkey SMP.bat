@echo off
rem Removes "Monkey SMP" from the Minecraft Launcher and deletes its game folder (asks first).
title Monkey SMP - Uninstall
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\install-client.ps1" -Uninstall
if errorlevel 1 (
  echo.
  echo Something went wrong - see the message above. READ ME.txt has help.
)
echo.
pause
