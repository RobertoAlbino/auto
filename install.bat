@echo off
rem install.bat - install `auto` on Windows.
rem
rem Creates an `auto.cmd` launcher in %LOCALAPPDATA%\Programs\auto and adds that
rem folder to your user PATH. Re-running is safe: it overwrites the launcher.
rem
rem     install.bat
rem
setlocal EnableExtensions

set "REPO=%~dp0"
set "SRC=%REPO%auto"
set "INSTALL_DIR=%LOCALAPPDATA%\Programs\auto"
set "SHIM=%INSTALL_DIR%\auto.cmd"

if not exist "%SRC%" (
    echo install: cannot find 'auto' next to install.bat ^(looked in %REPO%^) 1>&2
    exit /b 1
)

rem Locate a Python launcher: prefer the `py` launcher, fall back to `python`.
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo install: Python 3 is required but was not found on PATH. 1>&2
    echo          Install it from https://www.python.org/ and run install.bat again. 1>&2
    exit /b 1
)

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

rem Write the launcher. %%* in this file becomes %* in the generated auto.cmd.
> "%SHIM%" echo @echo off
>>"%SHIM%" echo %PY% "%SRC%" %%*
echo install: wrote launcher %SHIM%

rem Add the install dir to the user PATH if it is not already there.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d='%INSTALL_DIR%'; $p=[Environment]::GetEnvironmentVariable('Path','User'); if (-not $p) { $p='' }; if (($p -split ';') -notcontains $d) { [Environment]::SetEnvironmentVariable('Path', ($p.TrimEnd(';') + ';' + $d).TrimStart(';'), 'User'); Write-Host 'install: added' $d 'to your user PATH' } else { Write-Host 'install:' $d 'is already on your PATH' }"

echo.
echo Done. Open a NEW terminal, then try:  auto claude
endlocal
