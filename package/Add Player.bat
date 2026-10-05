@echo off
rem Lets a friend join (adds their Minecraft name to the whitelist).
title The Realms - Add Player
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0realms\realms.ps1" add-player
if errorlevel 1 (
  echo.
  echo Something went wrong - see the message above. READ ME FIRST.txt has help.
)
echo.
pause
