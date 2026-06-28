@echo off
echo Populating short Japanese test posts into Gnuboard database...
.venv\Scripts\python.exe db_populate_helper.py
pause
