@echo off
setlocal
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --windowed --onefile --name WindowsAutomationAssistant app.py
echo.
if exist dist\WindowsAutomationAssistant.exe (echo Build completed: dist\WindowsAutomationAssistant.exe) else (echo Build failed. Check the output above.)
pause
