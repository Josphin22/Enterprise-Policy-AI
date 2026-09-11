@echo off
title Enterprise Policy RAG - Backend
cd /d "%~dp0backend"
echo ===================================================
echo Starting Enterprise Policy RAG Backend (FastAPI)...
echo URL: http://localhost:8000
echo Docs: http://localhost:8000/docs
echo ===================================================

set "PYTHON_EXE=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" -m uvicorn app.main:app --reload --port 8000
pause
