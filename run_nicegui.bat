@echo off
cd /d "%~dp0"
rem Optional: set EFI_RSCRIPT=C:\Program Files\R\R-4.4.1\bin\Rscript.exe
python app_nicegui.py
pause
