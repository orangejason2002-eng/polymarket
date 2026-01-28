import os

import pytest

from lakers_odds_scraper import DEFAULT_BASE_URL, DEFAULT_STATUS_PATH, fetch_json


requires_live = pytest.mark.skipif(
    os.getenv("KALSHI_LIVE_TESTS") != "1",
    reason="Live Kalshi tests are disabled (set KALSHI_LIVE_TESTS=1).",
)


@pytest.mark.live
@requires_live
def test_markets_endpoint_reachable():
    url = f"{DEFAULT_BASE_URL}{DEFAULT_STATUS_PATH}"
    payload = fetch_json(url)
    assert isinstance(payload, dict)
