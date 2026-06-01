# Predictive Inventory System

A FastAPI + Streamlit inventory forecasting system with time-series procurement alerts.

## Features
- Per-product 7-day sales forecast using SARIMAX time-series models
- Procurement risk detection with depletion date and recommended reorder quantity
- REST API endpoint: `/api/v1/check-inventory`
- Stored alert history in `procurement_alerts`
- Streamlit dashboard with forecasts, alert metrics, and urgent reorder summary

## Setup
1. Install dependencies:
   ```bash
   py -m pip install -r requirements.txt
   ```
2. Initialize the database and seed base data:
   ```bash
   py setup_db_schema.py
   ```
3. Train the forecasting models:
   ```bash
   py train_model.py
   ```
4. Start the API server:
   ```bash
   py -m uvicorn main:app --host 127.0.0.1 --port 8001
   ```
5. Launch the dashboard:
   ```bash
   py -m streamlit run app.py --server.port 8503
   ```

### One-command startup
You can start both the backend and dashboard together using one of these commands:

- PowerShell:
  ```powershell
  .\run_services.ps1
  ```
- Command Prompt:
  ```cmd
  run_services.bat
  ```

## API Endpoints
- `GET /api/v1/check-inventory` — returns inventory forecasts and procurement alert recommendations
- `GET /api/v1/procurement-alerts` — returns stored procurement alert records

## Notes
- Ensure the MySQL database is available and configured for `inventory_system`
- The dashboard connects to `http://127.0.0.1:8001` by default
