@echo off
rem Makes Windows back up the world every 12 hours (a scheduled task for this user). Run again to update it.
title The Realms - Schedule Backups
schtasks /Create /F /TN "The Realms backup" /SC HOURLY /MO 12 /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"%~dp0realms\realms.ps1\" backup"
if errorlevel 1 (
  echo.
  echo Something went wrong - see the message above. READ ME FIRST.txt has help.
) else (
  echo.
  echo Backups now run every 12 hours while you are signed in to Windows.
  echo They go into the "backups" folder. Copy some of them to another drive or cloud storage now and then.
  echo To turn this off:  schtasks /Delete /TN "The Realms backup" /F
)
echo.
pause
