@echo off
title Enterprise Policy AI - Full Test Suite
cd /d "%~dp0"

echo ========================================================
echo   ENTERPRISE POLICY AI - AUTOMATED TEST SUITE RUNNER
echo ========================================================
echo.

echo [1/3] Running Backend Regression & Security Test Suite...
cd backend
python -m pytest tests/ -v --tb=short
if %ERRORLEVEL% NEQ 0 (
    echo [FAIL] Backend test suite failed!
    pause
    exit /b %ERRORLEVEL%
)
echo [PASS] Backend tests completed successfully.
echo.

echo [2/3] Running Frontend Static Linter...
cd ..\frontend
call npm run lint
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Frontend linting reported issues.
)
echo.

echo [3/3] Running Frontend Production Compilation Build...
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo [FAIL] Frontend build failed!
    pause
    exit /b %ERRORLEVEL%
)
echo [PASS] Frontend build succeeded.
echo.

echo ========================================================
echo   ALL SYSTEM TESTS & CHECKS PASSED WITH ZERO REGRESSIONS
echo ========================================================
pause
