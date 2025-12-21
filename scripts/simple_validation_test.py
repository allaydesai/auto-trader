#!/usr/bin/env python3
"""Simple test to verify FileDataFeed works and delivers bars correctly."""

import asyncio
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, "src")

from auto_trader.data_feed.file_feed import FileDataFeed, PlaybackMode, ColumnMapping
from auto_trader.models.market_data import BarData

bars_received = []

def on_bar(bar: BarData) -> None:
    """Simple callback to collect bars."""
    bars_received.append(bar)
    if len(bars_received) <= 5 or len(bars_received) % 50 == 0:
        print(f"Bar {len(bars_received)}: {bar.timestamp} Close={bar.close_price}")

async def main():
    print("Testing FileDataFeed with AAPL data...")

    # Create column mapping
    mapping = ColumnMapping.for_standard_ohlcv(
        symbol="AAPL",
        bar_size="1min",
        timestamp_column="Date"
    )

    # Create data feed
    feed = FileDataFeed(
        file_path="data/simulation/aapl_2024_01_03.csv",
        playback_mode=PlaybackMode.INSTANT,
        column_mapping=mapping
    )

    # Subscribe
    feed.add_subscriber("test", on_bar)
    await feed.subscribe_symbols(["AAPL"], ["1min"])

    # Start playback
    await feed.start()

    # Report results
    print(f"\nTotal bars received: {len(bars_received)}")
    if bars_received:
        print(f"First bar: {bars_received[0].timestamp} Close=${bars_received[0].close_price}")
        print(f"Last bar: {bars_received[-1].timestamp} Close=${bars_received[-1].close_price}")

        # Check for threshold crossings
        from decimal import Decimal
        threshold = Decimal("183.00")
        below_183 = [b for b in bars_received if b.close_price < threshold]
        print(f"\nBars with close < ${threshold}: {len(below_183)}")
        if below_183:
            print(f"First crossing: {below_183[0].timestamp} Close=${below_183[0].close_price}")

if __name__ == "__main__":
    asyncio.run(main())
