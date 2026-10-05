@echo off
:: StreetSense — Docker & WSL Virtualization Fix Script
:: Requires Administrator Privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] This script must be run as Administrator!
    echo Right-click fix_docker.bat and select "Run as Administrator".
    pause
    exit /b 1
)

echo ========================================================
echo [1/3] Enabling Virtual Machine Platform...
echo ========================================================
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

echo ========================================================
echo [2/3] Enabling Windows Subsystem for Linux (WSL)...
echo ========================================================
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

echo ========================================================
echo [3/3] Updating WSL Kernel...
echo ========================================================
wsl --update

echo.
echo ========================================================
echo SUCCESS! All required virtualization features are enabled.
echo.
echo IMPORTANT: You MUST RESTART YOUR PC now for Windows to
echo apply these changes.
echo.
echo After rebooting, open Docker Desktop and click "Recheck and retry".
echo ========================================================
pause
