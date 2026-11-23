import json, re, sys, time, webbrowser
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QListWidget, QSplitter, QMessageBox, QPlainTextEdit,
    QStatusBar, QInputDialog)

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.08
except Exception:
    pyautogui = None

APP_NAME = "Windows Automation Assistant"
APP_VERSION = "0.2.0"

def app_directory():
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

def prepare_data_directories():
    root = app_directory() / "Data"
    paths = {"root": root, "procedures": root / "Procedures", "settings": root / "Settings",
             "history": root / "History", "logs": root / "Logs"}
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    probe = root / ".write_test"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()
    return paths

class ParseError(Exception): pass

def parse_script(source):
    actions = []
    for line_no, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"): continue
        parts = line.split(maxsplit=1)
        cmd, arg = parts[0].upper(), parts[1] if len(parts) > 1 else ""
        if cmd == "WAIT":
            try: seconds = float(arg)
            except ValueError: raise ParseError(f"Riga {line_no}: WAIT richiede secondi numerici.")
            if not 0 <= seconds <= 60: raise ParseError(f"Riga {line_no}: WAIT deve essere tra 0 e 60 secondi.")
            actions.append((cmd, seconds))
        elif cmd == "OPEN_URL":
            if not re.match(r"^https?://", arg, re.I): raise ParseError(f"Riga {line_no}: usa un URL http/https valido.")
            actions.append((cmd, arg))
        elif cmd == "TYPE":
            if not arg: raise ParseError(f"Riga {line_no}: TYPE richiede testo.")
            if len(arg) > 1000: raise ParseError(f"Riga {line_no}: testo troppo lungo (max 1000 caratteri).")
            actions.append((cmd, arg))
        elif cmd == "HOTKEY":
            keys = [k.strip().lower() for k in arg.split("+") if k.strip()]
            allowed = {"ctrl","alt","shift","win","enter","tab","esc","escape","space","backspace","delete",
                       "up","down","left","right","home","end","pageup","pagedown"} | {f"f{i}" for i in range(1,13)}
            if not keys or any(k not in allowed and not (len(k)==1 and k.isalnum()) for k in keys):
                raise ParseError(f"Riga {line_no}: combinazione HOTKEY non supportata.")
            actions.append((cmd, keys))
        elif cmd == "CLICK":
            try: x, y = map(int, arg.split())
            except Exception: raise ParseError(f"Riga {line_no}: CLICK richiede coordinate X Y.")
            if not (0 <= x <= 10000 and 0 <= y <= 10000): raise ParseError(f"Riga {line_no}: coordinate fuori limite.")
            actions.append((cmd, (x,y)))
        elif cmd == "SCROLL":
            try: amount = int(arg)
            except ValueError: raise ParseError(f"Riga {line_no}: SCROLL richiede un intero.")
            if not -20 <= amount <= 20: raise ParseError(f"Riga {line_no}: SCROLL deve essere tra -20 e 20.")
            actions.append((cmd, amount))
        else: raise ParseError(f'Riga {line_no}: comando sconosciuto "{cmd}".')
    if len(actions) > 100: raise ParseError("Massimo 100 azioni per procedura.")
    return actions

class Runner(QThread):
    log = Signal(str)
    finished_ok = Signal(bool)
    def __init__(self, actions):
        super().__init__(); self.actions = actions; self.stop_requested = False
    def stop(self): self.stop_requested = True
    def run(self):
        try:
            for i, (cmd,arg) in enumerate(self.actions,1):
                if self.stop_requested: break
                self.log.emit(f"[{i}/{len(self.actions)}] {cmd}")
                if cmd == "WAIT":
                    end = time.monotonic()+arg
                    while time.monotonic()<end and not self.stop_requested: time.sleep(.05)
                elif cmd == "OPEN_URL": webbrowser.open(arg)
                elif cmd == "TYPE":
                    if pyautogui is None: raise RuntimeError("PyAutoGUI non disponibile.")
                    for char in arg:
                        if self.stop_requested: break
                        pyautogui.write(char, interval=0)
                elif cmd == "HOTKEY":
                    if pyautogui is None: raise RuntimeError("PyAutoGUI non disponibile.")
                    pyautogui.hotkey(*arg)
                elif cmd == "CLICK":
                    if pyautogui is None: raise RuntimeError("PyAutoGUI non disponibile.")
                    width,height = pyautogui.size()
                    if arg[0] >= width or arg[1] >= height: raise RuntimeError(f"Coordinate fuori schermo ({width}x{height}).")
                    pyautogui.click(x=arg[0], y=arg[1])
                elif cmd == "SCROLL":
                    if pyautogui is None: raise RuntimeError("PyAutoGUI non disponibile.")
                    pyautogui.scroll(arg)
            self.finished_ok.emit(not self.stop_requested)
        except Exception as exc:
            self.log.emit(f"ERRORE: {exc}"); self.finished_ok.emit(False)

class MainWindow(QMainWindow):
    def __init__(self, paths):
        super().__init__(); self.paths=paths; self.runner=None; self.current_procedure=None
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}"); self.resize(1080,740); self.setMinimumSize(860,600)
        self.setStyleSheet("""
        QMainWindow,QWidget{background:#f3f7fc;color:#172235;font-family:Segoe UI}
        QLabel#title{font-size:24px;font-weight:700;color:#16365f} QLabel#sub{color:#65758b}
        QPushButton{background:#e5edf7;border:1px solid #c9d7e8;border-radius:8px;padding:9px 14px;font-weight:600}
        QPushButton:hover{background:#d8e6f5} QPushButton#primary{background:#2675d8;color:white;border:0}
        QPushButton#stop{background:#ffe4e4;color:#a52222;border-color:#ffc4c4}
        QTextEdit,QPlainTextEdit,QListWidget{background:white;border:1px solid #d6e0eb;border-radius:8px;padding:8px}
        QStatusBar{background:#eaf0f7}""")
        root=QWidget(); layout=QVBoxLayout(root); layout.setContentsMargins(22,18,22,18); layout.setSpacing(12)
        head=QHBoxLayout(); titles=QVBoxLayout(); title=QLabel(APP_NAME); title.setObjectName("title"); titles.addWidget(title)
        sub=QLabel("Automazioni desktop · procedure archiviate sulla pendrive"); sub.setObjectName("sub"); titles.addWidget(sub)
        head.addLayout(titles); head.addStretch(); layout.addLayout(head)
        split=QSplitter(); left=QWidget(); lv=QVBoxLayout(left); lv.addWidget(QLabel("PROCEDURE SALVATE"))
        self.list=QListWidget(); self.list.itemDoubleClicked.connect(self.load_procedure); lv.addWidget(self.list)
        save=QPushButton("Salva procedura…"); save.clicked.connect(self.save_procedure); lv.addWidget(save)
        load=QPushButton("Carica selezionata"); load.clicked.connect(self.load_procedure); lv.addWidget(load)
        delete=QPushButton("Elimina selezionata"); delete.clicked.connect(self.delete_procedure); lv.addWidget(delete)
        right=QWidget(); rv=QVBoxLayout(right); rv.addWidget(QLabel("ISTRUZIONI (una per riga)"))
        self.editor=QPlainTextEdit(); self.editor.setPlaceholderText("# Esempio\nWAIT 1\nOPEN_URL https://example.com\nTYPE Testo di prova")
        self.editor.setPlainText("WAIT 1\nOPEN_URL https://example.com"); rv.addWidget(self.editor,3)
        rv.addWidget(QLabel("REGISTRO SESSIONE")); self.logview=QTextEdit(); self.logview.setReadOnly(True)
        self.logview.setMaximumHeight(155); rv.addWidget(self.logview,1)
        split.addWidget(left); split.addWidget(right); split.setSizes([245,800]); layout.addWidget(split,1)
        buttons=QHBoxLayout(); preview=QPushButton("Verifica istruzioni"); preview.clicked.connect(self.preview); buttons.addWidget(preview)
        run=QPushButton("▶ Esegui"); run.setObjectName("primary"); run.clicked.connect(self.execute); buttons.addWidget(run)
        self.stop_btn=QPushButton("⏹ STOP"); self.stop_btn.setObjectName("stop"); self.stop_btn.clicked.connect(self.stop)
        self.stop_btn.setEnabled(False); buttons.addWidget(self.stop_btn); layout.addLayout(buttons)
        note=QLabel("Nessun comando shell arbitrario. Anteprima e conferma obbligatorie. I dati restano nella cartella Data accanto al programma.")
        note.setObjectName("sub"); note.setWordWrap(True); layout.addWidget(note)
        self.setCentralWidget(root); self.setStatusBar(QStatusBar()); self.statusBar().showMessage(f"Dati: {paths['root']}")
        self.refresh_procedures(); self.log("Modalità portatile attiva: archivio accanto all'eseguibile.")
    def log(self,msg):
        line=f"[{datetime.now():%H:%M:%S}] {msg}"; self.logview.append(line)
        try:
            with (self.paths["logs"]/f"{datetime.now():%Y-%m-%d}.log").open("a",encoding="utf-8") as stream: stream.write(line+"\n")
        except OSError: self.statusBar().showMessage("Attenzione: registro non scrivibile sulla pendrive.")
    def refresh_procedures(self,select_name=None):
        self.list.clear()
        for file in sorted(self.paths["procedures"].glob("*.json")):
            self.list.addItem(file.stem)
            if file.stem==select_name: self.list.setCurrentRow(self.list.count()-1)
    def preview(self):
        try:
            actions=parse_script(self.editor.toPlainText())
            summary="\n".join(f"{i}. {cmd} — {arg}" for i,(cmd,arg) in enumerate(actions,1))
            QMessageBox.information(self,"Anteprima",summary or "(nessuna istruzione)")
            self.statusBar().showMessage(f"{len(actions)} istruzioni valide")
        except ParseError as exc: QMessageBox.warning(self,"Istruzioni non valide",str(exc))
    def execute(self):
        try: actions=parse_script(self.editor.toPlainText())
        except ParseError as exc: QMessageBox.warning(self,"Errore di sintassi",str(exc)); return
        if not actions: QMessageBox.information(self,"Nessuna azione","Inserisci almeno un'istruzione."); return
        summary="\n".join(f"{i}. {cmd} — {arg}" for i,(cmd,arg) in enumerate(actions,1))
        answer=QMessageBox.question(self,"Conferma esecuzione","Eseguire queste istruzioni?\n\n"+summary,
                                    QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if answer!=QMessageBox.Yes: return
        self.runner=Runner(actions); self.runner.log.connect(self.log); self.runner.finished_ok.connect(self.on_finished)
        self.stop_btn.setEnabled(True); self.statusBar().showMessage("In esecuzione…"); self.runner.start()
    def stop(self):
        if self.runner and self.runner.isRunning(): self.runner.stop(); self.statusBar().showMessage("Interruzione in corso…")
    def on_finished(self,ok):
        self.stop_btn.setEnabled(False); self.statusBar().showMessage("Completato" if ok else "Interrotto o errore")
    def save_procedure(self):
        name,ok=QInputDialog.getText(self,"Salva procedura","Nome della procedura:")
        if not ok: return
        name=name.strip()
        if not name or len(name)>60 or name in {".",".."} or re.search(r'[<>:"/\\|?*\x00-\x1f]',name):
            QMessageBox.warning(self,"Nome non valido","Massimo 60 caratteri; evita caratteri speciali."); return
        target=self.paths["procedures"]/f"{name}.json"
        if target.exists():
            answer=QMessageBox.question(self,"Sovrascrivere?",f"La procedura «{name}» esiste già. Sostituirla?",
                                         QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if answer!=QMessageBox.Yes: return
        payload={"name":name,"script":self.editor.toPlainText(),"updated":datetime.now().isoformat(timespec="seconds"),"version":1}
        try:
            target.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
            self.current_procedure=name; self.refresh_procedures(name); self.log(f"Procedura salvata sulla pendrive: {name}")
        except OSError as exc: QMessageBox.critical(self,"Errore di salvataggio",f"Impossibile scrivere sulla pendrive:\n{exc}")
    def load_procedure(self,*_):
        item=self.list.currentItem()
        if not item: return
        name=item.text(); target=self.paths["procedures"]/f"{name}.json"
        try:
            payload=json.loads(target.read_text(encoding="utf-8")); script=payload.get("script")
            if not isinstance(script,str): raise ValueError("Formato della procedura non valido.")
            self.editor.setPlainText(script); self.current_procedure=name; self.log(f"Procedura caricata: {name}")
        except (OSError,ValueError,json.JSONDecodeError) as exc: QMessageBox.warning(self,"Errore di caricamento",str(exc))
    def delete_procedure(self):
        item=self.list.currentItem()
        if not item: return
        name=item.text()
        answer=QMessageBox.question(self,"Elimina procedura",f"Eliminare «{name}» dalla pendrive?",
                                    QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if answer!=QMessageBox.Yes: return
        try:
            (self.paths["procedures"]/f"{name}.json").unlink(missing_ok=True)
            self.refresh_procedures(); self.log(f"Procedura eliminata: {name}")
        except OSError as exc: QMessageBox.warning(self,"Errore",str(exc))

if __name__=="__main__":
    app=QApplication(sys.argv); app.setApplicationName(APP_NAME)
    try: paths=prepare_data_directories()
    except OSError as exc:
        QMessageBox.critical(None,"Archivio portatile non disponibile",
            "Impossibile creare o scrivere Data accanto al programma. Controlla spazio libero e protezione da scrittura. "
            "Nessun dato verrà salvato in altre cartelle del PC.\n\n"+str(exc))
        sys.exit(2)
    window=MainWindow(paths); window.show(); sys.exit(app.exec())
