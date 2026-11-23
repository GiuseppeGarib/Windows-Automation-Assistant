# Windows Automation Assistant

Portable Windows desktop automation assistant prototype.

## Features
- Simple instruction editor and procedure library
- Safe, explicit instruction preview
- Stop button and step-by-step execution log
- Basic actions: wait, open URL, type text, hotkey, click, scroll
- No arbitrary shell/PowerShell execution

## Run
1. Install Python 3.11+.
2. `python -m pip install -r requirements.txt`
3. `python app.py`

For a portable build, run `build.bat` on Windows. The output will be in `dist/`.

## Instruction format
One instruction per line:

- `WAIT 1.5`
- `OPEN_URL https://example.com`
- `TYPE Hello world`
- `HOTKEY CTRL+L`
- `CLICK 500 300` (coordinates relative to the desktop)
- `SCROLL -3`

The app previews the parsed actions before running. Use only on your own computer and with apps/sites where you have permission. Actions may affect the active window. The stop control requests an immediate stop between actions.
