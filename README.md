# Multi-Agent Game Tester POC

Targets `https://play.ezygamers.com/` with planning, ranking, execution (Playwright), analysis, and reporting via FastAPI backend and minimal frontend.

## Quick Start

1. Python 3.10+
2. Install deps:

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
- Open `frontend/index.html` in a browser, or serve statically:
```bash
python -m http.server 3000 -d frontend
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
