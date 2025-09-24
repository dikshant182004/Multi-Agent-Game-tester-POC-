# Multi-Agent Game Tester POC

Targets `https://play.ezygamers.com/` with planning, ranking, execution (Playwright), analysis, and reporting via FastAPI backend and minimal frontend.

I have setup a sequential approach so executer agent may take some time and the test cases may fail because the game ui canvas was having some issue in navigating to new game button for every test case . Since its just for a poc i have not gone for much debugging and full agent execution ,a simple demo is depicted here.

## Quick Start

1. Python 3.10+
2. Install deps:

First make a Virtualenv using virtualenv venv and activate it then install the requirements there

```bash
pip install -r requirements.txt
python -m playwright install --with-deps
```

3. Run backend:

```bash
cd backend
python run.py
```

4. Open frontend:
I have used the streamlit for simple ui 
```bash
streamlit run streamlit_app.py
```

5. Workflow:
- Click "Generate Test Plan" (ensures >=20 tests; stores at `data/plan.json` and `data/top10.json`).
- Click "Run Tests" (executes top 10 on Playwright executors; artifacts under `artifacts/<run_id>/...`).
- Click "Refresh Report" (reads `reports/report.json`).

## OpenAI (optional)
If `OPENAI_API_KEY` is set, Planner uses LangChain+OpenAI to generate cases; otherwise falls back to heuristic generation.

## Artifacts
- `artifacts/<run_id>/<case_id>/<browser>/final.png` (screenshot)
- `dom.html` (DOM snapshot)
- `console.json` (console logs)
- `network.har` (HAR); `network.json` (simple list)
- `reports/report.json` (aggregated report)

## Demo Video Checklist
- Planner prints 20+ candidates
- Ranker shows top 10 selected
- Executor runs (show at least 3 for time)
- Report opens with evidence

## Notes
- This is a POC; selectors are heuristic and may need tuning for the target game UI.

