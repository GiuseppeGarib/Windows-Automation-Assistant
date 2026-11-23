import sys, time, webbrowser, re
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QListWidget, QSplitter, QMessageBox, QPlainTextEdit,
    QFrame, QStatusBar)

try:
    import pyautogui
    pyautogui.FAILSAFE = True
except Exception:
    pyautogui = None

APP_NAME = 'Windows Automation Assistant'

class ParseError(Exception): pass

def parse_script(source):
    actions=[]
    for line_no, raw in enumerate(source.splitlines(), 1):
        line=raw.strip()
        if not line or line.startswith('#'): continue
        parts=line.split(maxsplit=1); cmd=parts[0].upper(); arg=parts[1] if len(parts)>1 else ''
        if cmd=='WAIT':
            try: seconds=float(arg)
            except ValueError: raise ParseError(f'Riga {line_no}: WAIT richiede secondi numerici.')
            if not 0 <= seconds <= 60: raise ParseError(f'Riga {line_no}: WAIT deve essere tra 0 e 60 secondi.')
            actions.append((cmd, seconds))
        elif cmd=='OPEN_URL':
            if not re.match(r'^https?://',arg,re.I): raise ParseError(f'Riga {line_no}: usa un URL http/https valido.')
            actions.append((cmd,arg))
        elif cmd=='TYPE':
            if not arg: raise ParseError(f'Riga {line_no}: TYPE richiede testo.')
            if len(arg)>1000: raise ParseError(f'Riga {line_no}: testo troppo lungo (max 1000 caratteri).')
            actions.append((cmd,arg))
        elif cmd=='HOTKEY':
            keys=[k.strip().lower() for k in arg.split('+') if k.strip()]
            allowed={'ctrl','alt','shift','win','enter','tab','esc','escape','space','backspace','delete','up','down','left','right','home','end','pageup','pagedown','f1','f2','f3','f4','f5','f6','f7','f8','f9','f10','f11','f12'}
            if not keys or any(k not in allowed and not (len(k)==1 and k.isalnum()) for k in keys): raise ParseError(f'Riga {line_no}: combinazione HOTKEY non supportata.')
            actions.append((cmd,keys))
        elif cmd=='CLICK':
            try: x,y=map(int,arg.split())
            except Exception: raise ParseError(f'Riga {line_no}: CLICK richiede coordinate X Y.')
            if not (0<=x<=10000 and 0<=y<=10000): raise ParseError(f'Riga {line_no}: coordinate fuori limite.')
            actions.append((cmd,(x,y)))
        elif cmd=='SCROLL':
            try: amount=int(arg)
            except ValueError: raise ParseError(f'Riga {line_no}: SCROLL richiede un intero.')
            if not -20<=amount<=20: raise ParseError(f'Riga {line_no}: SCROLL deve essere tra -20 e 20.')
            actions.append((cmd,amount))
        else: raise ParseError(f'Riga {line_no}: comando sconosciuto "{cmd}".')
    return actions

class Runner(QThread):
    log=Signal(str); finished_ok=Signal(bool)
    def __init__(self, actions): super().__init__(); self.actions=actions; self.stop_requested=False
    def stop(self): self.stop_requested=True
    def run(self):
        try:
            for i,(cmd,arg) in enumerate(self.actions,1):
                if self.stop_requested: self.log.emit('⏹ Interruzione richiesta.'); break
                self.log.emit(f'[{i}/{len(self.actions)}] {cmd}')
                if cmd=='WAIT':
                    end=time.monotonic()+arg
                    while time.monotonic()<end:
                        if self.stop_requested: break
                        time.sleep(.05)
                elif cmd=='OPEN_URL': webbrowser.open(arg)
                elif cmd=='TYPE':
                    if pyautogui is None: raise RuntimeError('PyAutoGUI non disponibile.')
                    pyautogui.write(arg, interval=0.01)
                elif cmd=='HOTKEY':
                    if pyautogui is None: raise RuntimeError('PyAutoGUI non disponibile.')
                    pyautogui.hotkey(*arg)
                elif cmd=='CLICK':
                    if pyautogui is None: raise RuntimeError('PyAutoGUI non disponibile.')
                    pyautogui.click(x=arg[0],y=arg[1])
                elif cmd=='SCROLL':
                    if pyautogui is None: raise RuntimeError('PyAutoGUI non disponibile.')
                    pyautogui.scroll(arg)
            self.finished_ok.emit(not self.stop_requested)
        except Exception as e:
            self.log.emit(f'ERRORE: {e}'); self.finished_ok.emit(False)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle(APP_NAME); self.resize(1060,720); self.setMinimumSize(850,580)
        self.runner=None; self.procedures={}
        self.setStyleSheet('''QMainWindow,QWidget{background:#f4f7fb;color:#172235;font-family:Segoe UI} QLabel#title{font-size:24px;font-weight:700;color:#16365f} QLabel#sub{color:#65758b} QPushButton{background:#e5edf7;border:1px solid #c9d7e8;border-radius:8px;padding:9px 14px;font-weight:600} QPushButton:hover{background:#d8e6f5} QPushButton#primary{background:#2675d8;color:white;border:0} QPushButton#stop{background:#ffe4e4;color:#a52222;border-color:#ffc4c4} QTextEdit,QPlainTextEdit,QListWidget{background:white;border:1px solid #d6e0eb;border-radius:8px;padding:8px} QStatusBar{background:#eaf0f7}''')
        root=QWidget(); layout=QVBoxLayout(root); layout.setContentsMargins(22,18,22,18); layout.setSpacing(12)
        head=QHBoxLayout(); titles=QVBoxLayout(); t=QLabel(APP_NAME); t.setObjectName('title'); titles.addWidget(t); s=QLabel('Automazioni desktop · procedure controllate e portabili'); s.setObjectName('sub'); titles.addWidget(s); head.addLayout(titles); head.addStretch(); layout.addLayout(head)
        split=QSplitter(); left=QWidget(); lv=QVBoxLayout(left); lv.addWidget(QLabel('PROCEDURE')); self.list=QListWidget(); self.list.addItem('Nuova procedura'); lv.addWidget(self.list); save=QPushButton('Salva procedura'); save.clicked.connect(self.save_procedure); lv.addWidget(save); load=QPushButton('Carica selezionata'); load.clicked.connect(self.load_procedure); lv.addWidget(load)
        right=QWidget(); rv=QVBoxLayout(right); rv.addWidget(QLabel('ISTRUZIONI (una per riga)')); self.editor=QPlainTextEdit(); self.editor.setPlaceholderText('# Esempio\nWAIT 1\nOPEN_URL https://example.com\nWAIT 2\nTYPE Testo di prova'); self.editor.setPlainText('WAIT 1\nOPEN_URL https://example.com'); rv.addWidget(self.editor,3); rv.addWidget(QLabel('Registro')); self.logview=QTextEdit(); self.logview.setReadOnly(True); self.logview.setMaximumHeight(150); rv.addWidget(self.logview,1)
        split.addWidget(left); split.addWidget(right); split.setSizes([220,800]); layout.addWidget(split,1)
        buttons=QHBoxLayout(); preview=QPushButton('Verifica istruzioni'); preview.clicked.connect(self.preview); buttons.addWidget(preview); run=QPushButton('▶ Esegui'); run.setObjectName('primary'); run.clicked.connect(self.execute); buttons.addWidget(run); self.stop_btn=QPushButton('⏹ STOP'); self.stop_btn.setObjectName('stop'); self.stop_btn.clicked.connect(self.stop); self.stop_btn.setEnabled(False); buttons.addWidget(self.stop_btn); layout.addLayout(buttons)
        note=QLabel('Sicurezza: nessun comando shell arbitrario. Prima dell’esecuzione viene mostrata una conferma.'); note.setObjectName('sub'); layout.addWidget(note)
        self.setCentralWidget(root); self.setStatusBar(QStatusBar()); self.statusBar().showMessage('Pronto')
    def log(self,msg): self.logview.append(msg)
    def preview(self):
        try:
            actions=parse_script(self.editor.toPlainText())
            summary='\n'.join(f'{i}. {cmd} — {arg}' for i,(cmd,arg) in enumerate(actions,1)) or '(nessuna istruzione)'
            QMessageBox.information(self,'Anteprima',summary); self.statusBar().showMessage(f'{len(actions)} istruzioni valide')
        except ParseError as e: QMessageBox.warning(self,'Istruzioni non valide',str(e))
    def execute(self):
        try: actions=parse_script(self.editor.toPlainText())
        except ParseError as e: QMessageBox.warning(self,'Errore di sintassi',str(e)); return
        if not actions: QMessageBox.information(self,'Nessuna azione','Inserisci almeno un’istruzione.'); return
        summary='\n'.join(f'{i}. {cmd} — {arg}' for i,(cmd,arg) in enumerate(actions,1))
        if QMessageBox.question(self,'Conferma esecuzione','Eseguire queste istruzioni?\n\n'+summary, QMessageBox.Yes|QMessageBox.No, QMessageBox.No)!=QMessageBox.Yes: return
        self.runner=Runner(actions); self.runner.log.connect(self.log); self.runner.finished_ok.connect(self.on_finished); self.stop_btn.setEnabled(True); self.statusBar().showMessage('In esecuzione…'); self.runner.start()
    def stop(self):
        if self.runner and self.runner.isRunning(): self.runner.stop(); self.statusBar().showMessage('Interruzione in corso…')
    def on_finished(self,ok): self.stop_btn.setEnabled(False); self.statusBar().showMessage('Completato' if ok else 'Interrotto o errore')
    def save_procedure(self):
        name=self.list.currentItem().text() if self.list.currentItem() else 'Nuova procedura'
        if name=='Nuova procedura': name=f'Procedura {len(self.procedures)+1}'
        self.procedures[name]=self.editor.toPlainText()
        if self.list.findItems(name,0)==[]: self.list.addItem(name)
        self.log(f'Procedura salvata: {name}')
    def load_procedure(self):
        item=self.list.currentItem()
        if not item: return
        name=item.text()
        if name in self.procedures: self.editor.setPlainText(self.procedures[name]); self.statusBar().showMessage(f'Caricata: {name}')

if __name__=='__main__':
    app=QApplication(sys.argv); win=MainWindow(); win.show(); sys.exit(app.exec())
