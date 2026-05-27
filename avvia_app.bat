@echo off
cd /d "C:\Users\SERGI\AppData\Local\Temp\opencode\SYGS_MASTER_VIEWER"
set STREAMLIT_GATHER_USAGE_STATS=false
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

echo ============================================
echo   SYGS MASTER VIEWER
echo   Gestione dati Excel multi-utente
echo ============================================
echo.
echo Avvio in corso...
echo.
echo Se non si apre il browser, vai a:
echo   http://localhost:8501
echo ============================================
echo.

echo. | "C:\Users\SERGI\AppData\Local\Programs\Python\Python313\python.exe" -m streamlit run app.py --server.port 8501

echo.
pause
