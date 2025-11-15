@echo off
REM Wrapper script to always run LNB tests in UV environment
REM Usage: run_tests.cmd [test_number]
REM   1 = Data availability test
REM   2 = Mock data parser test
REM   3 = Comprehensive validation
REM   4 = Discovery guide

echo.
echo ================================================================================
echo   LNB Testing Suite - Always Uses UV Environment
echo ================================================================================
echo.

if "%1"=="" (
    echo Usage: run_tests.cmd [test_number]
    echo.
    echo Available tests:
    echo   1 - Data availability test ^(tests what data LNB API provides^)
    echo   2 - Mock data parser test ^(validates parser with 4 patterns^)
    echo   3 - Comprehensive validation ^(13 test cases^)
    echo   4 - Quick-start discovery ^(interactive endpoint discovery^)
    echo.
    exit /b 0
)

if "%1"=="1" (
    echo [RUN] Data availability test...
    uv run python tools/lnb/test_lnb_data_availability.py
) else if "%1"=="2" (
    echo [RUN] Mock data parser test...
    uv run python test_lnb_parser_with_mocks.py
) else if "%1"=="3" (
    echo [RUN] Comprehensive validation...
    uv run python tools/lnb/test_boxscore_comprehensive.py
) else if "%1"=="4" (
    echo [RUN] Quick-start discovery...
    uv run python tools/lnb/quick_start_discovery.py
) else (
    echo [ERROR] Unknown test number: %1
    echo Use 1-4
    exit /b 1
)

echo.
echo [COMPLETE] Test finished
echo.
