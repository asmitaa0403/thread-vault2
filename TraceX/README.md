# threadVault — Investigator Assistance Prototype

threadVault is a hackathon prototype for the Smart India Hackathon (SIH 2026) demonstrating an investigator-assistance platform that ingests synthetic law-enforcement-like records and helps discover relationships between entities.

Important: This repository contains only fictional synthetic data for demonstration and educational purposes. Do NOT use real police, personal, or government data.

## SIH 2026 Context
Project: threadVault — AI-Powered Criminal Network Analysis System (Prototype for SIH26189, Ministry of Home Affairs)

## Current Prototype Scope (Phase 0)
- Project scaffolding and Streamlit UI skeleton
- Placeholder demo officer login and case selector
- UI placeholders for KPIs, interactive graph, entity details, suspicious patterns, timeline, and audit log

Future phases will implement data ingestion, NLP entity extraction, entity resolution, graph construction and analysis, deterministic anomaly detection with explainability, and a tamper-evident audit log.

## Technology Stack
- Python 3.10
- Streamlit
- pandas
- spaCy
- NetworkX
- PyVis
- Plotly

## Installation
1. Create and activate a Python 3.10 virtual environment:

Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install the spaCy English model (not included in `requirements.txt`):
```bash
python -m spacy download en_core_web_sm
```

## Run the Streamlit app
```bash
streamlit run app.py
```

## Notes
- This is a hackathon prototype. All automated flags are investigative leads and require human review.
- The repository intentionally avoids external APIs and does not store or process real personal or law-enforcement data.
