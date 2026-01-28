#!/usr/bin/env python3
"""Fetch and resample Polymarket Lakers game odds history.

This script is intentionally dependency-free (stdlib only) so it can run in
minimal environments. You may need to adjust the API endpoints via CLI flags
if Polymarket changes their public endpoints or requires a specific path.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_BASE_URL = "https://gamma-api.polymarket.com"
DEFAULT_MARKETS_PATH = "/markets"
DEFAULT_HISTORY_TEMPLATE = "/markets/{market_id}/history"


@dataclasses.dataclass
class Market:
    id: str
    slug: str
    title: str
    status: str
    close_time: Optional[str]
    raw: Dict[str, Any]


@dataclasses.dataclass
class PriceSample:
    timestamp: float
    price: float


def _log(message: str) -> None:
    sys.stderr.write(message + "\n")


def fetch_json(url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    if params:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{url}?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "polymarket-odds-scraper/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = response.read().decode("utf-8")
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        raise RuntimeError(f"Non-JSON response from {url}: {payload[:200]}")


def normalize_market(item: Dict[str, Any]) -> Market:
    return Market(
        id=str(item.get("id") or item.get("market_id") or item.get("conditionId") or ""),
        slug=str(item.get("slug") or ""),
        title=str(item.get("title") or item.get("question") or ""),
        status=str(item.get("status") or item.get("state") or item.get("resolved") or ""),
        close_time=item.get("closeTime") or item.get("endDate") or item.get("end_date"),
        raw=item,
    )


def iter_markets(
    base_url: str,
    markets_path: str,
    search: str,
    resolved_only: bool,
    page_size: int,
    max_pages: int,
) -> Iterable[Market]:
    page = 0
    next_cursor: Optional[str] = None
    while True:
        params: Dict[str, Any] = {
            "limit": page_size,
            "search": search,
        }
        if resolved_only:
            params["closed"] = True
        if next_cursor:
            params["cursor"] = next_cursor
        url = urllib.parse.urljoin(base_url, markets_path)
        payload = fetch_json(url, params=params)

        data = payload.get("data") if isinstance(payload, dict) else payload
        if not data:
            break
        for item in data:
            market = normalize_market(item)
            if market.id and market.title:
                yield market

        next_cursor = payload.get("nextCursor") if isinstance(payload, dict) else None
        page += 1
        if max_pages and page >= max_pages:
            break
        if not next_cursor:
            break


def parse_timestamp(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not math.isnan(float(value)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            pass
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                return dt.datetime.strptime(value, fmt).replace(tzinfo=dt.timezone.utc).timestamp()
            except ValueError:
                continue
    return None


def extract_samples(payload: Any) -> List[PriceSample]:
    data = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(data, list):
        return []

    samples: List[PriceSample] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        timestamp = parse_timestamp(
            item.get("timestamp")
            or item.get("time")
            or item.get("createdAt")
            or item.get("blockTimestamp")
        )
        price = (
            item.get("price")
            or item.get("probability")
            or item.get("p")
            or item.get("value")
        )
        if timestamp is None or price is None:
            continue
        try:
            price_value = float(price)
        except (TypeError, ValueError):
            continue
        samples.append(PriceSample(timestamp=timestamp, price=price_value))

    samples.sort(key=lambda s: s.timestamp)
    return samples


def resample(samples: List[PriceSample], interval_seconds: int) -> List[PriceSample]:
    if not samples:
        return []
    buckets: Dict[int, PriceSample] = {}
    for sample in samples:
        bucket = int(sample.timestamp // interval_seconds) * interval_seconds
        buckets[bucket] = sample
    resampled = [PriceSample(timestamp=ts, price=buckets[ts].price) for ts in sorted(buckets)]
    return resampled


def write_csv(path: str, samples: List[PriceSample]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "iso_time", "price"])
        for sample in samples:
            iso_time = dt.datetime.fromtimestamp(sample.timestamp, tz=dt.timezone.utc).isoformat()
            writer.writerow([int(sample.timestamp), iso_time, f"{sample.price:.6f}"])


def write_svg(path: str, samples: List[PriceSample], title: str) -> None:
    if not samples:
        return
    width = 960
    height = 320
    padding = 50
    min_ts = samples[0].timestamp
    max_ts = samples[-1].timestamp
    if max_ts == min_ts:
        max_ts += 1

    def x_for(ts: float) -> float:
        return padding + (ts - min_ts) / (max_ts - min_ts) * (width - 2 * padding)

    def y_for(price: float) -> float:
        clamped = max(0.0, min(1.0, price))
        return height - padding - clamped * (height - 2 * padding)

    points = " ".join(f"{x_for(s.timestamp):.2f},{y_for(s.price):.2f}" for s in samples)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(
            "\n".join(
                [
                    f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
                    f'<rect width="100%" height="100%" fill="#ffffff"/>',
                    f'<text x="{padding}" y="24" font-size="16" font-family="Arial">{title}</text>',
                    f'<line x1="{padding}" y1="{height - padding}" x2="{width - padding}" y2="{height - padding}" stroke="#cccccc"/>',
                    f'<line x1="{padding}" y1="{padding}" x2="{padding}" y2="{height - padding}" stroke="#cccccc"/>',
                    f'<polyline fill="none" stroke="#0b5fff" stroke-width="2" points="{points}"/>',
                    f'<text x="{padding}" y="{height - padding + 24}" font-size="12" font-family="Arial">start</text>',
                    f'<text x="{width - padding}" y="{height - padding + 24}" font-size="12" text-anchor="end" font-family="Arial">end</text>',
                    f'<text x="{padding - 8}" y="{padding}" font-size="12" text-anchor="end" font-family="Arial">100%</text>',
                    f'<text x="{padding - 8}" y="{height - padding}" font-size="12" text-anchor="end" font-family="Arial">0%</text>',
                    "</svg>",
                ]
            )
        )


def write_html(path: str, samples: List[PriceSample], title: str) -> None:
    if not samples:
        return
    width = 960
    height = 320
    padding = 50
    min_ts = samples[0].timestamp
    max_ts = samples[-1].timestamp
    if max_ts == min_ts:
        max_ts += 1

    def x_for(ts: float) -> float:
        return padding + (ts - min_ts) / (max_ts - min_ts) * (width - 2 * padding)

    def y_for(price: float) -> float:
        clamped = max(0.0, min(1.0, price))
        return height - padding - clamped * (height - 2 * padding)

    points = [
        [int(s.timestamp), round(s.price, 6), round(x_for(s.timestamp), 2), round(y_for(s.price), 2)]
        for s in samples
    ]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(
            f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{title} win probability</title>
  <style>
    body {{ font-family: Arial, sans-serif; }}
    #chart {{ position: relative; width: {width}px; }}
    #tooltip {{
      position: absolute;
      background: rgba(0,0,0,0.8);
      color: #fff;
      padding: 6px 8px;
      border-radius: 4px;
      font-size: 12px;
      pointer-events: none;
      display: none;
      transform: translate(-50%, -120%);
    }}
  </style>
</head>
<body>
  <h3>{title}</h3>
  <div id="chart">
    <svg id="svg" xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
      <rect width="100%" height="100%" fill="#ffffff"></rect>
      <line x1="{padding}" y1="{height - padding}" x2="{width - padding}" y2="{height - padding}" stroke="#cccccc"></line>
      <line x1="{padding}" y1="{padding}" x2="{padding}" y2="{height - padding}" stroke="#cccccc"></line>
      <polyline id="line" fill="none" stroke="#0b5fff" stroke-width="2"></polyline>
      <circle id="cursor" r="4" fill="#0b5fff"></circle>
    </svg>
    <div id="tooltip"></div>
  </div>
  <script>
    const data = {json.dumps(points)};
    const svg = document.getElementById('svg');
    const line = document.getElementById('line');
    const cursor = document.getElementById('cursor');
    const tooltip = document.getElementById('tooltip');
    line.setAttribute('points', data.map(d => `${{d[2]}},${{d[3]}}`).join(' '));

    function findNearest(x) {{
      let best = data[0];
      let min = Math.abs(x - best[2]);
      for (const d of data) {{
        const dist = Math.abs(x - d[2]);
        if (dist < min) {{
          min = dist;
          best = d;
        }}
      }}
      return best;
    }}

    svg.addEventListener('mousemove', (event) => {{
      const rect = svg.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const nearest = findNearest(x);
      cursor.setAttribute('cx', nearest[2]);
      cursor.setAttribute('cy', nearest[3]);
      tooltip.style.left = `${{nearest[2]}}px`;
      tooltip.style.top = `${{nearest[3]}}px`;
      const date = new Date(nearest[0] * 1000).toISOString();
      tooltip.textContent = `${{date}} | ${{(nearest[1] * 100).toFixed(2)}}%`;
      tooltip.style.display = 'block';
    }});

    svg.addEventListener('mouseleave', () => {{
      tooltip.style.display = 'none';
    }});
  </script>
</body>
</html>
"""
        )


def sanitize_filename(value: str) -> str:
    keep = [c if c.isalnum() or c in ("-", "_") else "-" for c in value.lower()]
    return "".join(keep).strip("-") or "market"


def build_history_url(base_url: str, template: str, market_id: str) -> str:
    path = template.format(market_id=market_id)
    return urllib.parse.urljoin(base_url, path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch completed Lakers games and resample odds history.",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Polymarket API base URL")
    parser.add_argument("--markets-path", default=DEFAULT_MARKETS_PATH, help="Markets endpoint path")
    parser.add_argument(
        "--history-template",
        default=DEFAULT_HISTORY_TEMPLATE,
        help="History endpoint template (use {market_id})",
    )
    parser.add_argument("--search", default="Lakers", help="Search query for markets")
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Resample interval in seconds (default: 10)",
    )
    parser.add_argument("--output-dir", default="output", help="Output directory for CSV files")
    parser.add_argument("--page-size", type=int, default=100, help="Markets page size")
    parser.add_argument("--max-pages", type=int, default=0, help="Max pages to fetch (0=all)")
    parser.add_argument(
        "--resolved-only",
        action="store_true",
        default=True,
        help="Only fetch resolved/closed markets",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.25,
        help="Delay between history requests (seconds)",
    )
    parser.add_argument(
        "--no-svg",
        dest="write_svg",
        action="store_false",
        default=True,
        help="Disable SVG chart output.",
    )
    parser.add_argument(
        "--no-html",
        dest="write_html",
        action="store_false",
        default=True,
        help="Disable HTML chart output with hover tooltips.",
    )
    args = parser.parse_args()

    markets = list(
        iter_markets(
            base_url=args.base_url,
            markets_path=args.markets_path,
            search=args.search,
            resolved_only=args.resolved_only,
            page_size=args.page_size,
            max_pages=args.max_pages,
        )
    )
    if not markets:
        _log("No markets found. Try adjusting --search or endpoint settings.")
        return 1

    _log(f"Found {len(markets)} markets. Fetching history...")
    for market in markets:
        history_url = build_history_url(args.base_url, args.history_template, market.id)
        try:
            history_payload = fetch_json(history_url)
        except Exception as exc:
            _log(f"Failed to fetch history for {market.title} ({market.id}): {exc}")
            continue
        samples = extract_samples(history_payload)
        resampled = resample(samples, args.interval)
        filename = sanitize_filename(f"{market.title}-{market.id}")
        path = os.path.join(args.output_dir, f"{filename}.csv")
        write_csv(path, resampled)
        _log(f"Saved {len(resampled)} samples to {path}")
        if args.write_svg:
            svg_path = os.path.join(args.output_dir, f"{filename}.svg")
            write_svg(svg_path, resampled, market.title)
            _log(f"Saved SVG chart to {svg_path}")
        if args.write_html:
            html_path = os.path.join(args.output_dir, f"{filename}.html")
            write_html(html_path, resampled, market.title)
            _log(f"Saved HTML chart to {html_path}")
        if args.sleep:
            time.sleep(args.sleep)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
