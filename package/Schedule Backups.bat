@echo off
rem Makes Windows back up the world every 12 hours (a scheduled task for this user). Run again to update it.
rem The task runs from this folder with relative paths, so a long folder path still fits, and each run adds
rem a transcript (errors included) to "scheduled-backups.log" here so a failing backup doesn't go unnoticed.
title The Realms - Schedule Backups
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; $run = New-ScheduledTaskAction -Execute 'powershell.exe' -WorkingDirectory (Get-Location).Path -Argument '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command & .\realms\realms.ps1 backup *>> .\scheduled-backups.log'; $twiceADay = @((New-ScheduledTaskTrigger -Daily -At '06:00'), (New-ScheduledTaskTrigger -Daily -At '18:00')); Register-ScheduledTask -TaskName 'The Realms backup' -Action $run -Trigger $twiceADay -Force | Out-Null"
if errorlevel 1 (
  echo.
  echo Something went wrong - see the message above. READ ME FIRST.txt has help.
) else (
  echo.
  echo Backups now run at 6 AM and 6 PM while you are signed in to Windows.
  echo They go into the "backups" folder; each run's messages are added to scheduled-backups.log.
  echo Copy some backups to another drive or cloud storage now and then.
  echo To turn this off:  schtasks /Delete /TN "The Realms backup" /F
)
echo.
pause
