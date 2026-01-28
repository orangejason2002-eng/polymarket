import datetime as dt

import pathlib

from lakers_odds_scraper import extract_samples, parse_timestamp, resample, write_html, write_svg


def test_parse_timestamp_handles_iso_zulu():
    value = "2024-01-02T03:04:05Z"
    parsed = parse_timestamp(value)
    expected = dt.datetime(2024, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc).timestamp()
    assert parsed == expected


def test_extract_samples_filters_and_sorts():
    payload = {
        "data": [
            {"timestamp": 10, "price": "0.4"},
            {"timestamp": 5, "price": 0.6},
            {"timestamp": None, "price": 0.2},
        ]
    }
    samples = extract_samples(payload)
    assert [sample.timestamp for sample in samples] == [5.0, 10.0]
    assert [sample.price for sample in samples] == [0.6, 0.4]


def test_resample_buckets_by_interval():
    samples = [
        type("Sample", (), {"timestamp": 0.0, "price": 0.1}),
        type("Sample", (), {"timestamp": 5.0, "price": 0.2}),
        type("Sample", (), {"timestamp": 11.0, "price": 0.3}),
    ]
    resampled = resample(samples, interval_seconds=10)
    assert [sample.timestamp for sample in resampled] == [0, 10]
    assert [sample.price for sample in resampled] == [0.2, 0.3]


def test_write_svg_outputs_file(tmp_path: pathlib.Path):
    samples = [
        type("Sample", (), {"timestamp": 0.0, "price": 0.2}),
        type("Sample", (), {"timestamp": 10.0, "price": 0.8}),
    ]
    svg_path = tmp_path / "chart.svg"
    write_svg(str(svg_path), samples, "Lakers")
    assert svg_path.exists()


def test_write_html_outputs_file(tmp_path: pathlib.Path):
    samples = [
        type("Sample", (), {"timestamp": 0.0, "price": 0.2}),
        type("Sample", (), {"timestamp": 10.0, "price": 0.8}),
    ]
    html_path = tmp_path / "chart.html"
    write_html(str(html_path), samples, "Lakers")
    assert html_path.exists()
