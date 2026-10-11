@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist roteiro_windows.exe (
 echo O executavel ainda nao foi gerado. Execute COMPILAR_WINDOWS.bat.
 pause
 exit /b 1
)
roteiro_windows.exe
pause
