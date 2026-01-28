# polymarket
Capture Lakers game win probability history from Kalshi.

## Usage

The script is dependency-free and expects Kalshi API endpoints to be
reachable. If the default endpoints require a different path or parameters,
override them via CLI flags.

```bash
python lakers_odds_scraper.py --search "Lakers" --interval 10 --output-dir output
```

### Common adjustments

* `--base-url`: API host (default: https://exchange-api.kalshi.com)
* `--markets-path`: markets listing path (default: /trade-api/v2/markets)
* `--history-template`: odds history path (default: /trade-api/v2/markets/{market_id}/trades)
* `--interval`: resample interval in seconds (default: 10)
* `--no-svg`: disable SVG win-probability chart output
* `--no-html`: disable interactive HTML chart output with hover tooltips

Example with custom endpoints:

```bash
python lakers_odds_scraper.py \
  --base-url "https://example.kalshi.com" \
  --markets-path "/custom/markets" \
  --history-template "/custom/markets/{market_id}/trades" \
  --interval 5
```

## Testing

This repo uses `pytest`. Unit tests run without network access. Live Kalshi
API checks are optional and skipped by default. To run them locally, set the
environment variable below:

```bash
KALSHI_LIVE_TESTS=1 pytest -m live
```
