@echo off
setlocal
cd /d "%~dp0"
title Copilot-Agent

REM 1) Programmdateien von .txt zurueck in .py umbenennen
for %%f in (agent mail kalender werkzeuge mcp_client) do (
  if exist "%%f.txt" move /Y "%%f.txt" "%%f.py" >nul
)

REM 2) Python suchen
set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY (
  py -3 --version >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
  echo Python wurde nicht gefunden. Bitte Python 3.10 oder neuer installieren:
  echo https://www.python.org/downloads/   ^(Haken bei "Add python.exe to PATH" setzen^)
  pause
  exit /b 1
)
%PY% -c "import sys; sys.exit(sys.version_info < (3, 10))" || (
  echo Python ist zu alt. Bitte Python 3.10 oder neuer installieren.
  pause
  exit /b 1
)

REM 3) pywin32 fuer das klassische Outlook (nur beim ersten Mal)
%PY% -c "import win32com.client" >nul 2>&1 || (
  echo Installiere pywin32 fuer Outlook ...
  %PY% -m pip install --user -q pywin32 || echo Hinweis: pywin32 nicht installiert - klassisches Outlook geht dann nicht.
)

REM 4) Agent starten
%PY% agent.py
pause
