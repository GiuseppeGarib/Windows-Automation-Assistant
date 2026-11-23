@echo off
setlocal
cd /d "%~dp0"
echo Windows Automation Assistant - build portatile
echo Python serve soltanto sul PC di compilazione.
where python >nul 2>nul
if errorlevel 1 (echo ERRORE: Python non trovato sul PC di compilazione.& pause & exit /b 1)
python -m pip install --upgrade pip
if errorlevel 1 goto error
python -m pip install -r requirements.txt
if errorlevel 1 goto error
python -m PyInstaller --noconfirm --clean --windowed --onedir --name WindowsAutomationAssistant --contents-directory _internal app.py
if errorlevel 1 goto error
for %%D in (Procedures Settings History Logs) do if not exist "dist\WindowsAutomationAssistant\Data\%%D" mkdir "dist\WindowsAutomationAssistant\Data\%%D"
(
echo Windows Automation Assistant - Portable
echo Avvia WindowsAutomationAssistant.exe da questa cartella.
echo Mantieni insieme EXE, _internal e Data. Non spostare il solo EXE.
) > "dist\WindowsAutomationAssistant\LEGGIMI.txt"
echo.
echo BUILD COMPLETATA. Copia l'intera cartella dist\WindowsAutomationAssistant sulla pendrive.
pause
exit /b 0
:error
echo BUILD NON RIUSCITA. Controlla gli errori sopra.
pause
exit /b 1
