@echo off
title Enterprise Policy RAG - Frontend
cd /d "%~dp0frontend"
echo ===================================================
echo Starting Enterprise Policy RAG Frontend (Vite)...
echo App URL: http://localhost:5173
echo ===================================================

call npm run dev
pause
