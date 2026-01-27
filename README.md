# polymarket
Capture Lakers game win probability history from Polymarket.

## Usage

The script is dependency-free and expects Polymarket API endpoints to be
reachable. If the default endpoints require a different path or parameters,
override them via CLI flags.

```bash
python lakers_odds_scraper.py --search "Lakers" --interval 10 --output-dir output
```

### Common adjustments

* `--base-url`: API host (default: https://gamma-api.polymarket.com)
* `--markets-path`: markets listing path (default: /markets)
* `--history-template`: odds history path (default: /markets/{market_id}/history)
* `--interval`: resample interval in seconds (default: 10)

Example with custom endpoints:

```bash
python lakers_odds_scraper.py \
  --base-url "https://example.polymarket.com" \
  --markets-path "/custom/markets" \
  --history-template "/custom/markets/{market_id}/history" \
  --interval 5
```
