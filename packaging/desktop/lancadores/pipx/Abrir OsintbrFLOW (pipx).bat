@echo off
rem Para quem instalou o pacote Python (wheel) com pipx
rem Deixe esta janela aberta enquanto usa o painel; fecha-la encerra o laboratorio.
chcp 65001 >nul
where osintbr >nul 2>nul
if errorlevel 1 goto ausente
osintbr %*
if errorlevel 1 pause
exit /b
:ausente
echo Comando osintbr nao encontrado. Instale o arquivo .whl da pagina de Releases com: pipx install ./osintbrflow-*.whl
echo Depois rode: pipx ensurepath  e abra este arquivo de novo.
pause
