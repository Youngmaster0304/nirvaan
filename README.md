# RailBlock AI - Automatic Block Planning for Indian Railways

**SIH 2026 Problem Statement #26027** | Ministry of Railways | Category: Software

AI-Powered Automatic Block Planning system that automates maintenance block scheduling, optimizes multi-department coordination, and ensures safety compliance across Indian Railway networks.

## Problem
Indian Railways manages 131,000+ km of track with thousands of daily maintenance blocks. Current planning is manual, phone-based, and causes:
- Blocks treated as "favors" instead of entitlements
- No audit trail of block refusals
- Same time slot sold twice (trains + corridors)
- Safety incidents from delayed maintenance (Kanchanjunga, Khatauli)

## Solution
RailBlock AI automates the entire block planning lifecycle:

### Core Features
- **Block Planning Calendar** - AI-generated weekly block schedules
- **Defect Tracking** - Priority-based defect management (critical/high/medium/low)
- **Corridor Management** - Track utilization across 10 corridors
- **AI Optimizer** - ML-based optimization for downtime reduction

### Advanced Systems
- **Maintenance Engine** - Categorizes defects as Routine (168h SLA), Fault (24h SLA), or Urgent (4h emergency override)
- **Directional Token Locks** - Prevents head-on deadlocks on single-line sections by enforcing mutual exclusion of UP/DOWN tokens
- **HOER Crew Compliance** - Non-linear penalty engine ensuring crew don't exceed 10-hour duty limits, with automatic reassignment alerts
- **VVIP & Emergency Protocols** - Auto-protects Rajdhani/special trains through maintenance corridors, triggers critical pushes after 11-hour delays

## Tech Stack
- **Backend**: Python 3.13, FastAPI, SQLite
- **Frontend**: Vanilla JS, Inter font, Font Awesome icons
- **Theme**: White IRCTC/government style, no emojis, professional typography

## API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboard/stats` | GET | Dashboard KPIs |
| `/api/maintenance/engine` | GET | Maintenance categories & rules |
| `/api/token/locks` | GET | Directional token lock status |
| `/api/crew/duty` | GET | Crew HOER compliance |
| `/api/emergency/pushes` | GET | Emergency push history |
| `/api/emergency/vvip-status` | GET | VVIP protection rules |
| `/api/ai/optimize` | GET | Run AI optimization |
| `/api/ai/generate-plan` | GET | Generate weekly block plan |
| `/api/defects` | GET | Defect list with filters |
| `/api/blocks` | GET/POST | Block planning |
| `/api/corridors` | GET | Corridor management |
| `/api/trains` | GET | Train schedule (COA) |

## Quick Start
```bash
# Install dependencies
pip install fastapi uvicorn

# Run server
python run_server.py

# Open browser
http://localhost:8000
```

## Project Structure
```
sih-railways/
├── backend/
│   └── main.py          # FastAPI application (all endpoints)
├── frontend/
│   └── index.html       # IRCTC-style UI
├── presentation/
│   └── SIH26027_RailBlockAI_FILLED.pptx
├── run_server.py         # Server entry point
├── fill_template.py      # PPTX template filler
└── railblock.db          # SQLite database (auto-created)
```

## System Architecture

```mermaid
graph TB
    subgraph Frontend["Frontend - IRCTC Style UI"]
        UI[Dashboard]
        BP[Block Planning Calendar]
        DT[Defect Tracking]
        CM[Corridor Management]
        AO[AI Optimizer]
        TS[Train Schedule]
        ME[Maintenance Engine]
        TL[Token Locks]
        CH[Crew HOER]
        EP[Emergency/VVIP]
    end

    subgraph Backend["Backend - FastAPI + SQLite"]
        API[REST API Layer]
        DB[(SQLite Database)]
        AI[AI Optimization Engine]
        ME2[Maintenance Categorizer]
        TK[Token Lock Controller]
        HC[HOER Compliance Checker]
        VP[VVIP Protection Engine]
    end

    subgraph DataSources["External Data"]
        TMS[TMS - Track Management]
        SMMS[SMMS - Safety Management]
        TDMS[TDMS - Traction Distribution]
        COA[COA - Controller of Operations]
        TT[Timetable / Train Schedule]
    end

    UI --> API
    BP --> API
    DT --> API
    CM --> API
    AO --> API
    TS --> API
    ME --> API
    TL --> API
    CH --> API
    EP --> API

    API --> DB
    API --> AI
    API --> ME2
    API --> TK
    API --> HC
    API --> VP

    TMS --> DB
    SMMS --> DB
    TDMS --> DB
    COA --> DB
    TT --> DB

    AI --> DB
    ME2 --> DB
    TK --> DB
    HC --> DB
    VP --> DB
```

## Block Planning Workflow

```mermaid
flowchart TD
    A[Defect Detected] --> B{Maintenance Type?}
    
    B -->|Routine| C[Schedule in Night Window<br>01:00 - 04:00]
    B -->|Fault| D[Allocate Dedicated Block<br>24h SLA]
    B -->|Urgent| E[Emergency Override<br>4h SLA]
    
    C --> F[AI Optimizer Checks<br>Multi-department Conflicts]
    D --> F
    E --> G[Cancel Lower Priority Blocks<br>Rescue Train Dispatch]
    
    F --> H{Single Line Section?}
    H -->|Yes| I[Acquire Directional Token<br>UP or DOWN Lock]
    H -->|No| J[Proceed to Block Grant]
    
    I --> K{Opposing Direction Locked?}
    K -->|No| L[Lock Token - Train Passes]
    K -->|Yes| M[Wait / Reschedule<br>Deadlock Prevented]
    
    L --> J
    G --> J
    
    J --> N[PTW Issued<br>Private Number Allocated]
    N --> O[Field Execution]
    O --> P[Block Released]
    P --> Q[Token Released<br>Audit Trail Updated]
    
    subgraph VVIP["VVIP Protection Layer"]
        R{Rajdhani/Special Train?}
        R -->|Yes| S[Auto-Reschedule Blocks<br>2h Window Protection]
        R -->|No| T[Normal Processing]
    end
    
    subgraph HOER["Crew Compliance Layer"]
        U{Crew Hours > 10h?}
        U -->|Yes| V[Block Assignment<br>Reassign to Fresh Crew]
        U -->|No| W[Allow Assignment]
    end
    
    F --> VVIP
    J --> HOER
```

## Data Flow Diagram

```mermaid
sequenceDiagram
    participant U as User/Controller
    participant F as Frontend
    participant A as FastAPI
    participant D as SQLite DB
    participant AI as AI Engine

    U->>F: Open Dashboard
    F->>A: GET /api/dashboard/stats
    A->>D: Query blocks, defects, corridors
    D-->>A: Return aggregated data
    A-->>F: JSON response
    F-->>U: Render dashboard

    U->>F: Generate AI Plan
    F->>A: GET /api/ai/generate-plan
    A->>D: Fetch corridors, trains, defects
    D-->>A: Raw data
    A->>AI: Run optimization algorithm
    AI-->>A: Optimized block schedule
    A->>D: Insert planned blocks
    A-->>F: Plan response
    F-->>U: Calendar updated

    U->>F: Check Token Lock
    F->>A: GET /api/token/locks
    A->>D: Query token_locks
    D-->>A: Token status
    A-->>F: UP/DOWN lock status
    F-->>U: Visual lock indicators

    U->>F: Check Crew HOER
    F->>A: GET /api/crew/duty
    A->>D: Query crew_duty
    D-->>A: Hours worked
    A->>AI: Calculate HOER compliance
    AI-->>A: Violation/at-risk flags
    A-->>F: Crew status
    F-->>U: Violation alerts
```

## License
SIH 2026 Submission
