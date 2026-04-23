# Protocol Analysis System

> Multi-agent, evidence-bound, online-adaptive analysis framework for general network protocols.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                    WebUI (React)                     │
│  Dashboard │ StateMachine │ Messages │ Evidence │ Probe │
├─────────────────────────────────────────────────────┤
│                  FastAPI Backend                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │Spec Agent│ │Trace Agent│ │ Verifier │ │Probe   │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
│  ┌──────────────────────────────────────────────────┐│
│  │          Tool Functions (7 tools)                ││
│  │  extract_message_types · infer_candidate_states  ││
│  │  propose_transitions · score_evidence · ...      ││
│  └──────────────────────────────────────────────────┘│
│  ┌──────────────────────────────────────────────────┐│
│  │          SQLite + Protocol Model Manager         ││
│  └──────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- npm

### 1. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Config

```bash
cp .env.example .env
# Edit .env to set your OPENAI_API_KEY (optional for basic demo)
```

### 3. Import Demo Data

```bash
cd backend
python ../scripts/import_demo_data.py
```

### 4. Start Backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Backend API docs: http://localhost:8000/docs

### 5. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173

## 📋 Demo Workflow

1. Open Dashboard at http://localhost:5173
2. Click **Run Pipeline** to execute all 4 agents
3. Navigate to **State Machine** to see the FTP protocol state graph
4. Click edges to view evidence bindings
5. Check **Messages** for message types and invariants
6. Check **Evidence Chain** for full evidence trail
7. Check **Probe History** for online probe records

## 🧩 Project Structure

```
project/
  backend/
    app/
      api/          # FastAPI route handlers
      core/         # Config and database
      models/       # SQLModel domain models
      schemas/      # Pydantic request/response schemas
      services/     # Agent service implementations
      tools/        # Protocol tools and FTP parser
      tests/        # Unit tests
    main.py         # FastAPI entry point
    requirements.txt
  frontend/
    src/
      api/          # API client
      components/   # Layout components
      pages/        # Dashboard, StateMachine, Messages, Evidence, Probes
    package.json
  data/
    docs/           # Protocol documentation
    traces/         # Session trace samples
    outputs/        # Analysis outputs
  scripts/          # Data import and utility scripts
  Docs/             # Project documentation
```

## 🔬 Supported Agents

| Agent | Role |
|-------|------|
| **Spec Agent** | Extracts message types, fields, and ordering rules from protocol docs |
| **Trace Agent** | Recovers states and transitions from session traces |
| **Verifier** | Binds evidence to claims, computes confidence and status |
| **Probe Agent** | Generates discriminative probes for disputed/low-confidence claims |

## 📊 API Endpoints

- `POST /projects` — Create analysis project
- `POST /projects/{id}/import/doc` — Import protocol documentation
- `POST /projects/{id}/import/trace` — Import session traces
- `POST /projects/{id}/run/full-pipeline` — Run all agents
- `GET /projects/{id}/dashboard` — Get analysis stats
- `GET /projects/{id}/states` — List protocol states
- `GET /projects/{id}/transitions` — List transitions
- `GET /projects/{id}/evidence` — List evidence records
- `GET /projects/{id}/model/export` — Export full model JSON

Full API docs at http://localhost:8000/docs
