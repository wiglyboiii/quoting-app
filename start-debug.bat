@echo off
echo --- Starting the application in debug mode...
echo --- If an error occurs, it will be displayed below.
echo ----------------------------------------------------

rem This runs the app and shows all messages in this window
python.exe app.py

rem This command forces the window to stay open so we can read the error
pause