@echo off
title Enterprise Policy RAG - All Services
cd /d "%~dp0"
echo ===================================================
echo Launching Enterprise Policy AI Assistant...
echo ===================================================

echo [1/2] Launching Backend...
start "Enterprise Policy Backend" cmd /c "%~dp0run_backend.bat"

timeout /t 3 /nobreak >nul

echo [2/2] Launching Frontend...
start "Enterprise Policy Frontend" cmd /c "%~dp0run_frontend.bat"

echo.
echo ===================================================
echo Services are starting in separate windows:
echo - Backend API:  http://localhost:8000
echo - Swagger Docs: http://localhost:8000/docs
echo - Frontend UI:  http://localhost:5173
echo ===================================================
