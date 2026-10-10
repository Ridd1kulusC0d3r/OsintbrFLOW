@echo off
rem Abre o OSINT Brasil Flow. Deixe esta janela aberta enquanto usa o painel;
rem fechar esta janela encerra o laboratorio.
chcp 65001 >nul
cd /d "%~dp0"
if not exist "OsintbrFLOW\OsintbrFLOW.exe" goto ausente
"OsintbrFLOW\OsintbrFLOW.exe" %*
if errorlevel 1 pause
exit /b
:ausente
echo Nao encontrei o aplicativo. Este arquivo precisa ficar ao lado da pasta OsintbrFLOW.
echo Extraia o .zip inteiro antes de abrir (botao direito, Extrair tudo).
pause
