@echo off
set "SHORTCUT_PATH=%USERPROFILE%\Desktop\Fabric Identification.bat"
set "TARGET_DIR=%~dp0"

echo @echo off > "%SHORTCUT_PATH%"
echo cd /d "%TARGET_DIR%" >> "%SHORTCUT_PATH%"
echo call run_realtime.bat >> "%SHORTCUT_PATH%"

echo ================================================================
echo  Desktop Shortcut Created Successfully!
echo  Location: %SHORTCUT_PATH%
echo ================================================================
pause
