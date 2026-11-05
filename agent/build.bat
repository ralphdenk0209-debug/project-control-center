@echo off
REM Baut agent.exe fuer Windows. Danach liegt alles in dist\agent\
python -m pip install --upgrade pyinstaller -r requirements.txt || exit /b 1
python -m PyInstaller --onefile --name agent --distpath dist\agent agent.py || exit /b 1
xcopy /E /I /Y wissen dist\agent\wissen >nul
copy /Y config.json dist\agent\ >nul
echo.
echo Fertig: dist\agent\agent.exe  (Ordner dist\agent komplett weitergeben)
