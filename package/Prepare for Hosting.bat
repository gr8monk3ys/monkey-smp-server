@echo off
rem Makes a zip of the server for running it on an online host instead of this PC (see HOSTING.txt inside).
title Monkey SMP - Prepare for Hosting
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0monkey\monkey.ps1" export-host
if errorlevel 1 (
  echo.
  echo Something went wrong - see the message above. READ ME FIRST.txt has help.
)
echo.
pause
