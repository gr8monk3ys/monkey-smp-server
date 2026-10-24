@echo off
rem Starts Monkey SMP. The first time, it downloads everything and asks two questions.
title Monkey SMP - Start Server
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0realms\realms.ps1" start
if errorlevel 1 (
  echo.
  echo Something went wrong - see the message above. READ ME FIRST.txt has help.
)
echo.
pause
