---
name: mitid-status
description: Check the current MitID operational status from digitaliser.dk. Use this when the user asks about MitID drift, whether MitID is down or available, or wants to fetch status/news from digitaliser.dk. Run the bundled Python script — no browser needed.
---

# MitID Drift Status

Checks current MitID operational status from [digitaliser.dk/driftsstatus](https://www.digitaliser.dk/driftsstatus) using a plain HTTP call — no browser required.

## Quick usage

```bash
# Current status only
python3 "$SKILL_DIR/scripts/check_mitid_status.py"

# With latest news/operational updates
python3 "$SKILL_DIR/scripts/check_mitid_status.py" --news

# JSON output (for piping or scripting)
python3 "$SKILL_DIR/scripts/check_mitid_status.py" --news --json
```

**Dependency:** `pip install requests` (only external dependency).

## How it works

The page is server-side rendered by the GoBasic CMS. Two data sources:

1. **Current status** — fetched from the `/driftsstatus` HTML page and parsed directly.  
   The status is in the element `a[href="/mitid"] ~ [data-serviceVariable="Class"]`:
   - `status-ok` → Normal drift (operational)
   - `status-error` → Utilgængelig (unavailable)

2. **News/updates** (`--news` flag) — calls the `proxy.gba` GoBasic RPC API:
   - `POST https://www.digitaliser.dk/mitid/proxy.gba`
   - `Content-Type: versus/callback; charset=UTF-8`
   - Returns an HTML snippet of recent MitID operational news items, filtered to label `MitID`

## Example output

```
❌  MitID: Utilgængelig

Latest MitID updates:
  [Publiceret 31-03-2026] Ustabilitet på MitID
             Oprettet: 09:47...
             https://www.digitaliser.dk/mitid/nyt-fra-mitid/2026/mar/driftsforstyrrelser-mitid-3
```

## Key constants (in script)

| Constant | Value |
|----------|-------|
| MitID service widget ID | `7446031` |
| MitID content category IDs | `6323, 7013, 7006, 7012, 7533, 6320` |
| proxy.gba context hash | `fbd212405d7ef...` (SHA256 for HTTP cache) |

The `MITID_CONTEXT` in the script is a base64-encoded GoBasic filter. Decoded, it filters `NewsPage` content within the MitID category IDs, sorted by date descending, excluding a pinned item (ID 6892). The hash is a SHA256 of the context used by the server for cache keying — it must match the context or the server may return stale/empty results.
