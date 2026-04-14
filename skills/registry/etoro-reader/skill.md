# Skill: eToro Reader

## Goal
Read-only access to eToro portfolio data and financial instruments via the `etoroportfoliomcp` MCP server. Use this skill to fetch portfolio positions, instrument details, and search for tradable assets.

---

## MCP Server

This skill uses the `etoroportfoliomcp` MCP server, started automatically by Claude Code via:

```bash
npx etoroportfoliomcp
```

No API keys required. Data is fetched from eToro's public-facing endpoints.

---

## Available Tools

### `fetch_etoro_portfolio`
Fetch the portfolio of a given eToro user.

```
fetch_etoro_portfolio(username: string)
→ list of open positions with instrument, quantity, P&L
```

### `fetch_instrument_details`
Get details for a specific instrument by its eToro instrument ID.

```
fetch_instrument_details(instrument_id: number | string)
→ name, symbol, asset class, market, current price
```

### `search_instruments`
Search eToro instruments by name or ticker.

```
search_instruments(query: string)
→ list of matching instruments with ID, name, symbol
```

---

## Usage Examples

```markdown
# Get portfolio for user "johndoe"
Use fetch_etoro_portfolio with username "johndoe"

# Look up Apple stock
Use search_instruments with query "Apple"
Then use fetch_instrument_details with the returned instrument_id
```

---

## Constraints

- **Read-only** — this skill cannot place trades or modify any eToro account
- No authentication required for public portfolio data
- Rate-limit requests to avoid being blocked by eToro's servers
- Do not store or log full portfolio data in memory files — treat it as sensitive financial information
