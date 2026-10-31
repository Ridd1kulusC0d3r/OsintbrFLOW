@echo off
REM SOSIA - lancador de dois cliques para Windows
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 sosia.py %*
    goto fim
)
where python >nul 2>nul
if %errorlevel%==0 (
    python sosia.py %*
    goto fim
)
echo.
echo  Python nao encontrado neste computador.
echo  Vou abrir a pagina de download. Na instalacao, marque a opcao
echo  "Add python.exe to PATH" e depois clique de novo neste arquivo.
echo.
start "" https://www.python.org/downloads/
:fim
if errorlevel 1 pause
