# SIP Simulator - pipeline and decision diagrams

All diagrams are Mermaid. They render in VS Code (Markdown Preview
Mermaid Support), GitHub, Obsidian and Notion.

---

## 1. End-to-end pipeline (high level)

```mermaid
flowchart TB
    subgraph INPUT["1 · INPUT LAYER (Streamlit)"]
        direction TB
        A1["Money input mode<br/>Per-fund SIP  |  Total SIP + %"]
        A2["Fund table<br/>name, return, expense, start,<br/>target %, STCG/LTCG, threshold,<br/>exemption, step-up"]
        A3["Global settings<br/>horizon, SIP timing,<br/>portfolio start, inflation, slab"]
        A4["Strategy switches<br/>step-up · stagger · rebalance ·<br/>SWP · pauses"]
    end

    subgraph BUILD["2 · TRANSLATION LAYER"]
        B1["apply tax presets<br/>(unless Override)"]
        B2["normalise allocation to 100%<br/>-> per-fund SIP"]
        B3["build FundConfiguration list<br/>net = gross - expense"]
        B4["build SimulationSettings<br/>StepUp · Withdrawal · Pause ·<br/>Rebalance"]
    end

    subgraph ENGINE["3 · SIMULATION ENGINE (no Streamlit)"]
        direction TB
        C1["PortfolioSimulator<br/>loop month = 0 .. 12·years"]
        C2["FundHoldings<br/>FIFO lot book per fund"]
        C3["CapitalGainsTaxPolicy<br/>+ ExemptionLedger"]
        C4["ContributionPlan · WithdrawalPlan<br/>· PauseCalendar · target weights"]
    end

    subgraph RUNS["4 · TWO PASSES"]
        D1["NOMINAL run<br/>net return"]
        D2["REAL run<br/>net return deflated by inflation"]
    end

    subgraph OUT["5 · RESULT OBJECTS"]
        E1["MonthlySnapshot[]<br/>value · invested · withdrawn ·<br/>tax · SIP · SWP"]
        E2["FundOutcome[]<br/>per fund end value, gain, tax,<br/>STCG/LTCG split"]
        E3["RebalanceEvent[]<br/>before/after value + weights, tax"]
    end

    subgraph PRESENT["6 · PRESENTATION"]
        F1["tables.py<br/>monthly series + per-fund summary"]
        F2["charts.py<br/>growth panel + 3 donuts"]
        F3["narrative.py<br/>summary lines, cautions, how-to"]
    end

    subgraph DELIVER["7 · DELIVERY"]
        G1["Dashboard<br/>KPI cards · charts · tables"]
        G2["Excel workbook<br/>6 sheets"]
        G3["PDF snapshot<br/>landscape report"]
    end

    INPUT --> BUILD --> ENGINE
    ENGINE --> RUNS
    D1 --> OUT
    D2 --> OUT
    OUT --> PRESENT --> DELIVER
```

---

## 2. What happens inside ONE simulated month

```mermaid
flowchart TB
    S(["month m starts"]) --> T1{"SIP timing =<br/>start of month?"}
    T1 -- yes --> C1["for each fund:<br/>instalment = base x step-up factor"]
    C1 --> P1{"month paused<br/>for SIP?"}
    P1 -- yes --> Z1["contribute 0"]
    P1 -- no --> P2{"m >= fund start<br/>offset?"}
    P2 -- no --> Z1
    P2 -- yes --> BUY1["add lot<br/>invested principal += amount"]
    T1 -- no --> VAL
    Z1 --> VAL
    BUY1 --> VAL

    VAL["value every fund<br/>lot value = principal x (1+i)^months held"] --> W1{"SWP on and<br/>m >= SWP start?"}
    W1 -- no --> R1
    W1 -- yes --> W2{"month paused<br/>for SWP?"}
    W2 -- yes --> R1
    W2 -- no --> W3["amount = fixed or Jan..Dec schedule<br/>x (1 + annual change)^years"]
    W3 --> W4["sell pro-rata from each fund<br/>by current value weight"]
    W4 --> W5["FIFO lots -> gain -> tax<br/>(STCG / LTCG / exemption)"]
    W5 --> R1

    R1{"rebalancing on<br/>and (m+1) mod N = 0<br/>and event cap not hit?"}
    R1 -- no --> T2
    R1 -- yes --> R2{"method?"}
    R2 -- "full liquidation" --> R3["sell 100% of every fund<br/>-> cash - tax -> buy at target %"]
    R2 -- "sell overweight only" --> R4["sell excess above target<br/>-> cash - tax -> top up underweight"]
    R3 --> R5["record RebalanceEvent<br/>weights before / after / tax"]
    R4 --> R5
    R5 --> T2

    T2{"SIP timing =<br/>end of month?"} -- yes --> BUY2["add lot (no extra growth month)"]
    T2 -- no --> SNAP
    BUY2 --> SNAP
    SNAP["record MonthlySnapshot<br/>value, invested, withdrawn, tax,<br/>SIP, SWP"] --> E(["month m ends"])
```

---

## 3. Toggle tree - every optional branch and its sub-inputs

```mermaid
flowchart LR
    ROOT(["Strategy switches"])

    ROOT --> SU["Step-up SIP"]
    SU --> SU0["OFF"]
    SU --> SU1["GLOBAL<br/>-> one % per year"]
    SU --> SU2["PER_FUND<br/>-> each fund's own %"]
    SU --> SU3["BOTH<br/>-> global x per-fund"]
    SU0 --> SUX["plus, in any mode:<br/>interval in months ·<br/>delay before first step ·<br/>fixed Rs increment"]
    SU1 --> SUX
    SU2 --> SUX
    SU3 --> SUX

    ROOT --> ST{"Different start<br/>dates per fund?"}
    ST -- OFF --> ST0["all funds start on<br/>portfolio start date"]
    ST -- ON --> ST1["Fund Start column<br/>editable per fund"]

    ROOT --> RB{"Rebalancing?"}
    RB -- OFF --> RB0["natural drift<br/>targets never used"]
    RB -- ON --> RBT["target basis"]
    RBT --> RBT1["INITIAL_SIP_SPLIT"]
    RBT --> RBT2["TARGET_ALLOC_COLUMN"]
    RBT1 --> RBG["trigger"]
    RBT2 --> RBG
    RBG --> RBG1["CALENDAR<br/>-> every N months"]
    RBG --> RBG2["DRIFT_BAND<br/>-> band in % points"]
    RBG --> RBG3["CALENDAR_AND_BAND<br/>-> check on date,<br/>trade only if out of band"]
    RBG1 --> RBM["method"]
    RBG2 --> RBM
    RBG3 --> RBM
    RBM --> RBM1["Full liquidation<br/>exact target split"]
    RBM --> RBM2["Partial<br/>sell overweight only"]
    RBM1 --> RBX{"Pay rebalancing<br/>tax from?"}
    RBM2 --> RBX
    RBX -- OUTSIDE --> RBX1["tax owed and reported,<br/>paid from your bank<br/>(no TDS on equity)"]
    RBX -- PORTFOLIO --> RBX0["tax funded by selling<br/>more units"]
    RBX1 --> RBC["optional: max event cap"]
    RBX0 --> RBC

    ROOT --> CS{"Steer new SIP money<br/>to underweight funds?"}
    CS -- ON --> CS1["cash-flow rebalancing<br/>sells nothing, zero tax"]
    CS -- OFF --> CS0["each fund gets<br/>its own instalment"]

    ROOT --> SW{"SWP?"}
    SW -- OFF --> SW0["no withdrawals"]
    SW -- ON --> SWD["SWP start date"]
    SWD --> SWM["mode"]
    SWM --> SWM1["FIXED<br/>-> Rs/month<br/>-> annual change % (+/-)"]
    SWM --> SWM2["SCHEDULE_12<br/>-> Rs for Jan..Dec<br/>-> change %/yr for Jan..Dec<br/>-> global annual change %"]
    SWM --> SWM3["PERCENT_OF_CORPUS<br/>-> % of value each month<br/>-> can never deplete"]

    ROOT --> TX["Taxation & expense"]
    TX --> TX1["exemption: PER_TAXPAYER<br/>(statutory) or PER_FUND"]
    TX --> TX2["final exit tax on<br/>unrealized gains?"]
    TX --> TX3["expense: CONTINUOUS_ACCRUAL<br/>or SIMPLE_SUBTRACTION"]

    ROOT --> GP{"Gaps / pauses?"}
    GP -- OFF --> GP0["never paused"]
    GP -- ON --> GP1["recurring: pick SIP months"]
    GP --> GP2["recurring: pick SWP months"]
    GP --> GP3["irregular ranges table<br/>start · end · apply to<br/>SIP / SWP / BOTH"]

    ROOT --> PR["Fund tax preset<br/>per fund"]
    PR --> PR1["Equity (default)<br/>20 / 12.5 / 12m / 1.25L"]
    PR --> PR2["Debt post Apr-2023<br/>always STCG at slab %"]
    PR --> PR3["Custom / Override<br/>-> type every tax field"]
```

---

## 4. Money input mode - the first decision

```mermaid
flowchart TB
    M(["Monthly money to invest"]) --> MODE{"input mode"}

    MODE -- "Per-fund SIP (manual)" --> A1["type Rs for each fund"]
    A1 --> A2["add / remove funds"]
    A2 --> A3["per-fund start dates allowed<br/>if stagger is ON"]
    A3 --> OUT

    MODE -- "Total SIP + allocation %" --> B1["type ONE total Rs / month"]
    B1 --> B2["type % per fund"]
    B2 --> B3{"normalise to 100%?"}
    B3 -- ON --> B4["% rescaled so sum = 100"]
    B3 -- OFF --> B5["% kept as typed<br/>(sum may be under/over 100)"]
    B4 --> B6["fund SIP = total x % / 100"]
    B5 --> B6
    B6 --> B7["% is also reused as the<br/>default rebalancing target"]
    B7 --> OUT

    OUT["per-fund monthly instalment"] --> F["fund detail table<br/>return · expense · start ·<br/>target % · tax fields · step-up"]
    F --> OV{"Override Preset<br/>per fund?"}
    OV -- no --> D["preset tax values used"]
    OV -- yes --> E["manually typed tax values used"]
```

---

## 5. Output surface

```mermaid
flowchart LR
    R(["Simulation results"]) --> N["NOMINAL block"]
    R --> RE["REAL block (inflation adjusted)"]

    N --> N1["KPI cards<br/>end value · invested ·<br/>withdrawn · tax"]
    N --> N2["Growth chart<br/>money vs months"]
    N --> N3["Invested split donut"]
    N --> N4["Gains split donut"]
    N --> N5["End value split donut"]
    N --> N6["Per-fund summary table"]

    RE --> R1["Real KPI cards"]
    RE --> R2["Real growth chart"]
    RE --> R3["Real donuts x3"]
    RE --> R4["Per-fund real table"]

    R --> NOTE["Notes · cautions · how to use"]
    R --> EXP["Export"]
    EXP --> X1["Excel<br/>Dashboard · Funds ·<br/>Nominal/Real summary ·<br/>Nominal/Real series"]
    EXP --> X2["PDF<br/>summaries · charts ·<br/>tables · notes"]
```

---

## 6. Module dependency map (what imports what)

```mermaid
flowchart BT
    C["constants"] --> F["formatting"]
    C --> T["time_utils"]
    C --> RT["returns"]
    F --> M["models"]
    T --> M
    RT --> M
    M --> TX["taxation"]
    M --> H["holdings"]
    M --> SC["schedules"]
    M --> AL["allocation"]
    TX --> H
    H --> EN["engine"]
    SC --> EN
    AL --> EN
    EN --> TB["tables"]
    EN --> LAB["rebalancing_lab"]
    EN --> IN["inflation"]
    EN --> LG["ledgers"]
    EN --> VA["validation"]
    TB --> CH["charts"]
    TB --> DR["dashboard_run"]
    LG --> DR
    IN --> DR
    CH --> DR
    NR["narrative"] --> DR
    DR --> UI["ui/*"]
    DR --> EX["exports/*"]
    VA --> UI
    SC["scenarios"] --> APP
    UI --> APP
    EX --> APP
    FB["fund_builder"] --> APP
```
