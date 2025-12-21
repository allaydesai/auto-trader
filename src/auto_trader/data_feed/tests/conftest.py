"""Shared pytest fixtures for data feed tests."""

import pytest
import yaml
import json


@pytest.fixture
def sample_csv_file(tmp_path):
    """Create a sample CSV file with standard format."""
    csv_file = tmp_path / "sample.csv"
    content = """timestamp,symbol,open,high,low,close,volume,bar_size
2025-01-01T09:30:00+00:00,AAPL,180.50,181.00,180.00,180.75,1000000,5min
2025-01-01T09:35:00+00:00,AAPL,180.75,181.25,180.50,181.00,1100000,5min
2025-01-01T09:40:00+00:00,AAPL,181.00,181.50,180.75,181.25,1200000,5min
2025-01-01T09:30:00+00:00,TSLA,250.00,251.00,249.50,250.50,500000,5min
2025-01-01T09:35:00+00:00,TSLA,250.50,251.50,250.00,251.00,550000,5min
"""
    csv_file.write_text(content)
    return csv_file


@pytest.fixture
def multi_symbol_csv_file(tmp_path):
    """Create CSV file with multiple symbols and bar sizes."""
    csv_file = tmp_path / "multi_symbol.csv"
    content = """timestamp,symbol,open,high,low,close,volume,bar_size
2025-01-01T09:30:00+00:00,AAPL,180.50,181.00,180.00,180.75,1000000,5min
2025-01-01T09:45:00+00:00,AAPL,180.75,181.25,180.50,181.00,1100000,15min
2025-01-01T09:30:00+00:00,TSLA,250.00,251.00,249.50,250.50,500000,5min
2025-01-01T09:45:00+00:00,TSLA,250.50,251.50,250.00,251.00,550000,15min
"""
    csv_file.write_text(content)
    return csv_file


@pytest.fixture
def sample_yaml_file(tmp_path):
    """Create a sample YAML file."""
    yaml_file = tmp_path / "sample.yaml"
    data = {
        "bars": [
            {
                "timestamp": "2025-01-01T09:30:00+00:00",
                "symbol": "AAPL",
                "open": "180.50",
                "high": "181.00",
                "low": "180.00",
                "close": "180.75",
                "volume": 1000000,
                "bar_size": "5min",
            },
            {
                "timestamp": "2025-01-01T09:35:00+00:00",
                "symbol": "AAPL",
                "open": "180.75",
                "high": "181.25",
                "low": "180.50",
                "close": "181.00",
                "volume": 1100000,
                "bar_size": "5min",
            },
        ]
    }
    with open(yaml_file, "w") as f:
        yaml.dump(data, f)
    return yaml_file


@pytest.fixture
def sample_json_file(tmp_path):
    """Create a sample JSON file."""
    json_file = tmp_path / "sample.json"
    data = {
        "bars": [
            {
                "timestamp": "2025-01-01T09:30:00+00:00",
                "symbol": "AAPL",
                "open": "180.50",
                "high": "181.00",
                "low": "180.00",
                "close": "180.75",
                "volume": 1000000,
                "bar_size": "5min",
            },
            {
                "timestamp": "2025-01-01T09:35:00+00:00",
                "symbol": "AAPL",
                "open": "180.75",
                "high": "181.25",
                "low": "180.50",
                "close": "181.00",
                "volume": 1100000,
                "bar_size": "5min",
            },
        ]
    }
    with open(json_file, "w") as f:
        json.dump(data, f)
    return json_file


@pytest.fixture
def yahoo_finance_csv_file(tmp_path):
    """Create CSV file in Yahoo Finance format."""
    csv_file = tmp_path / "yahoo_finance.csv"
    content = """Date,Open,High,Low,Close,Volume
2006-01-03 00:00:00,39.69,40.15,38.64,39.76,807234400.0
2006-01-04 00:00:00,39.76,40.43,39.69,40.31,733039200.0
2006-01-05 00:00:00,40.25,40.90,40.12,40.68,638887200.0
"""
    csv_file.write_text(content)
    return csv_file


@pytest.fixture
def unsorted_csv_file(tmp_path):
    """Create CSV file with unsorted timestamps."""
    csv_file = tmp_path / "unsorted.csv"
    content = """timestamp,symbol,open,high,low,close,volume,bar_size
2025-01-01T09:40:00+00:00,AAPL,181.00,181.50,180.75,181.25,1200000,5min
2025-01-01T09:30:00+00:00,AAPL,180.50,181.00,180.00,180.75,1000000,5min
2025-01-01T09:35:00+00:00,AAPL,180.75,181.25,180.50,181.00,1100000,5min
"""
    csv_file.write_text(content)
    return csv_file


@pytest.fixture
def missing_timestamp_csv_file(tmp_path):
    """Create CSV file with missing timestamp column."""
    csv_file = tmp_path / "missing_timestamp.csv"
    content = """symbol,open,high,low,close,volume,bar_size
AAPL,180.50,181.00,180.00,180.75,1000000,5min
"""
    csv_file.write_text(content)
    return csv_file


@pytest.fixture
def missing_symbol_csv_file(tmp_path):
    """Create CSV file with missing symbol column."""
    csv_file = tmp_path / "missing_symbol.csv"
    content = """timestamp,open,high,low,close,volume,bar_size
2025-01-01T09:30:00+00:00,180.50,181.00,180.00,180.75,1000000,5min
"""
    csv_file.write_text(content)
    return csv_file


@pytest.fixture
def missing_ohlc_csv_file(tmp_path):
    """Create CSV file with missing OHLC columns."""
    csv_file = tmp_path / "missing_ohlc.csv"
    content = """timestamp,symbol,volume,bar_size
2025-01-01T09:30:00+00:00,AAPL,1000000,5min
"""
    csv_file.write_text(content)
    return csv_file


@pytest.fixture
def case_insensitive_csv_file(tmp_path):
    """Create CSV file with mixed case column names."""
    csv_file = tmp_path / "case_insensitive.csv"
    content = """date,OPEN,High,low,CLOSE,VoLuMe
2006-01-03 00:00:00,39.69,40.15,38.64,39.76,807234400.0
2006-01-04 00:00:00,39.76,40.43,39.69,40.31,733039200.0
"""
    csv_file.write_text(content)
    return csv_file
