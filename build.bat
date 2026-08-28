@echo off
title AutoForge AI Stable Builder
echo =========================================================
echo   BUILDING: AutoForge AI (by Yassine Della) [STABLE EXE]
echo =========================================================
echo.
echo [1/2] Installing Dependencies...
pip install -r requirements.txt

echo.
echo [2/2] Compiling Executable with Admin Privileges (uac-admin)...
pyinstaller --noconsole --onefile --uac-admin --name "AutoForge-AI" --distpath ./build_output src/autoforge_app.py

echo.
echo =========================================================
echo  Compilation Complete! 
echo  The executable is in 'build_output/AutoForge-AI.exe'
echo =========================================================
pause
