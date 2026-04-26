# Agent-Driven Protocol Analysis

> **Multi-agent, evidence-bound, online-adaptive analysis framework for network protocols.**
> 
> This project is a prototype for a multi-agent protocol analysis system, capable of transforming documentation, session traces, and seeds into structured protocol models with full evidence chains. It currently supports **FTP, SMTP, RTSP, and HTTP**.

---

## 🏗️ Architecture

The system follows an "Agent-First" pipeline where analysis tasks are delegated to specialized agents communicating via structured function calling.

```
┌─────────────────────────────────────────────────────┐
│                    WebUI (React)                     │
│  Dashboard │ StateMachine │ Evidence │ Probes │ Msg  │
├─────────────────────────────────────────────────────┤
│                  FastAPI Backend                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │Spec Agent│ │Trace Agent│ │ Verifier │ │Probe   │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
│  ┌──────────────────────────────────────────────────┐│
│  │          Protocol Adapter Registry                ││
│  │      (FTP │ SMTP │ RTSP │ HTTP)                  ││
│  └──────────────────────────────────────────────────┘│
│  ┌──────────────────────────────────────────────────┐│
│  │          SQLite + Protocol Model Manager         ││
│  └──────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

### 🔬 Supported Agents

| Agent | Role | Source |
|-------|------|--------|
| **Spec Agent** | Extracts message types, fields, and ordering rules from documentation. | `spec_agent_service.py` |
| **Trace Agent** | Recovers states and transitions from session traces and observations. | `trace_agent_service.py` |
| **Verifier** | Binds evidence to claims, computes confidence scores, and flags disputes. | `verifier_service.py` |
| **Probe Agent** | Executes online probes against live servers to verify disputed claims. | `probe_service.py` |

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11+
- Node.js 18+
- Active LLM Provider (OpenAI/Gemini compatible API)

### 2. Setup

```bash
# Clone and enter
cd Agent-Driven-Protocol-Analysis

# Backend Setup
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env # Set your LLM API Key here

# Frontend Setup
cd ../frontend
npm install
```

### 3. Run Analysis Pipeline (CLI)

You can run the full analysis for any supported protocol using the provided scripts:

```bash
# 1. Start a local protocol server (e.g., FTP)
python3 scripts/start_ftp_server.py

# 2. Run the full analysis pipeline
python3 scripts/run_full_analysis.py FTP
```

### 4. Launch the Web Interface

```bash
# Terminal 1: Backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) to view the Dashboard and State Machine.

---

## 🌐 Multi-Protocol Support

The system uses a `ProtocolAdapter` abstraction to handle diverse text-based protocols.

| Protocol | Status | Features | Data Sources |
|:---:|:---:|---|---|
| **FTP** | 🌟 High | Full states, transitions, and live probes | doc, 10 sessions, 39 seeds |
| **SMTP** | ✅ Med-High | Core auth and mail flow recovery | doc, 5 sessions, 5 seeds |
| **RTSP** | 🧪 Medium | Header-aware parsing, session flow | doc, 3 sessions, 3 seeds |
| **HTTP** | 🧪 Medium | Request/Response pattern recognition | doc, 3 sessions, 3 seeds |

---

## 📊 Evaluation & Artifacts

The system produces several structured artifacts for every run, located in `data/outputs/`:

- **`evaluation_report.json`**: Summary of agent performance and coverage.
- **`protocol_schema.json`**: Structural model (Message Types + Field Constraints).
- **`multi_protocol_comparison.json`**: Side-by-side metrics for all analyzed protocols.
- **`regression_report.json`**: Stability metrics across multiple pipeline iterations.

---

## 📂 Project Structure

```bash
backend/
  app/
    api/          # FastAPI endpoints
    services/     # Core Agent & Pipeline logic
    protocols/    # Protocol-specific adapters (FTP, SMTP, etc.)
    core/         # Database and LLM client
  main.py         # Entry point
frontend/
  src/
    pages/        # Dashboard, State Machine, Evidence Chain, etc.
    api/          # Frontend client
data/
  docs/           # Protocol documentation summaries
  traces/         # Session traces and ProFuzzBench raw data
  outputs/        # JSON artifacts and evaluation results
scripts/          # Server simulators and analysis entry points
```

---

## 🎓 Project Identity

This project is a **"Run-able, Explain-able, and Show-able"** Multi-Agent prototype. It prioritizes:
- **Agent-First Analysis**: The model is built via tool calls, not hard-coded rules.
- **Evidence Binding**: Every transition and invariant is backed by documented or observed snippets.
- **Interactive Visualization**: A premium React dashboard for exploring complex protocol states.

*Developed as part of the Multi-Agent Protocol Analysis Research Project.*
