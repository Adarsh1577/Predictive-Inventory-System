$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

Write-Host "Starting FastAPI backend on http://127.0.0.1:8001"
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "py -m uvicorn main:app --host 127.0.0.1 --port 8001"
Start-Sleep -Seconds 1

Write-Host "Starting Streamlit dashboard on http://localhost:8503"
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "py -m streamlit run app.py --server.port 8503 --server.headless true"
Write-Host "✅ Startup commands launched. Two windows should now be open."