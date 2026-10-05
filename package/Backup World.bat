@echo off
rem Copies the world and settings into the backups folder. Safe while the server runs.
title The Realms - Backup World
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0realms\realms.ps1" backup
if errorlevel 1 (
  echo.
  echo Something went wrong - see the message above. READ ME FIRST.txt has help.
)
echo.
pause
