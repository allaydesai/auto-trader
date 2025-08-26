========================
CODE SNIPPETS
========================
TITLE: Install All ib_async Development and Documentation Dependencies with Poetry
DESCRIPTION: This command installs all dependencies for the `ib_async` project, including those specifically for documentation generation and development testing. It's intended for contributors and developers who need a full development environment.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_3

LANGUAGE: Python
CODE:
```
poetry install --with=docs,dev
```

----------------------------------------

TITLE: Import ib_async and Start Event Loop
DESCRIPTION: Shows the standard setup for `ib_async` in Jupyter notebooks, importing all functionalities and starting the event loop to keep the notebook live updated. Note that `util.startLoop()` is specifically designed for notebook environments.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/basics.ipynb#_snippet_1

LANGUAGE: python
CODE:
```
from ib_async import *

util.startLoop()
```

----------------------------------------

TITLE: Install Documentation Generation Dependencies with Poetry
DESCRIPTION: This command installs the specific dependencies required to build the `ib_async` project's documentation. It's a necessary step before attempting to generate the HTML documentation files.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_4

LANGUAGE: Python
CODE:
```
poetry install --with=docs
```

----------------------------------------

TITLE: Install ib_async Python Library via pip
DESCRIPTION: This command installs the `ib_async` library and its core dependencies using pip, the standard Python package installer. It's the recommended and simplest way to get the library set up for use in a Python environment.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_0

LANGUAGE: Python
CODE:
```
pip install ib_async
```

----------------------------------------

TITLE: Install ib_async Development Dependencies with Poetry
DESCRIPTION: This command uses `poetry` to install all necessary development and documentation-related dependencies for the `ib_async` project, preparing the environment for local contributions.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_35

LANGUAGE: bash
CODE:
```
poetry install --with=dev,docs
```

----------------------------------------

TITLE: Quick Start: Basic ib_async Connection and Disconnection
DESCRIPTION: A simple example demonstrating how to establish a connection to Interactive Brokers TWS or Gateway using `ib_async` and then disconnect. It prints a confirmation message upon successful connection.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_17

LANGUAGE: python
CODE:
```
from ib_async import *

# Connect to TWS or IB Gateway
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)
print("Connected")

# Disconnect when done
ib.disconnect()
```

----------------------------------------

TITLE: Install ib_async Library Dependencies with Poetry
DESCRIPTION: This command uses Poetry to install only the production dependencies required for the `ib_async` library. It's suitable for users who intend to use the library without needing development or documentation tools.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_2

LANGUAGE: Python
CODE:
```
poetry install
```

----------------------------------------

TITLE: Initialize IB Connection and Utilities
DESCRIPTION: Establishes a connection to the Interactive Brokers TWS/Gateway. It imports necessary modules from `ib_async`, starts the event loop, and connects to the specified host and port with a client ID. A warning about live orders is noted, recommending a paper trading account.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/ordering.ipynb#_snippet_0

LANGUAGE: python
CODE:
```
from ib_async import *

util.startLoop()

ib = IB()
ib.connect("127.0.0.1", 7497, clientId=13)
```

----------------------------------------

TITLE: Install Poetry for Python Project Management
DESCRIPTION: This command installs Poetry, a dependency management and packaging tool for Python, and updates it to the latest version. Poetry is a prerequisite for manually building, developing, or contributing to the `ib_async` project.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_1

LANGUAGE: Python
CODE:
```
pip install poetry -U
```

----------------------------------------

TITLE: Initialize IB_async Connection
DESCRIPTION: Sets up the `ib_async` library, starts the event loop, and establishes a connection to the TWS or IB Gateway. This is the prerequisite for all subsequent API calls.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/contract_details.ipynb#_snippet_0

LANGUAGE: python
CODE:
```
from ib_async import *

util.startLoop()

import logging
# util.logToConsole(logging.DEBUG)

ib = IB()
ib.connect("127.0.0.1", 7497, clientId=11)
```

----------------------------------------

TITLE: Build ib_async HTML Documentation with Sphinx
DESCRIPTION: This command executes Sphinx, a documentation generator, to build the HTML documentation for the `ib_async` project. It requires the documentation dependencies to be installed first using Poetry.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_5

LANGUAGE: Python
CODE:
```
poetry run sphinx-build -b html docs html
```

----------------------------------------

TITLE: Run ib_async Tests with Poetry
DESCRIPTION: This snippet provides the shell commands to set up the development environment and run tests for the `ib_async` project. It uses `poetry` to install development dependencies and execute the `pytest` test suite.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_31

LANGUAGE: bash
CODE:
```
poetry install --with=dev
poetry run pytest
```

----------------------------------------

TITLE: ib_async Connection Pattern for Jupyter Notebooks
DESCRIPTION: Illustrates the specific setup required for using `ib_async` within a Jupyter Notebook environment. It highlights the necessity of `util.startLoop()` to integrate with the notebook's event loop.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_15

LANGUAGE: python
CODE:
```
from ib_async import *
util.startLoop()  # Required for notebooks

ib = IB()
ib.connect('172.0.0.1', 7497, clientId=1)
# Your code here - no need to call ib.run()
```

----------------------------------------

TITLE: Connect to Interactive Brokers API
DESCRIPTION: Establishes a connection to the Interactive Brokers TWS or Gateway. It initializes the `ib_async` library, starts the event loop, and connects to the specified IP address and port with a client ID.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/bar_data.ipynb#_snippet_0

LANGUAGE: python
CODE:
```
from ib_async import *

util.startLoop()

ib = IB()
ib.connect("127.0.0.1", 7497, clientId=14)
```

----------------------------------------

TITLE: Retrieve News Articles with ib_async
DESCRIPTION: Demonstrates how to get available news providers, qualify a stock contract (AMD), request historical news headlines, and then fetch the full content of the latest news article.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/docs/recipes.rst#_snippet_6

LANGUAGE: python
CODE:
```
newsProviders = ib.reqNewsProviders()
print(newsProviders)
codes = '+'.join(np.code for np in newsProviders)

amd = Stock('AMD', 'SMART', 'USD')
ib.qualifyContracts(amd)
headlines = ib.reqHistoricalNews(amd.conId, codes, '', '', 10)
latest = headlines[0]
print(latest)
article = ib.reqNewsArticle(latest.providerCode, latest.articleId)
print(article)
```

----------------------------------------

TITLE: Handle ib_async Events for Order and Ticker Updates
DESCRIPTION: This example demonstrates how to subscribe to and handle events in `ib_async`. It shows how to register a synchronous callback for order status updates and an asynchronous callback for real-time ticker updates, enabling reactive programming based on API events.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_29

LANGUAGE: python
CODE:
```
# Subscribe to events
def onOrderUpdate(trade):
    print(f"Order update: {trade.orderStatus.status}")

ib.orderStatusEvent += onOrderUpdate

# Or with async
async def onTicker(ticker):
    print(f"Price update: {ticker.last}")

ticker.updateEvent += onTicker
```

----------------------------------------

TITLE: Request IB API Market Data Types
DESCRIPTION: Shows how to request different types of market data from Interactive Brokers. Includes examples for free delayed data (types 3 and 4) and real-time data (type 1), noting subscription requirements for real-time data.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_13

LANGUAGE: python
CODE:
```
# For free delayed data (no subscription required)
ib.reqMarketDataType(3)  # Delayed
ib.reqMarketDataType(4)  # Delayed frozen

# For real-time data (requires subscription)
ib.reqMarketDataType(1)  # Real-time
```

----------------------------------------

TITLE: Define Various Financial Contracts
DESCRIPTION: Provides multiple examples of how to define different types of financial instruments (e.g., Stock, Forex, Future, Option, Bond) using `ib_async`'s specialized contract classes, specifying key attributes like ticker, exchange, currency, expiry, and strike.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/basics.ipynb#_snippet_5

LANGUAGE: python
CODE:
```
Contract(conId=270639)
Stock("AMD", "SMART", "USD")
Stock("INTC", "SMART", "USD", primaryExchange="NASDAQ")
Forex("EURUSD")
CFD("IBUS30")
Future("ES", "20180921", "GLOBEX")
Option("SPY", "20170721", 240, "C", "SMART")
Bond(secIdType="ISIN", secId="US03076KAA60");
```

----------------------------------------

TITLE: Retrieve and Analyze Historical Data with ib_async and Pandas
DESCRIPTION: This example shows how to connect to the Interactive Brokers API using `ib_async`, request historical data for a stock (SPY) at different timeframes (daily and 5-minute bars), convert the data into Pandas DataFrames, and perform a simple moving average calculation. It highlights the integration of `ib_async` with data analysis libraries.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_26

LANGUAGE: python
CODE:
```
from ib_async import *
import pandas as pd

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

# Get multiple timeframes
contract = Stock('SPY', 'SMART', 'USD')

# Daily bars for 1 year
daily_bars = ib.reqHistoricalData(
    contract, endDateTime='', durationStr='1 Y',
    barSizeSetting='1 day', whatToShow='TRADES', useRTH=True)

# 5-minute bars for last 5 days
intraday_bars = ib.reqHistoricalData(
    contract, endDateTime='', durationStr='5 D',
    barSizeSetting='5 mins', whatToShow='TRADES', useRTH=True)

# Convert to DataFrames
daily_df = util.df(daily_bars)
intraday_df = util.df(intraday_bars)

print(f"Daily bars: {len(daily_df)} rows")
print(f"Intraday bars: {len(intraday_df)} rows")

# Calculate simple moving average
daily_df['SMA_20'] = daily_df['close'].rolling(20).mean()
print(daily_df[['date', 'close', 'SMA_20']].tail())

ib.disconnect()
```

----------------------------------------

TITLE: Contract-from-params Abstraction (ib_async API)
DESCRIPTION: Centralizes logic for converting generic `Contract` objects to specific subclass types. For example, a `Contract` object with `secType='OPT'` can now be automatically converted to an `Option` object, simplifying contract handling.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/docs/changelog.rst#_snippet_6

LANGUAGE: APIDOC
CODE:
```
Contract:
  (Internal abstraction for converting generic Contract to specific types like Option, Stock, etc. based on secType)
  # Example: Contract(secType="OPT") -> Option()
```

----------------------------------------

TITLE: Utilize WSH Event Calendar with ib_async
DESCRIPTION: Explains how to connect to IB, get the contract ID for a stock (IBM), retrieve WSH metadata for available filters and event types, and then query specific corporate event data (Earnings Dates, Board of Directors meetings) using a WshEventData filter.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/docs/recipes.rst#_snippet_8

LANGUAGE: python
CODE:
```
from ib_async import *

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

# Get the conId of an instrument (IBM in this case):
ibm = Stock('IBM', 'SMART', 'USD')
ib.qualifyContracts(ibm)
print(ibm.conId)  # is 8314

# Get the list of available filters and event types:
meta = ib.getWshMetaData()
print(meta)

# For IBM (with conId=8314) query the:
#   - Earnings Dates (wshe_ed)
#   - Board of Directors meetings (wshe_bod)
data = WshEventData(
    filter = '''{
      "country": "All",
      "watchlist": ["8314"],
      "limit_region": 10,
      "limit": 10,
      "wshe_ed": "true",
      "wshe_bod": "true"
    }''')
events = ib.getWshEventData(data)
print(events)
```

----------------------------------------

TITLE: Fetch Historical Tick Data with ib_async
DESCRIPTION: Retrieves historical tick data for a specified contract within a given time range. This method allows fetching up to 1000 ticks at a time, requiring either a start time or an end time to be provided.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/tick_data.ipynb#_snippet_8

LANGUAGE: python
CODE:
```
import datetime

start = ""
end = datetime.datetime.now()
ticks = ib.reqHistoricalTicks(eurusd, start, end, 1000, "BID_ASK", useRth=False)

ticks[-1]
```

----------------------------------------

TITLE: Request Earliest Available Bar Data Timestamp
DESCRIPTION: Retrieves the earliest available historical data timestamp for a given contract. This is useful for determining the start of available data for a specific instrument and data type, such as 'TRADES'.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/bar_data.ipynb#_snippet_1

LANGUAGE: python
CODE:
```
contract = Stock("TSLA", "SMART", "USD")

ib.reqHeadTimeStamp(contract, whatToShow="TRADES", useRTH=True)
```

----------------------------------------

TITLE: Request and Cancel Tick-by-Tick Bid/Ask Data
DESCRIPTION: Requests highly granular tick-by-tick data for a specific contract and data type, such as 'BidAsk'. This functionality provides every individual tick as it occurs, mirroring the TWS Time & Sales window. The example also demonstrates how to cancel the tick-by-tick subscription.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/tick_data.ipynb#_snippet_7

LANGUAGE: python
CODE:
```
ticker = ib.reqTickByTickData(eurusd, "BidAsk")
ib.sleep(2)
print(ticker)

ib.cancelTickByTickData(ticker.contract, "BidAsk")
```

----------------------------------------

TITLE: Place a Simple Market Order with ib_async
DESCRIPTION: Illustrates how to place a basic market order (e.g., BUY 100 shares of AAPL) using `ib_async`. It shows the creation of a contract and an order object, placing the order, and then monitoring its status until completion.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_21

LANGUAGE: python
CODE:
```
from ib_async import *

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

# Create a contract and order
contract = Stock('AAPL', 'SMART', 'USD')
order = MarketOrder('BUY', 100)

# Place the order
trade = ib.placeOrder(contract, order)
print(f"Order placed: {trade}")

# Monitor order status
while not trade.isDone():
    ib.sleep(1)
    print(f"Order status: {trade.orderStatus.status}")

ib.disconnect()
```

----------------------------------------

TITLE: Inspect ib_async Package Contents
DESCRIPTION: Demonstrates how to import the `ib_async` library and print its `__all__` attribute to see the top-level modules and functions exposed by the package.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/basics.ipynb#_snippet_0

LANGUAGE: python
CODE:
```
import ib_async

print(ib_async.__all__)
```

----------------------------------------

TITLE: Connect to Interactive Brokers TWS/IBG
DESCRIPTION: Illustrates how to create an `IB` instance and establish a connection to a running TWS or IB Gateway application. It specifies the local IP address, default port, and a unique client ID for the connection.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/basics.ipynb#_snippet_2

LANGUAGE: python
CODE:
```
ib = IB()
ib.connect("127.0.0.1", 7497, clientId=10)
```

----------------------------------------

TITLE: Clone ib_async Repository for Local Development
DESCRIPTION: This snippet provides the Git commands to clone the `ib_async` repository from GitHub and navigate into its directory, which is the first step for local development.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_34

LANGUAGE: bash
CODE:
```
git clone https://github.com/ib-api-reloaded/ib_async.git
cd ib_async
```

----------------------------------------

TITLE: Publish ib_async Package to PyPI with Poetry
DESCRIPTION: This command builds and publishes the `ib_async` package to PyPI. It requires the PyPI token to be configured beforehand and the package to be built, streamlining the release process for maintainers.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_9

LANGUAGE: Python
CODE:
```
poetry publish --build
```

----------------------------------------

TITLE: Build ib_async Distribution Package with Poetry
DESCRIPTION: This command uses Poetry to build the distributable package for `ib_async`. This process typically generates source distributions and wheel files, preparing the library for publication or distribution.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_7

LANGUAGE: Python
CODE:
```
poetry build
```

----------------------------------------

TITLE: Configure Interactive Brokers Gateway/TWS API Access
DESCRIPTION: This section details the critical steps for setting up and configuring API access within Interactive Brokers' Trader Workstation (TWS) or IB Gateway. Proper configuration is essential for `ib_async` to establish a connection and interact with the trading platform.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_10

LANGUAGE: APIDOC
CODE:
```
API Configuration Steps:
  1. Enable API:
    - Path: Configure -> API -> Settings
    - Action: Check "Enable ActiveX and Socket Clients"
  2. Set Port:
    - Default TWS Port: 7497
    - Default Gateway Port: 4001
    - Note: Can be changed if needed.
  3. Allow Connections:
    - Path: Trusted IPs
    - Action: Add `127.0.0.1` for local connections.
  4. Download Orders:
    - Action: Check "Download open orders on connection" to see existing orders.

Performance Settings:
  1. Memory Allocation:
    - Path: Configure -> Settings -> Memory Allocation
    - Action: Set minimum 4096 MB to prevent crashes with bulk data.
  2. Timeouts:
    - Action: Increase API timeout settings if experiencing disconnections during large data requests.
```

----------------------------------------

TITLE: Connect to Interactive Brokers TWS/Gateway
DESCRIPTION: Establishes a connection to the Interactive Brokers TWS or Gateway, initializes the event loop, and sets up the IB client for subsequent API calls.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/option_chain.ipynb#_snippet_0

LANGUAGE: python
CODE:
```
from ib_async import *

util.startLoop()

ib = IB()
ib.connect("127.0.0.1", 7497, clientId=12)
```

----------------------------------------

TITLE: Place Bracket Order with ib_async
DESCRIPTION: This snippet demonstrates how to place a bracket order using the `ib_async` library. It involves placing a parent order, a stop-loss order, and a take-profit order, then printing the number of orders placed before disconnecting from the IB API.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_25

LANGUAGE: python
CODE:
```
trades = []
trades.append(ib.placeOrder(contract, parent))
trades.append(ib.placeOrder(contract, stopLoss))
trades.append(ib.placeOrder(contract, takeProfit))

print(f"Bracket order placed: {len(trades)} orders")
ib.disconnect()
```

----------------------------------------

TITLE: Initialize and Connect to Interactive Brokers API
DESCRIPTION: Establishes a connection to the Interactive Brokers TWS (Trader Workstation) or Gateway using the `ib_async` library. This is the prerequisite step for all subsequent API interactions.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/scanners.ipynb#_snippet_0

LANGUAGE: python
CODE:
```
from ib_async import *

util.startLoop()

ib = IB()
ib.connect("127.0.0.1", 7497, clientId=17)
```

----------------------------------------

TITLE: Configure PyPI API Token for Poetry Package Upload
DESCRIPTION: This command configures Poetry with a PyPI API token, which is essential for authenticating when uploading packages to the Python Package Index. Replace 'your-api-token' with the actual token obtained from PyPI.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_8

LANGUAGE: Python
CODE:
```
poetry config pypi-token.pypi your-api-token
```

----------------------------------------

TITLE: Filter Account Values for Net Liquidation
DESCRIPTION: Shows how to retrieve all account values via `ib.accountValues()` and then filter them using a list comprehension to specifically extract the 'NetLiquidationByCurrency' for the base currency.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/basics.ipynb#_snippet_4

LANGUAGE: python
CODE:
```
[
    v
    for v in ib.accountValues()
    if v.tag == "NetLiquidationByCurrency" and v.currency == "BASE"
]
```

----------------------------------------

TITLE: Place Market Order and Wait for Completion
DESCRIPTION: Demonstrates how to make order placement blocking by waiting until the order is either filled or canceled. It places a MarketOrder for 100 units and then enters a loop that continuously calls `ib.waitOnUpdate()` until the trade is marked as done (`trade.isDone()`), ensuring the script waits for the order's final state.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/ordering.ipynb#_snippet_7

LANGUAGE: python
CODE:
```
%%time
order = MarketOrder("BUY", 100)

trade = ib.placeOrder(contract, order)
while not trade.isDone():
    ib.waitOnUpdate()
```

----------------------------------------

TITLE: Connect to Interactive Brokers TWS/Gateway
DESCRIPTION: Establishes a connection to the Interactive Brokers TWS or Gateway using the `ib_async` library. It initializes the event loop, creates an `IB` instance, and connects to the specified IP address, port, and client ID.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/market_depth.ipynb#_snippet_0

LANGUAGE: python
CODE:
```
from ib_async import *

util.startLoop()

ib = IB()
ib.connect("127.0.0.1", 7497, clientId=16)
```

----------------------------------------

TITLE: Compare Current State vs. Request Performance for Positions
DESCRIPTION: Demonstrates the performance difference between retrieving current positions using the immediately available `ib.positions()` (current state) and the blocking `ib.reqPositions()` (request). The `%time` magic command is used to measure execution time in a Jupyter environment, highlighting the efficiency of current state methods.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/basics.ipynb#_snippet_7

LANGUAGE: python
CODE:
```
%time l = ib.positions()
```

LANGUAGE: python
CODE:
```
%time l = ib.reqPositions()
```

----------------------------------------

TITLE: Request Contract Details for a Stock
DESCRIPTION: Illustrates the process of defining a stock contract and then using the `ib.reqContractDetails()` method to send a request to TWS/IBG to fetch detailed information about that specific contract.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/basics.ipynb#_snippet_6

LANGUAGE: python
CODE:
```
contract = Stock("TSLA", "SMART", "USD")
ib.reqContractDetails(contract)
```

----------------------------------------

TITLE: Define Forex Contract and Limit Order
DESCRIPTION: Creates a Forex contract for EURUSD and qualifies it with the IB connection to ensure it's a valid contract. It then defines a LimitOrder to SELL 20,000 units at a specific price of 1.11, preparing it for submission.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/ordering.ipynb#_snippet_1

LANGUAGE: python
CODE:
```
contract = Forex("EURUSD")
ib.qualifyContracts(contract)

order = LimitOrder("SELL", 20000, 1.11)
```

----------------------------------------

TITLE: ib_async Asynchronous Application Connection
DESCRIPTION: Shows how to integrate `ib_async` into an asynchronous Python application using `asyncio`. It demonstrates connecting with `connectAsync` and running the main asynchronous function.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_16

LANGUAGE: python
CODE:
```
import asyncio
from ib_async import *

async def main():
    ib = IB()
    await ib.connectAsync('127.0.0.1', 7497, clientId=1)
    # Your async code here
    ib.disconnect()

asyncio.run(main())
```

----------------------------------------

TITLE: ib_async Version 0.9.51 Compatibility and Disconnect Handling
DESCRIPTION: This version improves compatibility for `ib.placeOrder` with older TWS/gateway versions and enhances handling of unclean disconnects.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/docs/changelog.rst#_snippet_53

LANGUAGE: APIDOC
CODE:
```
ib.placeOrder:
  - Fixed for older TWS/gateway versions.
Connection Handling:
  - Better handling of unclean disconnects.
```

----------------------------------------

TITLE: Place Limit Order with Unrealistic Price
DESCRIPTION: Demonstrates placing a LimitOrder with an intentionally unrealistic limit price (0.05) to observe its behavior when it's unlikely to be filled immediately. The `limitTrade` object returned by `placeOrder` is then displayed, showing its initial state.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/ordering.ipynb#_snippet_4

LANGUAGE: python
CODE:
```
limitOrder = LimitOrder("BUY", 20000, 0.05)
limitTrade = ib.placeOrder(contract, limitOrder)

limitTrade
```

----------------------------------------

TITLE: Run Tests and Type Checks During ib_async Local Development
DESCRIPTION: This snippet combines commands to run the test suite and perform type checking on the `ib_async` project. These steps are crucial for verifying changes during local development before submitting a pull request.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_36

LANGUAGE: bash
CODE:
```
poetry run pytest
poetry run mypy ib_async
```

----------------------------------------

TITLE: Connect to Interactive Brokers with ib_async
DESCRIPTION: Initializes the ib_async event loop, creates an IB object, and establishes a connection to the Interactive Brokers TWS/Gateway. Ensure that the TWS/Gateway application is running and accessible at the specified IP address and port before executing this code.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/tick_data.ipynb#_snippet_0

LANGUAGE: python
CODE:
```
from ib_async import *

util.startLoop()

ib = IB()
ib.connect("127.0.0.1", 7497, clientId=15)
```

----------------------------------------

TITLE: Enable INFO Level Logging to Console
DESCRIPTION: Configures `ib_async` to output log messages of INFO level and higher directly to the console, providing basic operational insights into the library's activities.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/basics.ipynb#_snippet_8

LANGUAGE: python
CODE:
```
util.logToConsole()
```

----------------------------------------

TITLE: Subscribe to Live Market Data with ib_async
DESCRIPTION: Demonstrates how to subscribe to real-time market data for a stock (e.g., AAPL) using `ib_async`. It continuously prints the last price, bid, and ask for a specified duration, using `ib.sleep` to pause between updates.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_20

LANGUAGE: python
CODE:
```
from ib_async import *
import time

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

# Subscribe to live market data
contract = Stock('AAPL', 'SMART', 'USD')
ticker = ib.reqMktData(contract, '', False, False)

# Print live quotes for 30 seconds
for i in range(30):
    ib.sleep(1)  # Wait 1 second
    if ticker.last:
        print(f"AAPL: ${ticker.last} (bid: ${ticker.bid}, ask: ${ticker.ask})")

ib.disconnect()
```

----------------------------------------

TITLE: Create Advanced Bracket Orders with ib_async
DESCRIPTION: Demonstrates how to construct a complex bracket order (parent, stop loss, and take profit) using `ib_async`. It shows how to link child orders to a parent order using `parentId` and manage order transmission flags.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_24

LANGUAGE: python
CODE:
```
from ib_async import *

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

# Create a bracket order (entry + stop loss + take profit)
contract = Stock('TSLA', 'SMART', 'USD')

# Parent order
parent = LimitOrder('BUY', 100, 250.00)
parent.orderId = ib.client.getReqId()
parent.transmit = False

# Stop loss
stopLoss = StopOrder('SELL', 100, 240.00)
stopLoss.orderId = ib.client.getReqId()
stopLoss.parentId = parent.orderId
stopLoss.transmit = False

# Take profit
takeProfit = LimitOrder('SELL', 100, 260.00)
takeProfit.orderId = ib.client.getReqId()
takeProfit.parentId = parent.orderId
takeProfit.transmit = True
```

----------------------------------------

TITLE: Monitor Portfolio Positions and Open Orders with ib_async
DESCRIPTION: Demonstrates how to retrieve and display current portfolio positions and open orders using `ib_async`. It iterates through positions to show symbol, quantity, and average cost, and lists details of any open trades.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_22

LANGUAGE: python
CODE:
```
from ib_async import *

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

# Get current positions
positions = ib.positions()
print("Current Positions:")
for pos in positions:
    print(f"{pos.contract.symbol}: {pos.position} @ {pos.avgCost}")

# Get open orders
orders = ib.openTrades()
print(f"\nOpen Orders: {len(orders)}")
for trade in orders:
    print(f"{trade.contract.symbol}: {trade.order.action} {trade.order.totalQuantity}")

ib.disconnect()
```

----------------------------------------

TITLE: Place Order and Access Trade Object
DESCRIPTION: Places the previously defined contract and order using `ib.placeOrder()`. This method is non-blocking and immediately returns a `Trade` object. The `Trade` object will be live-updated with order status changes, fills, and other related information.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/ordering.ipynb#_snippet_2

LANGUAGE: python
CODE:
```
trade = ib.placeOrder(contract, order)
```

----------------------------------------

TITLE: Format and Lint ib_async Code with Ruff
DESCRIPTION: This snippet provides the commands to automatically format and lint the `ib_async` project's Python code using `ruff`. The first command formats the code, and the second checks for style violations and applies fixes.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_33

LANGUAGE: bash
CODE:
```
poetry run ruff format
poetry run ruff check --fix
```

----------------------------------------

TITLE: Create and Request Basic Market Scanner Data
DESCRIPTION: Demonstrates how to define a basic market scanner subscription using `ScannerSubscription` by specifying the instrument type, location, and scan code. The subscription is then submitted to `ib.reqScannerData` to retrieve initial scanner results.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/scanners.ipynb#_snippet_1

LANGUAGE: python
CODE:
```
sub = ScannerSubscription(
    instrument="STK", locationCode="STK.US.MAJOR", scanCode="TOP_PERC_GAIN"
)

scanData = ib.reqScannerData(sub)

print(f"{len(scanData)} results, first one:")
print(scanData[0])
```

----------------------------------------

TITLE: ib_async Core Components API Reference
DESCRIPTION: This section outlines the core classes and modules within the `ib_async` library, detailing their primary functionalities. It covers connection management, market data requests, order management, financial instruments, real-time market data tickers, and various data structures used for portfolio and account information.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_27

LANGUAGE: APIDOC
CODE:
```
ib_async.ib.IB
  - Connection management (connect(), disconnect(), connectAsync())
  - Market data requests (reqMktData(), reqHistoricalData())
  - Order management (placeOrder(), cancelOrder())
  - Account data (positions(), accountSummary(), reqPnL())

ib_async.contract - Financial instruments
  - Stock, Option, Future, Forex, Index, Bond
  - Contract - Base class for all instruments
  - ComboLeg, DeltaNeutralContract - Complex instruments

ib_async.order - Order types and management
  - MarketOrder, LimitOrder, StopOrder, StopLimitOrder
  - Order - Base order class with all parameters
  - OrderStatus, OrderState - Order execution tracking
  - Trade - Complete order lifecycle tracking

ib_async.ticker - Real-time market data
  - Ticker - Live quotes, trades, and market data
  - Automatic field updates (bid, ask, last, volume, etc.)
  - Event-driven updates via updateEvent

ib_async.objects - Data structures
  - BarData - Historical price bars
  - Position - Portfolio positions
  - PortfolioItem - Portfolio details with P&L
  - AccountValue - Account metrics
```

----------------------------------------

TITLE: ib_async Version 0.9.52 Bug Fix
DESCRIPTION: This version includes a fix for the `Client.exerciseOptions` method.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/docs/changelog.rst#_snippet_52

LANGUAGE: APIDOC
CODE:
```
Client.exerciseOptions:
  - Fixed bug #152.
```

----------------------------------------

TITLE: Perform What-If Order Analysis
DESCRIPTION: Uses `ib.whatIfOrder()` to simulate an order (a MarketOrder to SELL 20,000 units) without actually sending it to the exchange. This allows checking the estimated commission and margin impact of the proposed order before committing to it, aiding in pre-trade analysis.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/ordering.ipynb#_snippet_9

LANGUAGE: python
CODE:
```
order = MarketOrder("SELL", 20000)
ib.whatIfOrder(contract, order)
```

----------------------------------------

TITLE: Track Real-time P&L with ib_async Callbacks
DESCRIPTION: Shows how to subscribe to and receive real-time Profit & Loss (P&L) updates using `ib_async`'s event-driven system. It defines a callback function `onPnL` that prints P&L changes and keeps the connection alive to receive continuous updates.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_23

LANGUAGE: python
CODE:
```
from ib_async import *

def onPnL(pnl):
    print(f"P&L Update: Unrealized: ${pnl.unrealizedPnL:.2f}, Realized: ${pnl.realizedPnL:.2f}")

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

# Subscribe to P&L updates
account = ib.managedAccounts()[0]
pnl = ib.reqPnL(account)
pnl.updateEvent += onPnL

# Keep running to receive updates
try:
    ib.run()  # Run until interrupted
except KeyboardInterrupt:
    ib.disconnect()
```

----------------------------------------

TITLE: Request Historical Market Data with ib_async
DESCRIPTION: Shows how to request historical market data for a given contract (e.g., EURUSD Forex) using `ib_async`. It includes parameters for duration, bar size, and what to show, and demonstrates converting the results to a pandas DataFrame.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_19

LANGUAGE: python
CODE:
```
from ib_async import *
# util.startLoop()  # uncomment this line when in a notebook

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

# Request historical data
contract = Forex('EURUSD')
bars = ib.reqHistoricalData(
    contract, endDateTime='', durationStr='30 D',
    barSizeSetting='1 hour', whatToShow='MIDPOINT', useRTH=True)

# Convert to pandas dataframe (pandas needs to be installed):
df = util.df(bars)
print(df.head())

ib.disconnect()
```

----------------------------------------

TITLE: Retrieve IB Account Summary with ib_async
DESCRIPTION: Demonstrates how to fetch and display account summary information from Interactive Brokers using `ib_async`. It retrieves the first managed account and iterates through its summary items.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_18

LANGUAGE: python
CODE:
```
from ib_async import *

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

# Get account summary
account = ib.managedAccounts()[0]
summary = ib.accountSummary(account)
for item in summary:
    print(f"{item.tag}: {item.value}")

ib.disconnect()
```

----------------------------------------

TITLE: Query Minimum Price Increments with ib_async
DESCRIPTION: Illustrates how to retrieve contract details for a Forex pair (USDJPY) to find associated market rule IDs, and then fetch the details of those market rules.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/docs/recipes.rst#_snippet_5

LANGUAGE: python
CODE:
```
usdjpy = Forex('USDJPY')
cd = ib.reqContractDetails(usdjpy)[0]
print(cd.marketRuleIds)

rules = [
    ib.reqMarketRule(ruleId)
    for ruleId in cd.marketRuleIds.split(',')]
print(rules)
```

----------------------------------------

TITLE: Basic ib_async Script Connection Pattern
DESCRIPTION: Demonstrates the fundamental connection and disconnection pattern for `ib_async` in a standalone Python script. It initializes the IB object, connects to TWS/Gateway, and ensures proper disconnection.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_14

LANGUAGE: python
CODE:
```
from ib_async import *

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)
# Your code here
ib.disconnect()
```

----------------------------------------

TITLE: Type System Modernization (ib_async API)
DESCRIPTION: Extensive type annotation improvements have been implemented, converting generic types like `Dict` to `dict` and `List` to `list`. The `Order` class now has proper type annotations and supports `Decimal` for price/quantity fields. `NamedTuple` instances have been converted to frozen dataclasses for better extensibility.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/docs/changelog.rst#_snippet_11

LANGUAGE: APIDOC
CODE:
```
(Type annotation changes throughout codebase):
  Dict -> dict
  List -> list
  FrozenSet -> frozenset

Order:
  (Proper type annotations for fields)
  price: Decimal
  totalQuantity: Decimal

(NamedTuple instances converted to frozen dataclasses)
```

----------------------------------------

TITLE: Retrieve Current Trading Positions
DESCRIPTION: Demonstrates how to access the current trading positions from the connected TWS/IBG instance using the `ib.positions()` method, which provides the synchronized 'current state' data.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/basics.ipynb#_snippet_3

LANGUAGE: python
CODE:
```
ib.positions()
```

----------------------------------------

TITLE: Perform Option Calculations with ib_async
DESCRIPTION: Demonstrates how to calculate implied volatility and option price for a given option contract using the ib_async library.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/docs/recipes.rst#_snippet_3

LANGUAGE: python
CODE:
```
option = Option('EOE', '20171215', 490, 'P', 'FTA', multiplier=100)

calc = ib.calculateImpliedVolatility(
    option, optionPrice=6.1, underPrice=525)
print(calc)

calc = ib.calculateOptionPrice(
    option, volatility=0.14, underPrice=525)
print(calc)
```

----------------------------------------

TITLE: Query Current Positions and Total Commissions
DESCRIPTION: Retrieves and displays the current trading positions held by the account using `ib.positions()`. It also calculates and sums the commissions from all fills received today by iterating through `ib.fills()` and accessing each fill's `commissionReport.commission` attribute.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/ordering.ipynb#_snippet_8

LANGUAGE: python
CODE:
```
ib.positions()
```

LANGUAGE: python
CODE:
```
sum(fill.commissionReport.commission for fill in ib.fills())
```

----------------------------------------

TITLE: ib_async: Migration Notes for v2.0.0
DESCRIPTION: Important considerations and behavioral changes for users migrating to ib_async version 2.0.0, covering updates to contract qualification, default value handling, ticker behavior, and order management.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/docs/changelog.rst#_snippet_20

LANGUAGE: APIDOC
CODE:
```
qualifyContractsAsync() users:
  - The return value now always contains the same number of elements as input contracts.
  - Check for `None` values to detect failed qualifications.
```

LANGUAGE: APIDOC
CODE:
```
Custom defaults users:
  - Consider using `IBDefaults()` to customize empty values if you've been manually handling -1 prices or 0 sizes.
```

LANGUAGE: APIDOC
CODE:
```
Ticker previous value users:
  - The logic for `previousPrice`/`previousSize` is now more accurate but may show different values if you were relying on the old conditional update behavior.
```

LANGUAGE: APIDOC
CODE:
```
Order management users:
  - Order validation errors are now logged to order history instead of causing order deletions.
  - Check order event logs for validation details.
```

----------------------------------------

TITLE: Handle IB API Connection Refused Errors
DESCRIPTION: Demonstrates how to connect to Interactive Brokers TWS or Gateway, highlighting common port issues. Ensures the TWS/Gateway application is running and API is enabled, and that the correct port (7497 for TWS, 4001 for Gateway) is used.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_11

LANGUAGE: python
CODE:
```
# Make sure TWS/Gateway is running and API is enabled
# Check that ports match (7497 for TWS, 4001 for Gateway)
ib.connect('127.0.0.1', 7497, clientId=1)  # TWS
ib.connect('127.0.0.1', 4001, clientId=1)  # Gateway
```

----------------------------------------

TITLE: Enable DEBUG Level Logging to Console
DESCRIPTION: Configures `ib_async` to output all log messages, including detailed debug information and network traffic, to the console for in-depth troubleshooting and monitoring.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/basics.ipynb#_snippet_9

LANGUAGE: python
CODE:
```
import logging

util.logToConsole(logging.DEBUG)
```

----------------------------------------

TITLE: Access Order Book Data with ib_async
DESCRIPTION: Shows how to request market depth (order book) for a Forex pair (EURUSD) and continuously print the bid and ask prices.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/docs/recipes.rst#_snippet_4

LANGUAGE: python
CODE:
```
eurusd = Forex('EURUSD')
ticker = ib.reqMktDepth(eurusd)
while ib.sleep(5):
    print(
        [d.price for d in ticker.domBids],
        [d.price for d in ticker.domAsks])
```

----------------------------------------

TITLE: Basic Error Handling for ib_async Connection
DESCRIPTION: This snippet provides a basic error handling pattern for connecting to the Interactive Brokers API using `ib_async`. It catches `ConnectionRefusedError` if the TWS/Gateway is not running or the API is not enabled, and a general `Exception` for other connection issues, providing informative messages.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/README.md#_snippet_30

LANGUAGE: python
CODE:
```
try:
    ib.connect('127.0.0.1', 7497, clientId=1)
except ConnectionRefusedError:
    print("TWS/Gateway not running or API not enabled")
except Exception as e:
    print(f"Connection error: {e}")
```

----------------------------------------

TITLE: Display live market depth (order book) updates
DESCRIPTION: Sets up an event handler to dynamically display a live order book. It uses `IPython.display` and `pandas` to create and update a DataFrame with bid/ask sizes and prices from `ticker.domBids` and `ticker.domAsks` whenever the `ticker.updateEvent` is triggered. The display is refreshed every 15 seconds.

SOURCE: https://github.com/ib-api-reloaded/ib_async/blob/main/notebooks/market_depth.ipynb#_snippet_3

LANGUAGE: python
CODE:
```
from IPython.display import display, clear_output
import pandas as pd

df = pd.DataFrame(index=range(5), columns="bidSize bidPrice askPrice askSize".split())


def onTickerUpdate(ticker):
    bids = ticker.domBids
    for i in range(5):
        df.iloc[i, 0] = bids[i].size if i < len(bids) else 0
        df.iloc[i, 1] = bids[i].price if i < len(bids) else 0
    asks = ticker.domAsks
    for i in range(5):
        df.iloc[i, 2] = asks[i].price if i < len(asks) else 0
        df.iloc[i, 3] = asks[i].size if i < len(asks) else 0
    clear_output(wait=True)
    display(df)

ticker.updateEvent += onTickerUpdate

IB.sleep(15);
```