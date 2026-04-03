# Skill: Brave Search

Usa questa skill per cercare informazioni sul web tramite Brave Search API.

## Come usarla

Usa il tool `WebSearch` — Claude Code lo chiama automaticamente quando hai `internet: true` nei permessi.

Se hai bisogno di controllare i risultati manualmente, la Brave Search API risponde a:

```
GET https://api.search.brave.com/res/v1/web/search
Headers:
  Accept: application/json
  Accept-Encoding: gzip
  X-Subscription-Token: {BRAVE_API_KEY}
Query params:
  q: termine di ricerca
  count: numero risultati (max 20, default 10)
  search_lang: it (italiano) o en (inglese)
  freshness: pd (oggi), pw (settimana), pm (mese)
```

## Parsing risultati

La risposta JSON ha struttura:
```json
{
  "web": {
    "results": [
      {
        "title": "Titolo pagina",
        "url": "https://...",
        "description": "Snippet...",
        "age": "2026-04-01T..."
      }
    ]
  }
}
```

## Gestione errori

- 401: BRAVE_API_KEY non valida o mancante
- 429: rate limit superato — attendi 1 secondo e riprova una volta
- 422: query non valida — semplifica il termine di ricerca

## Best practice

- Usa query brevi e precise (max 5-7 parole)
- Per news recenti aggiungi `freshness: pd`
- Per contenuto italiano usa `search_lang: it`
- Non fare più di 10 ricerche per run
