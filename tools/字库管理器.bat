@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

rem ===== Python with tkinter + Pillow + pypinyin =====
set "PYW=C:\Users\ABC\AppData\Local\Programs\Python\Python311\pythonw.exe"
if not exist "%PYW%" set "PYW=C:\Users\ABC\AppData\Local\Programs\Python\Python311\python.exe"
rem ==================================================

start "" "%PYW%" "%~dp0font_gui.py"
