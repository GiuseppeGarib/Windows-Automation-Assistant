import ctypes, json, re, sys, time, webbrowser
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QCursor, QGuiApplication
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QListWidget, QSplitter, QMessageBox, QPlainTextEdit,
    QStatusBar, QInputDialog, QDialog, QFormLayout, QKeySequenceEdit, QDialogButtonBox, QLineEdit)

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.08
except Exception:
    pyautogui = None

APP_NAME = "Windows Automation Assistant"
APP_VERSION = "0.5.0"
DEFAULT_SHORTCUTS = {"execute":"Ctrl+Return", "preview":"Ctrl+Shift+V", "stop":"Esc",
                     "save":"Ctrl+S", "add_action":"Ctrl+N", "shortcuts":"Ctrl+,"}

def app_directory():
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

def prepare_data_directories():
    root = app_directory() / "Data"
    paths = {"root":root, "procedures":root/"Procedures", "settings":root/"Settings",
             "history":root/"History", "logs":root/"Logs"}
    for path in paths.values(): path.mkdir(parents=True, exist_ok=True)
    probe=root/".write_test"; probe.write_text("ok",encoding="utf-8"); probe.unlink()
    return paths

class ParseError(Exception): pass

def parse_script(source):
    actions=[]
    for line_no,raw in enumerate(source.splitlines(),1):
        line=raw.strip()
        if not line or line.startswith("#"): continue
        parts=line.split(maxsplit=1); cmd=parts[0].upper(); arg=parts[1] if len(parts)>1 else ""
        if cmd=="WAIT":
            try: seconds=float(arg)
            except ValueError: raise ParseError(f"Riga {line_no}: WAIT richiede secondi numerici.")
            if not 0<=seconds<=60: raise ParseError(f"Riga {line_no}: WAIT deve essere tra 0 e 60 secondi.")
            actions.append((cmd,seconds))
        elif cmd=="OPEN_URL":
            if not re.match(r"^https?://",arg,re.I): raise ParseError(f"Riga {line_no}: usa un URL http/https valido.")
            actions.append((cmd,arg))
        elif cmd=="TYPE":
            if not arg: raise ParseError(f"Riga {line_no}: TYPE richiede testo.")
            if len(arg)>1000: raise ParseError(f"Riga {line_no}: testo troppo lungo (max 1000 caratteri).")
            actions.append((cmd,arg))
        elif cmd=="HOTKEY":
            keys=[k.strip().lower() for k in arg.split("+") if k.strip()]
            allowed={"ctrl","alt","shift","win","enter","tab","esc","escape","space","backspace","delete",
                     "up","down","left","right","home","end","pageup","pagedown"}|{f"f{i}" for i in range(1,13)}
            if not keys or any(k not in allowed and not(len(k)==1 and k.isalnum()) for k in keys):
                raise ParseError(f"Riga {line_no}: combinazione HOTKEY non supportata.")
            actions.append((cmd,keys))
        elif cmd=="CLICK":
            try: x,y=map(int,arg.split())
            except Exception: raise ParseError(f"Riga {line_no}: CLICK richiede coordinate X Y.")
            if not(-10000<=x<=10000 and -10000<=y<=10000): raise ParseError(f"Riga {line_no}: coordinate fuori limite.")
            actions.append((cmd,(x,y)))
        elif cmd=="SCROLL":
            try: amount=int(arg)
            except ValueError: raise ParseError(f"Riga {line_no}: SCROLL richiede un intero.")
            if not -20<=amount<=20: raise ParseError(f"Riga {line_no}: SCROLL deve essere tra -20 e 20.")
            actions.append((cmd,amount))
        else: raise ParseError(f'Riga {line_no}: comando sconosciuto "{cmd}".')
    if len(actions)>100: raise ParseError("Massimo 100 azioni per procedura.")
    return actions

class Runner(QThread):
    log=Signal(str); finished_ok=Signal(bool)
    def __init__(self,actions):
        super().__init__(); self.actions=actions; self.stop_requested=False
    def stop(self): self.stop_requested=True
    def run(self):
        try:
            for i,(cmd,arg) in enumerate(self.actions,1):
                if self.stop_requested: break
                self.log.emit(f"[{i}/{len(self.actions)}] {cmd}")
                if cmd=="WAIT":
                    end=time.monotonic()+arg
                    while time.monotonic()<end and not self.stop_requested: time.sleep(.05)
                elif cmd=="OPEN_URL": webbrowser.open(arg)
                elif cmd=="TYPE":
                    if pyautogui is None: raise RuntimeError("PyAutoGUI non disponibile.")
                    for char in arg:
                        if self.stop_requested: break
                        pyautogui.write(char,interval=0)
                elif cmd=="HOTKEY":
                    if pyautogui is None: raise RuntimeError("PyAutoGUI non disponibile.")
                    pyautogui.hotkey(*arg)
                elif cmd=="CLICK":
                    if pyautogui is None: raise RuntimeError("PyAutoGUI non disponibile.")
                    if sys.platform == "win32":
                        user32=ctypes.windll.user32
                        left=user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
                        top=user32.GetSystemMetrics(77)    # SM_YVIRTUALSCREEN
                        width=user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
                        height=user32.GetSystemMetrics(79) # SM_CYVIRTUALSCREEN
                        x,y=arg
                        if not(left<=x<left+width and top<=y<top+height):
                            raise RuntimeError(f"Coordinate fuori dal desktop virtuale ({left},{top} {width}x{height}).")
                        if pyautogui.position()==(0,0):
                            raise RuntimeError("Failsafe attivo: sposta il mouse fuori dall'angolo alto-sinistro.")
                        if not user32.SetCursorPos(x,y):
                            raise RuntimeError("Windows non ha accettato la posizione del puntatore.")
                        user32.mouse_event(0x0002,0,0,0,0)
                        user32.mouse_event(0x0004,0,0,0,0)
                    else:
                        pyautogui.click(x=arg[0],y=arg[1])
                elif cmd=="SCROLL":
                    if pyautogui is None: raise RuntimeError("PyAutoGUI non disponibile.")
                    pyautogui.scroll(arg)
            self.finished_ok.emit(not self.stop_requested)
        except Exception as exc:
            self.log.emit(f"ERRORE: {exc}"); self.finished_ok.emit(False)

class ShortcutDialog(QDialog):
    LABELS={"execute":"Esegui procedura","preview":"Verifica istruzioni","stop":"STOP (interrompi)",
            "save":"Salva procedura","add_action":"Aggiungi azione guidata","shortcuts":"Impostazioni tasti rapidi"}
    def __init__(self,current,parent=None):
        super().__init__(parent); self.setWindowTitle("Personalizza tasti rapidi"); self.edits={}
        layout=QVBoxLayout(self); form=QFormLayout()
        for key,label in self.LABELS.items():
            edit=QKeySequenceEdit(QKeySequence(current.get(key,DEFAULT_SHORTCUTS[key])))
            self.edits[key]=edit; form.addRow(label,edit)
        layout.addLayout(form)
        info=QLabel("Le scorciatoie funzionano quando la finestra dell'app è attiva. Lascia vuoto per disattivarne una.")
        info.setWordWrap(True); layout.addWidget(info)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
    def values(self):
        return {key:edit.keySequence().toString(QKeySequence.PortableText) for key,edit in self.edits.items()}

class ClickCoordinateDialog(QDialog):
    """Inserimento coordinate con lettura live del desktop virtuale multi-monitor."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Coordinate del clic")
        self.setMinimumWidth(390)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Sposta il mouse sul punto da selezionare. Le coordinate sono aggiornate in tempo reale."))
        self.live = QLabel("X: —    Y: —")
        self.live.setStyleSheet("font-size:20px;font-weight:700;color:#1764b2;padding:8px")
        layout.addWidget(self.live)
        self.monitor = QLabel("Monitor: —")
        layout.addWidget(self.monitor)
        form = QFormLayout()
        self.coordinates = QLineEdit()
        self.coordinates.setPlaceholderText("X Y, ad esempio -1200 350")
        form.addRow("Coordinate da usare:", self.coordinates)
        layout.addLayout(form)
        capture = QPushButton("Acquisisci posizione attuale (F8)")
        capture.clicked.connect(self.capture_position)
        layout.addWidget(capture)
        self.capture_shortcut = QShortcut(QKeySequence("F8"), self)
        self.capture_shortcut.setContext(Qt.WindowShortcut)
        self.capture_shortcut.activated.connect(self.capture_position)
        info = QLabel("Sposta il puntatore sul punto desiderato e premi F8 per acquisirlo senza spostare il mouse. Le coordinate sono riferite al desktop virtuale: possono essere negative se un monitor si trova a sinistra o sopra quello principale.")
        info.setWordWrap(True)
        layout.addWidget(info)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_position)
        self.timer.start(40)
        self.update_position()

    def update_position(self):
        pos = QCursor.pos()
        self.live.setText(f"X: {pos.x()}    Y: {pos.y()}")
        screen = QGuiApplication.screenAt(pos)
        if screen:
            g = screen.geometry()
            self.monitor.setText(f"Monitor: {screen.name()}  ·  area {g.x()},{g.y()}  {g.width()}×{g.height()}")
        else:
            self.monitor.setText("Monitor: non identificato")

    def capture_position(self):
        pos = QCursor.pos()
        self.coordinates.setText(f"{pos.x()} {pos.y()}")

    def value(self):
        return self.coordinates.text().strip()


class MainWindow(QMainWindow):
    def __init__(self,paths):
        super().__init__(); self.paths=paths; self.runner=None; self.current_procedure=None; self.shortcuts={}
        self.load_settings()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}"); self.resize(1120,770); self.setMinimumSize(900,620)
        self.setStyleSheet("""
        QMainWindow,QWidget{background:#f3f7fc;color:#172235;font-family:Segoe UI}
        QLabel#title{font-size:24px;font-weight:700;color:#16365f} QLabel#sub{color:#65758b}
        QPushButton{background:#e5edf7;border:1px solid #c9d7e8;border-radius:8px;padding:8px 12px;font-weight:600}
        QPushButton:hover{background:#d8e6f5} QPushButton#primary{background:#2675d8;color:white;border:0}
        QPushButton#stop{background:#ffe4e4;color:#a52222;border-color:#ffc4c4}
        QTextEdit,QPlainTextEdit,QListWidget{background:white;border:1px solid #d6e0eb;border-radius:8px;padding:8px}
        QStatusBar{background:#eaf0f7}""")
        root=QWidget(); layout=QVBoxLayout(root); layout.setContentsMargins(20,16,20,16); layout.setSpacing(10)
        head=QHBoxLayout(); titles=QVBoxLayout(); title=QLabel(APP_NAME); title.setObjectName("title"); titles.addWidget(title)
        sub=QLabel("Automazioni desktop · procedure e impostazioni archiviate sulla pendrive"); sub.setObjectName("sub")
        titles.addWidget(sub); head.addLayout(titles); head.addStretch()
        shortcuts_btn=QPushButton("Tasti rapidi…"); shortcuts_btn.clicked.connect(self.configure_shortcuts); head.addWidget(shortcuts_btn)
        help_btn=QPushButton("Guida comandi"); help_btn.clicked.connect(self.show_help); head.addWidget(help_btn)
        layout.addLayout(head)
        split=QSplitter(); left=QWidget(); lv=QVBoxLayout(left); lv.addWidget(QLabel("PROCEDURE SALVATE"))
        self.list=QListWidget(); self.list.itemDoubleClicked.connect(self.load_procedure); lv.addWidget(self.list)
        for label,callback in [("Nuova procedura",self.new_procedure),("Salva procedura…",self.save_procedure),
                               ("Carica selezionata",self.load_procedure),("Elimina selezionata",self.delete_procedure)]:
            btn=QPushButton(label); btn.clicked.connect(callback); lv.addWidget(btn)
        lv.addWidget(QLabel("HOTKEY DELLE PROCEDURE"))
        self.procedure_hotkey_list=QListWidget()
        self.procedure_hotkey_list.setMaximumHeight(150)
        self.procedure_hotkey_list.setToolTip("Elenco delle scorciatoie assegnate alle procedure salvate")
        self.procedure_hotkey_list.itemDoubleClicked.connect(self.run_selected_hotkey_procedure)
        lv.addWidget(self.procedure_hotkey_list)
        assign_hotkey=QPushButton("Assegna hotkey alla procedura selezionata")
        assign_hotkey.clicked.connect(self.assign_procedure_hotkey); lv.addWidget(assign_hotkey)
        remove_hotkey=QPushButton("Rimuovi hotkey")
        remove_hotkey.clicked.connect(self.remove_procedure_hotkey); lv.addWidget(remove_hotkey)
        right=QWidget(); rv=QVBoxLayout(right); rv.addWidget(QLabel("ISTRUZIONI (una per riga)"))
        self.editor=QPlainTextEdit(); self.editor.setPlaceholderText("# Usa Aggiungi azione per comporre la procedura passo passo")
        self.editor.setPlainText("# Esempio\nWAIT 1\nOPEN_URL https://example.com"); rv.addWidget(self.editor,3)
        tools=QHBoxLayout()
        add=QPushButton("＋ Aggiungi azione guidata"); add.clicked.connect(self.add_action); tools.addWidget(add)
        template=QPushButton("Inserisci modello…"); template.clicked.connect(self.insert_template); tools.addWidget(template)
        rv.addLayout(tools)
        rv.addWidget(QLabel("REGISTRO SESSIONE")); self.logview=QTextEdit(); self.logview.setReadOnly(True)
        self.logview.setMaximumHeight(140); rv.addWidget(self.logview,1)
        split.addWidget(left); split.addWidget(right); split.setSizes([250,820]); layout.addWidget(split,1)
        buttons=QHBoxLayout(); preview=QPushButton("Verifica istruzioni"); preview.clicked.connect(self.preview); buttons.addWidget(preview)
        run=QPushButton("▶ Esegui"); run.setObjectName("primary"); run.clicked.connect(self.execute); buttons.addWidget(run)
        self.stop_btn=QPushButton("⏹ STOP"); self.stop_btn.setObjectName("stop"); self.stop_btn.clicked.connect(self.stop)
        self.stop_btn.setEnabled(False); buttons.addWidget(self.stop_btn); layout.addLayout(buttons)
        note=QLabel("Tasti rapidi modificabili · anteprima e conferma prima dell'esecuzione · dati nella cartella Data accanto al programma.")
        note.setObjectName("sub"); note.setWordWrap(True); layout.addWidget(note)
        self.setCentralWidget(root); self.setStatusBar(QStatusBar()); self.statusBar().showMessage(f"Dati: {paths['root']}")
        self.refresh_procedures(); self.install_shortcuts(); self.log("Modalità portatile attiva.")
    def load_settings(self):
        self.settings_file=self.paths["settings"]/"settings.json"
        self.settings={"shortcuts":dict(DEFAULT_SHORTCUTS),"procedure_hotkeys":{}}
        try:
            if self.settings_file.exists():
                saved=json.loads(self.settings_file.read_text(encoding="utf-8"))
                if isinstance(saved,dict):
                    if isinstance(saved.get("shortcuts"),dict):
                        self.settings["shortcuts"].update({k:v for k,v in saved["shortcuts"].items() if k in DEFAULT_SHORTCUTS and isinstance(v,str)})
                    if isinstance(saved.get("procedure_hotkeys"),dict):
                        self.settings["procedure_hotkeys"]={k:v for k,v in saved["procedure_hotkeys"].items()
                                                            if isinstance(k,str) and isinstance(v,str) and v.strip()}
        except (OSError,ValueError,json.JSONDecodeError): pass
        self.shortcuts=self.settings["shortcuts"]
    def save_settings(self):
        try:
            self.settings_file.write_text(json.dumps(self.settings,ensure_ascii=False,indent=2),encoding="utf-8")
            return True
        except OSError as exc:
            QMessageBox.warning(self,"Impostazioni non salvate",f"Impossibile scrivere sulla pendrive:\n{exc}")
            return False
    def install_shortcuts(self):
        for shortcut in self._shortcut_objects if hasattr(self,"_shortcut_objects") else []: shortcut.deleteLater()
        self._shortcut_objects=[]
        callbacks={"execute":self.execute,"preview":self.preview,"stop":self.stop,"save":self.save_procedure,
                   "add_action":self.add_action,"shortcuts":self.configure_shortcuts}
        used={}
        for key,callback in callbacks.items():
            sequence=self.shortcuts.get(key,"").strip()
            if not sequence: continue
            try: parsed=QKeySequence(sequence)
            except Exception: continue
            if parsed.isEmpty(): continue
            normalized=parsed.toString(QKeySequence.PortableText)
            if normalized in used:
                self.log(f"Tasto rapido duplicato ignorato: {normalized}"); continue
            used[normalized]=key
            shortcut=QShortcut(parsed,self); shortcut.setContext(Qt.WindowShortcut); shortcut.activated.connect(callback)
            self._shortcut_objects.append(shortcut)
        for procedure_name,sequence in self.settings.get("procedure_hotkeys",{}).items():
            if not sequence.strip(): continue
            try: parsed=QKeySequence(sequence)
            except Exception: continue
            if parsed.isEmpty(): continue
            normalized=parsed.toString(QKeySequence.PortableText)
            if normalized in used:
                self.log(f"Hotkey procedura in conflitto ignorata: {procedure_name} ({normalized})"); continue
            used[normalized]=f"procedura {procedure_name}"
            shortcut=QShortcut(parsed,self); shortcut.setContext(Qt.WindowShortcut)
            shortcut.activated.connect(lambda name=procedure_name: self.run_procedure_hotkey(name))
            self._shortcut_objects.append(shortcut)
    def configure_shortcuts(self):
        dialog=ShortcutDialog(self.shortcuts,self)
        if dialog.exec()!=QDialog.Accepted: return
        values=dialog.values(); used={}
        for key,value in values.items():
            if value and value in used:
                QMessageBox.warning(self,"Conflitto tasti rapidi",f"{value} è assegnato sia a «{used[value]}» sia a «{ShortcutDialog.LABELS[key]}». Scegli combinazioni diverse.")
                return
            if value: used[value]=ShortcutDialog.LABELS[key]
        previous=self.shortcuts; self.shortcuts=values; self.settings["shortcuts"]=values
        if self.save_settings():
            self.install_shortcuts(); self.log("Tasti rapidi aggiornati e salvati sulla pendrive.")
        else:
            self.shortcuts=previous; self.settings["shortcuts"]=previous; self.install_shortcuts()
    def refresh_procedure_hotkeys(self):
        if not hasattr(self,"procedure_hotkey_list"): return
        self.procedure_hotkey_list.clear()
        mappings=self.settings.get("procedure_hotkeys",{})
        for name,sequence in sorted(mappings.items(),key=lambda item:item[0].casefold()):
            if (self.paths["procedures"]/f"{name}.json").exists():
                self.procedure_hotkey_list.addItem(f"{sequence}    →    {name}")
    def assign_procedure_hotkey(self):
        item=self.list.currentItem()
        if not item:
            QMessageBox.information(self,"Seleziona una procedura","Seleziona prima una procedura salvata nell'elenco superiore.")
            return
        name=item.text()
        dialog=QDialog(self); dialog.setWindowTitle(f"Hotkey — {name}")
        layout=QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"Premi la combinazione da assegnare a «{name}»:"))
        edit=QKeySequenceEdit(QKeySequence(self.settings.get("procedure_hotkeys",{}).get(name,"")))
        layout.addWidget(edit)
        info=QLabel("La combinazione avvia questa procedura chiedendo conferma. Funziona quando la finestra dell'app è attiva.")
        info.setWordWrap(True); layout.addWidget(info)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        if dialog.exec()!=QDialog.Accepted: return
        sequence=edit.keySequence().toString(QKeySequence.PortableText)
        if not sequence:
            QMessageBox.information(self,"Nessuna hotkey","Non è stata inserita alcuna combinazione.")
            return
        for key,app_sequence in self.shortcuts.items():
            if app_sequence and QKeySequence(app_sequence)==QKeySequence(sequence):
                QMessageBox.warning(self,"Hotkey già utilizzata",f"{sequence} è già assegnata a una funzione dell'app.")
                return
        for other_name,other_sequence in self.settings.get("procedure_hotkeys",{}).items():
            if other_name!=name and other_sequence and QKeySequence(other_sequence)==QKeySequence(sequence):
                QMessageBox.warning(self,"Hotkey già utilizzata",f"{sequence} è già assegnata alla procedura «{other_name}».")
                return
        previous=dict(self.settings.get("procedure_hotkeys",{}))
        self.settings.setdefault("procedure_hotkeys",{})[name]=sequence
        if self.save_settings():
            self.install_shortcuts(); self.refresh_procedure_hotkeys()
            self.log(f"Hotkey {sequence} assegnata alla procedura «{name}».")
        else:
            self.settings["procedure_hotkeys"]=previous
    def remove_procedure_hotkey(self):
        item=self.procedure_hotkey_list.currentItem()
        if not item:
            QMessageBox.information(self,"Seleziona una hotkey","Seleziona una riga nell'elenco delle hotkey.")
            return
        name=item.text().split("→",1)[-1].strip()
        mappings=self.settings.get("procedure_hotkeys",{})
        if name not in mappings: return
        previous=dict(mappings); del mappings[name]
        if self.save_settings():
            self.install_shortcuts(); self.refresh_procedure_hotkeys()
            self.log(f"Hotkey rimossa dalla procedura «{name}».")
        else:
            self.settings["procedure_hotkeys"]=previous
    def run_selected_hotkey_procedure(self,*_):
        item=self.procedure_hotkey_list.currentItem()
        if not item: return
        name=item.text().split("→",1)[-1].strip()
        self.run_procedure_hotkey(name)
    def run_procedure_hotkey(self,name):
        target=self.paths["procedures"]/f"{name}.json"
        try:
            payload=json.loads(target.read_text(encoding="utf-8"))
            source=payload.get("script")
            if not isinstance(source,str): raise ValueError("Formato della procedura non valido.")
        except (OSError,ValueError,AttributeError,json.JSONDecodeError) as exc:
            QMessageBox.warning(self,"Procedura non disponibile",str(exc)); return
        self.execute_script(source,name)
    def add_action(self):
        commands=["WAIT — Attendi","OPEN_URL — Apri un indirizzo web","TYPE — Scrivi testo",
                  "HOTKEY — Premi una combinazione","CLICK — Clic su coordinate","SCROLL — Scorri"]
        choice,ok=QInputDialog.getItem(self,"Aggiungi azione","Scegli il tipo di azione:",commands,0,False)
        if not ok: return
        cmd=choice.split(" — ",1)[0]
        prompts={"WAIT":("Secondi (0–60):","1"),"OPEN_URL":("Indirizzo http/https:","https://"),
                 "TYPE":("Testo da digitare:",""),"HOTKEY":("Tasti separati da + (es. CTRL+L):","CTRL+L"),
                 "CLICK":("Coordinate X Y in pixel (es. 500 300):","500 300"),
                 "SCROLL":("Valore da -20 a 20:","-3")}
        if cmd=="CLICK":
            dialog=ClickCoordinateDialog(self)
            if dialog.exec()!=QDialog.Accepted: return
            value=dialog.value()
            if not value: return
        else:
            label,default=prompts[cmd]
            value,ok=QInputDialog.getText(self,"Parametri azione",label,text=default)
            if not ok: return
        line=f"{cmd} {value.strip()}".rstrip()
        try: parse_script(line)
        except ParseError as exc: QMessageBox.warning(self,"Parametri non validi",str(exc)); return
        cursor=self.editor.textCursor(); cursor.insertText(("\n" if cursor.position()>0 else "")+line)
        self.editor.setTextCursor(cursor); self.editor.setFocus()
        self.log(f"Azione aggiunta: {line}")
    def insert_template(self):
        templates={
          "Apri sito e attendi":"OPEN_URL https://example.com\nWAIT 2",
          "Copia testo negli appunti":"HOTKEY CTRL+L\nTYPE Testo da inserire",
          "Sequenza di tasti":"HOTKEY CTRL+L\nWAIT 0.5\nTYPE https://example.com\nHOTKEY ENTER",
          "Clic, attesa e testo":"CLICK 500 300\nWAIT 1\nTYPE Testo di prova",
          "Modello vuoto con commenti":"# Descrizione della procedura\n# Inserisci qui le azioni\nWAIT 1"
        }
        name,ok=QInputDialog.getItem(self,"Modelli di automazione","Scegli un modello:",list(templates),0,False)
        if ok:
            cursor=self.editor.textCursor(); cursor.insertText(("\n" if cursor.position()>0 else "")+templates[name])
            self.editor.setTextCursor(cursor); self.editor.setFocus()
    def new_procedure(self):
        if self.editor.toPlainText().strip():
            answer=QMessageBox.question(self,"Nuova procedura","Sostituire il contenuto corrente?",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if answer!=QMessageBox.Yes: return
        self.current_procedure=None; self.editor.clear(); self.editor.setFocus()
    def show_help(self):
        QMessageBox.information(self,"Guida rapida",
          "COMANDI DISPONIBILI\n\nWAIT 1.5 — attende fino a 60 secondi\n"
          "OPEN_URL https://example.com — apre un indirizzo web\n"
          "TYPE Ciao — digita testo nella finestra attiva\n"
          "HOTKEY CTRL+L — invia una combinazione di tasti\n"
          "CLICK 500 300 — clicca alle coordinate X Y dello schermo\n"
          "SCROLL -3 — scorre la pagina\n\n"
          "Usa «Aggiungi azione guidata» per inserire un comando con i parametri, oppure «Inserisci modello» per partire da una sequenza pronta.\n"
          "Le scorciatoie dell'app funzionano soltanto quando la finestra è attiva.")
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
        self.refresh_procedure_hotkeys()
    def preview(self):
        try:
            actions=parse_script(self.editor.toPlainText())
            summary="\n".join(f"{i}. {cmd} — {arg}" for i,(cmd,arg) in enumerate(actions,1))
            QMessageBox.information(self,"Anteprima",summary or "(nessuna istruzione)")
            self.statusBar().showMessage(f"{len(actions)} istruzioni valide")
        except ParseError as exc: QMessageBox.warning(self,"Istruzioni non valide",str(exc))
    def execute(self):
        self.execute_script(self.editor.toPlainText(),"procedura corrente")
    def execute_script(self,source,label):
        if self.runner and self.runner.isRunning():
            QMessageBox.information(self,"Automazione già attiva","Interrompi l'automazione corrente prima di avviarne un'altra."); return
        try: actions=parse_script(source)
        except ParseError as exc: QMessageBox.warning(self,"Errore di sintassi",str(exc)); return
        if not actions: QMessageBox.information(self,"Nessuna azione","La procedura non contiene istruzioni."); return
        summary="\n".join(f"{i}. {cmd} — {arg}" for i,(cmd,arg) in enumerate(actions,1))
        answer=QMessageBox.question(self,"Conferma esecuzione",f"Eseguire la procedura «{label}»?\n\n"+summary,
                                    QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if answer!=QMessageBox.Yes: return
        self.runner=Runner(actions); self.runner.log.connect(self.log); self.runner.finished_ok.connect(self.on_finished)
        self.stop_btn.setEnabled(True); self.statusBar().showMessage(f"In esecuzione: {label}…"); self.runner.start()
    def stop(self):
        if self.runner and self.runner.isRunning():
            self.runner.stop(); self.statusBar().showMessage("Interruzione in corso…")
    def on_finished(self,ok):
        self.stop_btn.setEnabled(False); self.statusBar().showMessage("Completato" if ok else "Interrotto o errore")
    def save_procedure(self):
        name,ok=QInputDialog.getText(self,"Salva procedura","Nome della procedura:",text=self.current_procedure or "")
        if not ok: return
        name=name.strip()
        if not name or len(name)>60 or name in {".",".."} or re.search(r'[<>:"/\\|?*\x00-\x1f]',name):
            QMessageBox.warning(self,"Nome non valido","Massimo 60 caratteri; evita caratteri speciali."); return
        target=self.paths["procedures"]/f"{name}.json"
        if target.exists() and name!=self.current_procedure:
            answer=QMessageBox.question(self,"Sovrascrivere?",f"La procedura «{name}» esiste già. Sostituirla?",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
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
        answer=QMessageBox.question(self,"Elimina procedura",f"Eliminare «{name}» dalla pendrive?",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if answer!=QMessageBox.Yes: return
        try:
            (self.paths["procedures"]/f"{name}.json").unlink(missing_ok=True)
            self.settings.setdefault("procedure_hotkeys",{}).pop(name,None)
            self.save_settings()
            self.install_shortcuts()
            self.refresh_procedures(); self.log(f"Procedura eliminata: {name}")
        except OSError as exc: QMessageBox.warning(self,"Errore",str(exc))

if __name__=="__main__":
    app=QApplication(sys.argv); app.setApplicationName(APP_NAME)
    try: paths=prepare_data_directories()
    except OSError as exc:
        QMessageBox.critical(None,"Archivio portatile non disponibile",
            "Impossibile creare o scrivere Data accanto al programma. Nessun dato verrà salvato altrove.\n\n"+str(exc))
        sys.exit(2)
    window=MainWindow(paths); window.show(); sys.exit(app.exec())
