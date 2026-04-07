# Skill: Web Fetch

Use this skill to download and read the content of web pages.

## How to use it

Use the `WebFetch` tool — Claude Code calls it automatically when you have `internet: true` in your permissions.

If you need manual fetch in Python:

```python
import requests
from bs4 import BeautifulSoup

def fetch_page(url: str, timeout: int = 15) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MyCow/1.0)",
        "Accept-Language": "en-US,en;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    # Force correct encoding
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser")
    # Remove script, style, nav
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)[:8000]
```

## Error handling

- `requests.exceptions.Timeout`: page too slow — skip and continue
- `requests.exceptions.HTTPError` 403/429: site is blocking bots — do not retry
- `requests.exceptions.ConnectionError`: no connection — check internet

## Best practices

- Always explicit timeout (default 15s)
- Do not download binary files (PDF, images) with this skill
- Truncate text to 8000 chars to avoid filling the context
- For sites with dynamic JS the content may be incomplete
