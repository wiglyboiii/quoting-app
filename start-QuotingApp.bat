@echo off
rem This sets the environment path for the PDF engine
set PATH=%~dp0bin;%PATH%

rem This starts your app silently in the background
start "" pythonw.exe app.py

rem This waits 3 seconds to give the server time to start
timeout /t 3 /nobreak > nul

rem This opens Google Chrome directly to the app
start chrome http://127.0.0.1:5000