@echo off
cd /d "%~dp0"
echo Starting FastAPI backend on http://127.0.0.1:8001
start "FastAPI" cmd /k py -m uvicorn main:app --host 127.0.0.1 --port 8001
timeout /t 1 >nul
echo Starting Streamlit dashboard on http://localhost:8503
start "Streamlit" cmd /k py -m streamlit run app.py --server.port 8503 --server.headless true
echo Done. Two windows should now be open.