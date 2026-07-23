@echo off
setlocal
pushd "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1" %*
set "build_result=%ERRORLEVEL%"
popd
exit /b %build_result%
