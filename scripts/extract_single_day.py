#!/usr/bin/env python3
"""Extract a single trading day from large AAPL historical CSV.

This script efficiently extracts one day of 1-minute AAPL data from the
large historical dataset without loading the entire file into memory.

Usage:
    python scripts/extract_single_day.py --date 2024-01-03
    python scripts/extract_single_day.py --date 2024-01-03 --output custom.csv
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from loguru import logger


def validate_date(date_str: str) -> datetime:
    """Validate and parse date string.

    Args:
        date_str: Date in YYYY-MM-DD format.

    Returns:
        Parsed datetime object.

    Raises:
        ValueError: If date format is invalid.
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(
            f"Invalid date format '{date_str}'. Expected YYYY-MM-DD"
        ) from e


def extract_trading_day(
    source_file: Path,
    target_file: Path,
    date_str: str,
) -> int:
    """Extract a single trading day from large CSV using grep.

    Args:
        source_file: Path to large AAPL CSV file.
        target_file: Path to output CSV file.
        date_str: Date to extract (YYYY-MM-DD format).

    Returns:
        Number of bars extracted.

    Raises:
        FileNotFoundError: If source file doesn't exist.
        subprocess.CalledProcessError: If grep command fails.
    """
    if not source_file.exists():
        raise FileNotFoundError(f"Source file not found: {source_file}")

    logger.info(f"Extracting {date_str} from {source_file}")

    # Ensure output directory exists
    target_file.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: Extract header
    logger.debug("Extracting CSV header...")
    header_result = subprocess.run(
        ["head", "-1", str(source_file)],
        capture_output=True,
        text=True,
        check=True,
    )
    header = header_result.stdout

    # Step 2: Extract all lines matching the date
    # Pattern matches: "YYYY-MM-DD HH:MM:SS"
    logger.debug(f"Extracting bars for {date_str}...")
    grep_pattern = f"^{date_str}"

    grep_result = subprocess.run(
        ["grep", grep_pattern, str(source_file)],
        capture_output=True,
        text=True,
    )

    # grep returns 1 if no matches found (not an error)
    if grep_result.returncode not in (0, 1):
        raise subprocess.CalledProcessError(
            grep_result.returncode, grep_result.args, grep_result.stderr
        )

    bars = grep_result.stdout

    if not bars:
        logger.warning(f"No data found for {date_str}")
        return 0

    # Step 3: Filter to market hours only (09:30 - 16:00)
    logger.debug("Filtering to market hours (09:30 - 16:00)...")
    market_hours_bars = []

    for line in bars.splitlines():
        # Extract time portion from timestamp
        # Format: "2024-01-03 09:30:00,..."
        try:
            timestamp_str = line.split(",")[0]
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            hour = dt.hour
            minute = dt.minute

            # Market hours: 09:30 - 16:00
            if (hour == 9 and minute >= 30) or (10 <= hour <= 15):
                market_hours_bars.append(line)
            elif hour == 16 and minute == 0:
                market_hours_bars.append(line)

        except (ValueError, IndexError) as e:
            logger.warning(f"Skipping malformed line: {line[:50]}... ({e})")
            continue

    bar_count = len(market_hours_bars)
    logger.info(f"Extracted {bar_count} bars for {date_str}")

    # Step 4: Write to output file
    logger.debug(f"Writing to {target_file}...")
    with open(target_file, "w") as f:
        f.write(header)
        for bar_line in market_hours_bars:
            f.write(bar_line + "\n")

    logger.success(
        f"Successfully extracted {bar_count} bars to {target_file}"
    )

    return bar_count


def analyze_extracted_data(csv_file: Path) -> None:
    """Analyze extracted CSV and print statistics.

    Args:
        csv_file: Path to extracted CSV file.
    """
    if not csv_file.exists():
        logger.error(f"File not found: {csv_file}")
        return

    logger.info(f"Analyzing {csv_file}...")

    with open(csv_file, "r") as f:
        lines = f.readlines()

    if len(lines) < 2:
        logger.warning("File is empty or has only header")
        return

    header = lines[0].strip()
    data_lines = lines[1:]

    # Extract first and last bar info
    first_bar = data_lines[0].split(",")
    last_bar = data_lines[-1].split(",")

    first_timestamp = first_bar[0]
    last_timestamp = last_bar[0]
    first_close = float(first_bar[4])
    last_close = float(last_bar[4])

    # Calculate price range
    closes = [float(line.split(",")[4]) for line in data_lines]
    min_close = min(closes)
    max_close = max(closes)

    print("\n" + "=" * 60)
    print("EXTRACTED DATA ANALYSIS")
    print("=" * 60)
    print(f"File: {csv_file}")
    print(f"Total Bars: {len(data_lines)}")
    print(f"First Bar: {first_timestamp}")
    print(f"Last Bar: {last_timestamp}")
    print(f"\nPrice Statistics:")
    print(f"  Open (first bar): ${first_close:.2f}")
    print(f"  Close (last bar): ${last_close:.2f}")
    print(f"  Intraday Low: ${min_close:.2f}")
    print(f"  Intraday High: ${max_close:.2f}")
    print(f"  Range: ${max_close - min_close:.2f}")
    print("=" * 60 + "\n")


def main() -> int:
    """Main entry point for script.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Extract single trading day from AAPL historical data"
    )
    parser.add_argument(
        "--date",
        type=str,
        required=True,
        help="Date to extract (YYYY-MM-DD format)",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/aapl_1min_data From 2006 -2024.csv"),
        help="Path to source CSV file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to output CSV file (default: data/simulation/aapl_YYYY_MM_DD.csv)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    logger.remove()
    log_level = "DEBUG" if args.verbose else "INFO"
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    )

    # Validate date
    try:
        date_obj = validate_date(args.date)
    except ValueError as e:
        logger.error(str(e))
        return 1

    # Determine output path
    if args.output is None:
        date_formatted = date_obj.strftime("%Y_%m_%d")
        args.output = Path(f"data/simulation/aapl_{date_formatted}.csv")

    # Extract data
    try:
        bar_count = extract_trading_day(
            source_file=args.source,
            target_file=args.output,
            date_str=args.date,
        )

        if bar_count == 0:
            logger.error(
                f"No data extracted for {args.date}. "
                "Check that the date exists in the source file."
            )
            return 1

        # Analyze extracted data
        analyze_extracted_data(args.output)

        logger.success("Extraction complete!")
        return 0

    except FileNotFoundError as e:
        logger.error(str(e))
        return 1
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
