# Skill: Telegram Notify

Usa questa skill per inviare messaggi Telegram tramite il bridge MyCow.

## Come usarla

Il bridge Telegram di MyCow è già attivo quando il daemon gira. Per inviare un messaggio dall'interno di un agente, scrivi in output il testo del messaggio — il trigger "cron" e "heartbeat" inviano automaticamente l'output su Telegram se `telegram_without_approval: true` nel cron.yaml.

## Formattazione messaggi

Telegram supporta Markdown subset:
```
*testo in grassetto*
_testo in corsivo_
`codice inline`
[testo link](https://url)
```

## Struttura messaggio consigliata

```
*[NomeAgente] Titolo breve*

- Punto 1
- Punto 2
- Punto 3

Fonte: [link](https://url)
```

## Limiti

- Massimo 4096 caratteri per messaggio
- Non usare HTML — usa Markdown
- Per liste lunghe, suddividi in più messaggi
- Non inviare messaggi se non hai informazioni nuove da comunicare

## Quando NON inviare

- Se il heartbeat non ha trovato nulla di rilevante → non inviare
- Se il task ha fallito con errore tecnico → il daemon notifica automaticamente
- Non inviare messaggi di "nessuna novità" — solo informazioni utili
