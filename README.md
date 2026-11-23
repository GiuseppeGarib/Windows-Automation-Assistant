# Windows Automation Assistant

Assistente desktop per Windows, progettato per essere eseguito da pendrive senza installazione sul PC ospite.

## Requisito di portabilità
- Avvio diretto da pendrive, mantenendo insieme l'intera cartella WindowsAutomationAssistant.
- Sul PC ospite non servono Python, pip o installazioni aggiuntive.
- Non richiede privilegi amministrativi e non installa servizi, driver o componenti di sistema.
- Procedure, tasti rapidi e registri vengono salvati nella cartella Data accanto all'eseguibile.
- Se Data non è scrivibile, il programma segnala l'errore e non ripiega su cartelle del PC ospite.
- La build usa PyInstaller in modalità onedir: copiare l'intera cartella, non soltanto l'EXE.

Le policy di Windows, antivirus e restrizioni aziendali possono comunque bloccare alcune azioni. Il programma non tenta di aggirare tali restrizioni.

## Preparare la versione portatile
La compilazione va eseguita una volta su un PC Windows di sviluppo con Python 3.11 o successivo:
1. Scaricare il repository.
2. Eseguire build.bat.
3. Copiare l'intera cartella dist/WindowsAutomationAssistant sulla pendrive.
4. Avviare WindowsAutomationAssistant.exe dalla pendrive.

Python serve soltanto sul PC di compilazione, non sui PC ospiti. La compilazione normalmente non richiede privilegi amministrativi.

## Struttura sulla pendrive
    WindowsAutomationAssistant/
      WindowsAutomationAssistant.exe
      _internal/
      LEGGIMI.txt
      Data/
        Procedures/
        Settings/
        History/
        Logs/

## Funzioni attuali
- Editor di istruzioni con anteprima e conferma esplicita.
- Selettore del tema chiaro, scuro o automatico in base alle impostazioni di Windows; preferenza salvata sulla pendrive.
- Libreria persistente: crea, salva, carica ed elimina procedure, con ricerca rapida per nome.
- Creazione guidata delle azioni con richieste dei parametri.
- Modelli di sequenze pronti da inserire nell'editor.
- Guida integrata alla sintassi.
- Tasti rapidi personalizzabili per i comandi dell'app.
- Elenco separato delle hotkey assegnate alle singole procedure, con assegnazione e rimozione dalla schermata principale; le associazioni sono salvate in Data/Settings/settings.json.
- STOP richiamabile anche da tastiera.
- Avvio delle procedure salvate tramite hotkey dedicata, con richiesta di conferma prima dell'esecuzione.
- Registro persistente delle operazioni e cronologia automatica delle esecuzioni, consultabile dall'interfaccia (ultime 100 attività).
- Selettore coordinate CLICK con aggiornamento live del puntatore, indicazione del monitor e acquisizione tramite F8 (senza spostare il puntatore).
- Coordinate riferite al desktop virtuale Windows: supporta monitor secondari anche a sinistra o sopra il principale, con coordinate negative.
- Nessuna esecuzione arbitraria di comandi shell o PowerShell.

## Tasti rapidi iniziali
- Ctrl+Invio: esegui (chiede conferma).
- Ctrl+Shift+V: verifica istruzioni.
- Esc: STOP.
- Ctrl+S: salva procedura.
- Ctrl+N: aggiungi azione guidata.
- Ctrl+,: personalizza tasti rapidi.

Le combinazioni dei comandi dell'app si modificano dal pulsante **Tasti rapidi…**. Le hotkey delle procedure si assegnano selezionando una procedura e usando **Assegna hotkey alla procedura selezionata**; l'elenco dedicato mostra tutte le associazioni e consente di rimuoverle. Un doppio clic su una riga avvia la procedura corrispondente. Anche queste hotkey funzionano solo quando la finestra dell'app è attiva e chiedono conferma prima dell'esecuzione. Sono attive soltanto quando la finestra del programma è in primo piano; non sono hotkey globali di Windows. È possibile lasciare vuoto un campo per disattivare la relativa scorciatoia.

## Formato delle istruzioni
    WAIT 1.5
    OPEN_URL https://example.com
    TYPE Testo di prova
    HOTKEY CTRL+L
    CLICK 500 300  # coordinate globali del desktop virtuale
    SCROLL -3

Usa **Aggiungi azione guidata** per scegliere un comando e inserire i parametri, oppure **Inserisci modello** per partire da una sequenza pronta. CLICK usa coordinate globali del desktop virtuale in pixel; durante l'inserimento mostra la posizione del mouse in tempo reale e consente di acquisirla. Su Windows il clic viene indirizzato anche ai monitor secondari. Le azioni agiscono sulla finestra attiva: utilizzare soltanto su dispositivi e applicazioni per i quali si dispone di autorizzazione.

## Limiti di questa versione
È una prima base funzionale. Non include ancora registrazione guidata delle azioni, OCR/riconoscimento visivo, selezione dei controlli tramite nome o interpretazione in linguaggio naturale. La compatibilità va verificata su diverse configurazioni Windows.
