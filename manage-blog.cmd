@echo off
cd /d "%~dp0"
python scripts\blog_manager.py
if errorlevel 1 pause
