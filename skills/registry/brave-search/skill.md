# Skill: Brave Search

Use this skill to search for information on the web via the Brave Search API.

## How to use it

Use the `WebSearch` tool — Claude Code calls it automatically when you have `internet: true` in your permissions.

If you need to check results manually, the Brave Search API responds at:

```
GET https://api.search.brave.com/res/v1/web/search
Headers:
  Accept: application/json
  Accept-Encoding: gzip
  X-Subscription-Token: {BRAVE_API_KEY}
Query params:
  q: search term
  count: number of results (max 20, default 10)
  search_lang: it (Italian) or en (English)
  freshness: pd (today), pw (week), pm (month)
```

## Parsing results

The JSON response has this structure:
```json
{
  "web": {
    "results": [
      {
        "title": "Page title",
        "url": "https://...",
        "description": "Snippet...",
        "age": "2026-04-01T..."
      }
    ]
  }
}
```

## Error handling

- 401: BRAVE_API_KEY is invalid or missing
- 429: rate limit exceeded — wait 1 second and retry once
- 422: invalid query — simplify the search term

## Best practices

- Use short, precise queries (max 5-7 words)
- For recent news add `freshness: pd`
- For English content use `search_lang: en`
- Do not make more than 10 searches per run
