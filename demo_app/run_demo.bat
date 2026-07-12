@echo off
echo ===================================================
echo   PHANTOMGUARD DEMO LAUNCHER
echo ===================================================
echo Installing dependencies from requirements.txt...
pip install -r requirements.txt

echo.
echo Starting FastAPI Backend Server...
start "PhantomGuard Backend" cmd /k "uvicorn backend.main:app --host 127.0.0.1 --port 8000"

echo Starting Streamlit Dashboard...
start "PhantomGuard Dashboard" cmd /k "streamlit run frontend/dashboard.py"

echo.
echo ===================================================
echo   🎉 SERVICES LAUNCHED SUCCESSFULLY!
echo ===================================================
echo 1. Streamlit Dashboard should open in your browser shortly.
echo 2. To run the simulated coding agent and watch the firewall intercept actions, execute:
echo    python scripts/simulate_agent.py
echo.
pause
