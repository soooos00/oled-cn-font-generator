@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

rem ===== config: change these two lines if needed =====
set "PY=C:\Users\ABC\.workbuddy-ai\binaries\python\envs\default\Scripts\python.exe"
set "OUT=C:\Users\ABC\Documents\STM32\bisai\Other"
rem ====================================================

echo.
echo   === OLED Font Generator ===
echo   Type the Chinese words you want, separated by SPACE.
echo   Example:  ZhouKaiYun  ShiJian  ZhengZhuan  FanZhuan
echo.

set "W="
set /p "W=Words: "

if not defined W (
    echo.
    echo   No input. Nothing changed.
    pause
    exit /b
)

"%PY%" make_font.py "%W%" --out "%OUT%" --preview

echo.
pause
