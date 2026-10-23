@echo off
rem Safely stops Monkey SMP (saves the world first).
title Monkey SMP - Stop Server
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0realms\realms.ps1" stop
if errorlevel 1 (
  echo.
  echo Something went wrong - see the message above. READ ME FIRST.txt has help.
)
echo.
pause
