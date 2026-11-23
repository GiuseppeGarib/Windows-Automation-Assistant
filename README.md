# Windows Automation Assistant

Assistente desktop per Windows, progettato per essere eseguito da pendrive senza installazione sul PC ospite.

## Requisito di portabilità
- Avvio diretto da pendrive, mantenendo insieme l'intera cartella WindowsAutomationAssistant.
- Sul PC ospite non servono Python, pip o installazioni aggiuntive.
- L'applicazione non richiede privilegi amministrativi e non installa servizi, driver o componenti di sistema.
- Procedure e registri vengono salvati nella cartella Data accanto all'eseguibile.
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

La cartella Data viene creata automaticamente al primo avvio.

## Funzioni attuali
- Editor di istruzioni e anteprima.
- Conferma esplicita prima dell'esecuzione.
- Pulsante STOP e registro persistente.
- Libreria persistente di procedure: salvataggio, caricamento ed eliminazione.
- Verifica delle coordinate di clic rispetto alle dimensioni dello schermo.
- Azioni: WAIT, OPEN_URL, TYPE, HOTKEY, CLICK, SCROLL.
- Nessuna esecuzione arbitraria di comandi shell o PowerShell.

## Formato delle istruzioni
    WAIT 1.5
    OPEN_URL https://example.com
    TYPE Testo di prova
    HOTKEY CTRL+L
    CLICK 500 300
    SCROLL -3

CLICK usa coordinate dello schermo in pixel. Le azioni agiscono sulla finestra attiva: utilizzare soltanto su dispositivi e applicazioni per i quali si dispone di autorizzazione.

## Limiti di questa versione
È una prima base funzionale. Non include ancora registrazione guidata, OCR/riconoscimento visivo, selezione dei controlli tramite nome o interpretazione in linguaggio naturale. La compatibilità va verificata su diverse configurazioni Windows.
