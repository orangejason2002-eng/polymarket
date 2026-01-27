import os

import pytest

from lakers_odds_scraper import DEFAULT_BASE_URL, DEFAULT_MARKETS_PATH, fetch_json


requires_live = pytest.mark.skipif(
    os.getenv("POLYMARKET_LIVE_TESTS") != "1",
    reason="Live Polymarket tests are disabled (set POLYMARKET_LIVE_TESTS=1).",
)


@pytest.mark.live
@requires_live
def test_markets_endpoint_reachable():
    url = f"{DEFAULT_BASE_URL}{DEFAULT_MARKETS_PATH}"
    payload = fetch_json(url, params={"limit": 1})
    assert isinstance(payload, dict)
