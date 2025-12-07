# Component Interaction Diagrams

## System Component Map

This document provides detailed interaction diagrams showing how components communicate within the Auto-Trader system.

## 1. High-Level Component Architecture

```mermaid
graph TB
    subgraph "Presentation Layer"
        CLI[CLI Interface<br/>commands.py]
        Config[Configuration Files<br/>YAML/ENV]
    end
    
    subgraph "Application Control"
        MainApp[Main Application<br/>src/main.py]
        TradingApp[Trading Application<br/>main_application.py]
        Orchestrator[Trade Orchestrator<br/>trade_orchestrator.py]
    end
    
    subgraph "Core Services"
        PlanLoader[Plan Loader<br/>plan_loader.py]
        RiskMgr[Risk Manager<br/>risk_manager.py]
        TradeEng[Trade Engine<br/>execution_functions.py]
        LifecycleMgr[Lifecycle Manager<br/>lifecycle_manager.py]
    end
    
    subgraph "Integration Services"
        IBKRClient[IBKR Client<br/>client.py]
        DiscordNotif[Discord Notifier<br/>notifier.py]
        MarketDataMgr[Market Data Manager<br/>market_data_manager.py]
    end
    
    subgraph "Data Persistence"
        StateMan[State Manager<br/>state_manager.py]
        FileWatch[File Watcher<br/>file_watcher.py]
        BackupMgr[Backup Manager<br/>backup_manager.py]
    end
    
    %% Primary flows
    CLI -.->|Commands| PlanLoader
    Config -->|Initialize| MainApp
    MainApp -->|Creates| TradingApp
    TradingApp -->|Manages| Orchestrator
    
    %% Core service interactions
    Orchestrator -->|Coordinates| TradeEng
    Orchestrator -->|Uses| RiskMgr
    Orchestrator -->|Controls| LifecycleMgr
    PlanLoader -->|Loads Plans| Orchestrator
    
    %% Integration flows (UPDATED with new market data flow)
    TradeEng -->|Executes via| IBKRClient
    LifecycleMgr -->|Notifies| DiscordNotif
    MarketDataMgr -->|Real-time bars| Orchestrator
    IBKRClient -->|IB instance| MarketDataMgr
    TradingApp -->|Initializes| MarketDataMgr
    TradingApp -->|Subscribes| MarketDataMgr
    
    %% Persistence flows
    LifecycleMgr -->|Saves State| StateMan
    StateMan -->|Writes| BackupMgr
    FileWatch -.->|Monitors| PlanLoader
    
    style MainApp fill:#f9f,stroke:#333,stroke-width:4px
    style Orchestrator fill:#bbf,stroke:#333,stroke-width:4px
```

## 2. Trade Plan Creation and Validation Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Wizard
    participant Validator
    participant PlanLoader
    participant FileSystem
    
    User->>CLI: create-plan-interactive
    CLI->>Wizard: Start wizard
    
    loop For each field
        Wizard->>User: Prompt for input
        User->>Wizard: Provide value
        Wizard->>Validator: Validate field
        Validator-->>Wizard: Valid/Invalid
    end
    
    Wizard->>PlanLoader: Create TradePlan object
    PlanLoader->>Validator: Full validation
    Validator-->>PlanLoader: Validation result
    
    alt Validation Success
        PlanLoader->>FileSystem: Save YAML
        FileSystem-->>User: Plan saved
    else Validation Failed
        PlanLoader-->>User: Error details
    end
```

## 3. Market Data Pipeline ✅ **FULLY INTEGRATED**

```mermaid
graph LR
    subgraph "IBKR Integration"
        TWS[IBKR TWS/Gateway]
        IBKRClient[IBKR Client<br/>client.py]
        IB_Instance[IB Instance<br/>get_ib_client()]
    end
    
    subgraph "Market Data Management (NEW)"
        MktDataMgr[Market Data Manager<br/>market_data_manager.py]
        SubMgr[Subscription Manager<br/>subscription_manager.py]
        DataDist[Data Distribution<br/>market_data_distribution.py]
        BarConv[Bar Converter<br/>bar_converter.py]
    end
    
    subgraph "Application Integration (NEW)"
        TradingApp[Trading Application<br/>main_application.py]
        Callback[Market Data Callback<br/>_market_data_callback()]
        TradeOrch[Trade Orchestrator<br/>trade_orchestrator.py]
    end
    
    subgraph "Signal Processing"
        BarData[Bar Data Events]
        ExecFunc[Execution Functions<br/>close_above/below/trailing]
        SignalProc[Signal Processor<br/>signal_processor.py]
    end
    
    subgraph "Plan Analysis (NEW)"
        PlanLoader[Active Trade Plans]
        SymbolExtract[Symbol Extraction<br/>['AAPL', 'MSFT']]
        TimeframeExtract[Timeframe Extraction<br/>['1min', '5min', '15min', '30min']]
    end
    
    TWS -->|Real-time Data| IBKRClient
    IBKRClient -->|Exposes| IB_Instance
    IB_Instance -->|Connects| MktDataMgr
    
    TradingApp -->|Initializes| MktDataMgr
    TradingApp -->|Registers Callback| MktDataMgr
    
    PlanLoader -->|Active Plans| TradingApp
    TradingApp -->|Extract| SymbolExtract
    TradingApp -->|Extract| TimeframeExtract
    SymbolExtract -->|Subscribe| SubMgr
    TimeframeExtract -->|Subscribe| SubMgr
    
    MktDataMgr -->|Manages| SubMgr
    SubMgr -->|Real-time Bars| BarConv
    BarConv -->|Processed| DataDist
    DataDist -->|Distribute| Callback
    Callback -->|Route| TradeOrch
    
    TradeOrch -->|Process| BarData
    BarData -->|Evaluate| ExecFunc
    ExecFunc -->|Generate| SignalProc
    
    style MktDataMgr fill:#f9f,stroke:#333,stroke-width:3px
    style TradingApp fill:#bbf,stroke:#333,stroke-width:3px
    style Callback fill:#bfb,stroke:#333,stroke-width:3px
```

## 4. Trade Execution Lifecycle

```mermaid
stateDiagram-v2
    [*] --> AwaitingEntry: Plan Loaded
    
    AwaitingEntry --> SignalGenerated: Entry Condition Met
    SignalGenerated --> RiskValidation: Process Signal
    
    RiskValidation --> OrderCreated: Risk Check Passed
    RiskValidation --> AwaitingEntry: Risk Check Failed
    
    OrderCreated --> OrderSubmitted: Send to IBKR
    OrderSubmitted --> OrderFilled: Execution
    OrderSubmitted --> OrderRejected: IBKR Rejection
    
    OrderRejected --> AwaitingEntry: Retry Logic
    
    OrderFilled --> PositionOpen: Entry Complete
    
    PositionOpen --> MonitoringExit: Track Position
    MonitoringExit --> ExitSignal: Exit Condition Met
    
    ExitSignal --> ExitOrderCreated: Create Exit Order
    ExitOrderCreated --> ExitOrderFilled: Execution
    
    ExitOrderFilled --> PositionClosed: Exit Complete
    PositionClosed --> TradeComplete: Update History
    
    TradeComplete --> [*]: Done
```

## 5. Risk Management Integration

```mermaid
graph TD
    subgraph "Risk Input"
        Plan[Trade Plan]
        Market[Market Price]
        Account[Account State]
    end
    
    subgraph "Risk Calculations"
        Sizer[Position Sizer]
        Portfolio[Portfolio Tracker]
        Validator[Risk Validator]
    end
    
    subgraph "Risk Outputs"
        Size[Position Size]
        Approval[Risk Approval]
        Limits[Risk Limits]
    end
    
    Plan -->|Risk Category| Sizer
    Market -->|Current Price| Sizer
    Account -->|Balance| Sizer
    
    Sizer -->|Calculate| Size
    
    Size -->|Proposed| Portfolio
    Portfolio -->|Current Risk| Validator
    
    Validator -->|Check Limits| Limits
    Validator -->|Decision| Approval
    
    Approval -->|Proceed/Block| Order[Order Creation]
```

## 6. Order Management Flow

```mermaid
sequenceDiagram
    participant Signal as Signal Processor
    participant Risk as Risk Manager
    participant OrderMgr as Order Manager
    participant IBKR as IBKR Client
    participant Simulator as Simulation Engine
    participant Discord as Discord Notifier
    participant State as State Manager
    
    Signal->>Risk: Validate Signal
    Risk-->>Signal: Approved/Rejected
    
    alt Risk Approved
        Signal->>OrderMgr: Create Order Request
        
        alt Simulation Mode
            OrderMgr->>Simulator: Simulate Order
            Simulator-->>OrderMgr: Simulated Fill
        else Live Mode
            OrderMgr->>IBKR: Submit Order
            IBKR-->>OrderMgr: Order Status
            IBKR-->>OrderMgr: Fill Event
        end
        
        OrderMgr->>Discord: Send Notification
        OrderMgr->>State: Update Position State
        State-->>State: Persist to Disk
    end
```

## 7. Event-Driven Architecture

```mermaid
graph TB
    subgraph "Event Sources"
        MktData[Market Data Events]
        UserCmd[User Commands]
        Timer[Timer Events]
        FileChg[File Changes]
    end
    
    subgraph "Event Bus"
        EventMgr[Event Manager]
        Queue[Event Queue]
    end
    
    subgraph "Event Handlers"
        BarClose[Bar Close Handler]
        SignalGen[Signal Generator]
        OrderProc[Order Processor]
        StateSync[State Synchronizer]
        NotifSend[Notification Sender]
    end
    
    subgraph "Actions"
        Evaluate[Evaluate Functions]
        Execute[Execute Orders]
        Persist[Persist State]
        Notify[Send Notifications]
    end
    
    MktData -->|Price Update| EventMgr
    UserCmd -->|Command| EventMgr
    Timer -->|Schedule| EventMgr
    FileChg -->|File Modified| EventMgr
    
    EventMgr -->|Dispatch| Queue
    
    Queue -->|Bar Complete| BarClose
    Queue -->|Signal Event| SignalGen
    Queue -->|Order Event| OrderProc
    Queue -->|State Change| StateSync
    Queue -->|Notification| NotifSend
    
    BarClose -->|Trigger| Evaluate
    SignalGen -->|Trigger| Execute
    OrderProc -->|Trigger| Execute
    StateSync -->|Trigger| Persist
    NotifSend -->|Trigger| Notify
```

## 8. Data Persistence Layer

```mermaid
graph LR
    subgraph "In-Memory State"
        Positions[Active Positions]
        Orders[Pending Orders]
        History[Trade History]
    end
    
    subgraph "Persistence Manager"
        StateMgr[State Manager]
        Serializer[JSON Serializer]
        Writer[Atomic Writer]
    end
    
    subgraph "File System"
        StateFile[state.json]
        BackupFile[state.backup.json]
        HistoryCSV[trade_history.csv]
        LogFiles[*.log]
    end
    
    subgraph "Recovery"
        Loader[State Loader]
        Validator[State Validator]
        Restorer[State Restorer]
    end
    
    Positions -->|Save| StateMgr
    Orders -->|Save| StateMgr
    History -->|Append| StateMgr
    
    StateMgr -->|Serialize| Serializer
    Serializer -->|Write| Writer
    Writer -->|Primary| StateFile
    Writer -->|Backup| BackupFile
    Writer -->|History| HistoryCSV
    
    StateFile -->|Load| Loader
    BackupFile -->|Fallback| Loader
    Loader -->|Validate| Validator
    Validator -->|Restore| Restorer
    Restorer -->|Initialize| Positions
    Restorer -->|Initialize| Orders
```

## 9. CLI Command Router

```mermaid
graph TD
    subgraph "CLI Entry"
        CLI[auto-trader CLI]
    end
    
    subgraph "Command Groups"
        Config[Config Commands<br/>validate-config, setup]
        Plan[Plan Commands<br/>create, validate, list]
        Template[Template Commands<br/>list-templates]
        Monitor[Monitor Commands<br/>monitor, summary]
        Risk[Risk Commands<br/>calculate-position]
        Mgmt[Management Commands<br/>update, archive, stats]
    end
    
    subgraph "Command Handlers"
        ConfigH[config_commands.py]
        PlanH[plan_commands.py]
        TemplateH[template_commands.py]
        MonitorH[monitor_commands.py]
        RiskH[risk_commands.py]
        MgmtH[management_commands.py]
    end
    
    subgraph "Core Services"
        Validation[Validation Engine]
        FileOps[File Operations]
        Display[Display Utils]
        Interactive[Interactive Wizards]
    end
    
    CLI -->|Route| Config
    CLI -->|Route| Plan
    CLI -->|Route| Template
    CLI -->|Route| Monitor
    CLI -->|Route| Risk
    CLI -->|Route| Mgmt
    
    Config --> ConfigH
    Plan --> PlanH
    Template --> TemplateH
    Monitor --> MonitorH
    Risk --> RiskH
    Mgmt --> MgmtH
    
    ConfigH --> Validation
    PlanH --> Interactive
    TemplateH --> FileOps
    MonitorH --> Display
    RiskH --> Validation
    MgmtH --> FileOps
```

## 10. Integration Points Summary

```mermaid
mindmap
  root((Auto-Trader))
    User Interface
      CLI Commands
      Configuration Files
      Interactive Wizards
    Core Engine
      Trade Orchestrator
      Execution Functions
      Lifecycle Manager
      Signal Processor
    Risk Management
      Position Sizer
      Portfolio Tracker
      Risk Validator
    External Systems
      IBKR TWS
        Market Data
        Order Execution
      Discord
        Trade Notifications
        Error Alerts
    Data Layer
      File System
        YAML Plans
        JSON State
        CSV History
      In-Memory
        Market Cache
        Position State
```

## 11. Periodic Signal Evaluation Flow ✅ **NEW IMPLEMENTATION**

```mermaid
sequenceDiagram
    participant TWS as IBKR TWS/Gateway
    participant IBKR as IBKRClient
    participant MDM as MarketDataManager
    participant TA as TradingApplication
    participant TO as TradeOrchestrator
    participant EF as ExecutionFunction
    participant SP as SignalProcessor
    participant OEM as OrderExecutionManager
    
    Note over TWS,OEM: Real-time Periodic Evaluation Flow
    
    %% Initialization Phase
    TA->>IBKR: connect()
    IBKR-->>TA: Connected
    TA->>IBKR: get_ib_client()
    IBKR-->>TA: IB instance
    TA->>MDM: new MarketDataManager(ib)
    TA->>MDM: add_subscriber("trade_orchestrator", callback)
    
    %% Subscription Phase
    TA->>TO: start() - loads active plans
    TO-->>TA: active_plans loaded
    TA->>TA: extract symbols ['AAPL', 'MSFT']
    TA->>TA: extract timeframes ['1min', '5min', '15min', '30min']
    TA->>MDM: subscribe_symbols(symbols, timeframes)
    MDM-->>TA: 8 subscriptions successful
    
    %% Real-time Processing Loop
    loop Every Bar (1min, 5min, 15min, 30min)
        TWS->>IBKR: Real-time bar data
        IBKR->>MDM: Bar update
        MDM->>MDM: Process & convert bar
        MDM->>TA: _market_data_callback(bar_data)
        TA->>TO: process_market_data_event(bar_data)
        
        alt Plan Status = AWAITING_ENTRY
            TO->>EF: evaluate_entry_function(plan, bar_data)
            EF-->>TO: ExecutionSignal (ENTER_LONG/NO_ACTION)
            
            alt Signal = ENTER_LONG
                TO->>SP: process_entry_signal(plan, signal)
                SP->>OEM: execute_order(entry_order)
                OEM-->>SP: OrderResult
                SP-->>TO: Entry successful
                TO->>TO: Update plan.status = POSITION_OPEN
            end
            
        else Plan Status = POSITION_OPEN
            TO->>EF: evaluate_exit_function(plan, bar_data)
            EF-->>TO: ExecutionSignal (EXIT/NO_ACTION)
            
            alt Signal = EXIT
                TO->>SP: process_exit_signal(plan, signal)
                SP->>OEM: execute_order(exit_order)
                OEM-->>SP: OrderResult
                SP-->>TO: Exit successful
                TO->>TO: Update plan.status = COMPLETED
            end
        end
    end
    
    Note over TWS,OEM: Continuous evaluation during market hours
```

**Key Implementation Details:**

1. **Automatic Symbol Detection**: Extracts unique symbols from all active trade plans
2. **Dynamic Timeframe Subscription**: Subscribes to all timeframes used by entry/exit functions
3. **Real-time Bar Processing**: Each bar update triggers evaluation for relevant plans
4. **Status-Based Evaluation**: Entry functions for AWAITING_ENTRY, exit functions for POSITION_OPEN
5. **Complete Lifecycle**: Automatic transition from entry → position tracking → exit → completion

## Component Communication Patterns

### 1. **Request-Response**
- CLI → Command Handlers
- Risk Manager → Position Sizer
- Order Manager → IBKR Client

### 2. **Event-Driven** ✅ **NOW FULLY FUNCTIONAL**
- **Market Data → Bar Close Events** ✅ Real-time IBKR integration complete
- **Bar Events → Signal Evaluation** ✅ Automatic periodic evaluation
- **Order Events → Discord Notifications** ✅ Complete trade lifecycle notifications
- File Changes → Plan Reloading (planned for v2)

### 3. **Publish-Subscribe** ✅ **ENHANCED WITH REAL-TIME DATA**
- **Market Data Distribution** ✅ MarketDataManager → TradeOrchestrator subscription
- **Real-time Bar Streaming** ✅ Automatic distribution to all registered subscribers
- Signal Broadcasting ✅ Signal events distributed to order processors
- State Change Notifications ✅ Position state changes broadcasted

### 4. **Pipeline**
- Market Data → Processing → Caching
- Signal → Validation → Execution
- Trade → History → Persistence

### 5. **Circuit Breaker**
- IBKR Connection Management
- Rate Limiting
- Error Recovery

## Key Integration Considerations

1. **Loose Coupling**: Components communicate through well-defined interfaces
2. **Async Operations**: Non-blocking I/O for market data and external APIs
3. **Error Boundaries**: Each component handles its own errors gracefully
4. **State Consistency**: Atomic operations for state changes
5. **Performance**: Caching and batching for efficiency
6. **Observability**: Comprehensive logging at all integration points
7. **Testability**: Mock implementations for all external dependencies
8. **Resilience**: Retry logic and fallback mechanisms