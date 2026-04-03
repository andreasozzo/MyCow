# Skill: Web Fetch

Usa questa skill per scaricare e leggere il contenuto di pagine web.

## Come usarla

Usa il tool `WebFetch` — Claude Code lo chiama automaticamente quando hai `internet: true` nei permessi.

Se hai bisogno di fetch manuale in Python:

```python
import requests
from bs4 import BeautifulSoup

def fetch_page(url: str, timeout: int = 15) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MyCow/1.0)",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    # Forza encoding corretto
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser")
    # Rimuovi script, style, nav
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)[:8000]
```

## Gestione errori

- `requests.exceptions.Timeout`: pagina troppo lenta — salta e continua
- `requests.exceptions.HTTPError` 403/429: sito blocca i bot — non riprovare
- `requests.exceptions.ConnectionError`: nessuna connessione — verifica internet

## Best practice

- Timeout sempre esplicito (default 15s)
- Non scaricare file binari (PDF, immagini) con questa skill
- Tronca il testo a 8000 char per evitare di riempire il contesto
- Per siti con JS dinamico il contenuto potrebbe essere incompleto
