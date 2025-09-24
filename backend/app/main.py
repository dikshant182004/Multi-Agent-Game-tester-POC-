import os
import json
import threading
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional

from .agents.planner import PlannerAgent
from .agents.ranker import RankerAgent
from .agents.executor import OrchestratorAgent
from .agents.analyzer import AnalyzerAgent

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
ARTIFACTS_DIR = BASE_DIR / "artifacts"

for d in [DATA_DIR, REPORTS_DIR, ARTIFACTS_DIR]:
    os.makedirs(d, exist_ok=True)

app = FastAPI(title="Multi-Agent Game Tester POC")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static mounts for artifacts and reports
app.mount("/artifacts", StaticFiles(directory=str(ARTIFACTS_DIR)), name="artifacts")
app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR)), name="reports")

class PlanResponse(BaseModel):
    candidates: list
    top10: list

class ExecuteRequest(BaseModel):
    max_cases: Optional[int] = None
    browsers: Optional[List[str]] = None

class ExecuteResponse(BaseModel):
    message: str
    run_id: str

class ReportResponse(BaseModel):
    report: dict

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/plan", response_model=PlanResponse)
def plan():
    # Load OpenAI API key from environment variable
    openai_api_key = os.getenv("OPENAI_API_KEY")
    # Optionally, enable LLM usage via environment variable
    use_llm = os.getenv("USE_LLM", "false").lower() == "true"
    
    # Initialize PlannerAgent with API key and LLM usage flag
    planner = PlannerAgent(openai_api_key=openai_api_key, use_llm=use_llm)
    candidates = planner.generate_tests(min_count=20)
    ranker = RankerAgent()
    scored = ranker.rank(candidates)
    top10 = [t for t, _ in scored[:10]]
    (DATA_DIR / "plan.json").write_text(json.dumps({"candidates": candidates}, indent=2))
    (DATA_DIR / "top10.json").write_text(json.dumps({"top10": top10}, indent=2))
    return {"candidates": candidates, "top10": top10}

_status: dict[str, dict] = {}

def _background_execute(run_id: str, test_cases: list, max_cases: Optional[int], browsers: Optional[List[str]]):
    try:
        _status[run_id] = {"state": "running"}
        orchestrator = OrchestratorAgent(artifacts_dir=str(ARTIFACTS_DIR), browsers=browsers, max_cases=max_cases)
        orchestrator.run_tests(test_cases, run_id=run_id)
        analyzer = AnalyzerAgent(reports_dir=str(REPORTS_DIR))
        report = analyzer.analyze_run(run_id, artifacts_dir=str(ARTIFACTS_DIR))
        (REPORTS_DIR / f"report-{run_id}.json").write_text(json.dumps(report, indent=2))
        (REPORTS_DIR / "report.json").write_text(json.dumps(report, indent=2))
        _status[run_id] = {"state": "done"}
    except Exception as e:
        _status[run_id] = {"state": "error", "detail": str(e)}

@app.post("/execute", response_model=ExecuteResponse)
def execute(payload: ExecuteRequest | None = None):
    plan_path = DATA_DIR / "top10.json"
    if not plan_path.exists():
        raise HTTPException(status_code=400, detail="No plan found. Run /plan first.")
    try:
        plan = json.loads(plan_path.read_text())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid plan file: {e}")
    test_cases = plan.get("top10", [])
    if not isinstance(test_cases, list) or not test_cases:
        raise HTTPException(status_code=400, detail="Plan has no test cases.")
    # Kick off background execution with options
    run_id = os.getenv("RUN_ID_OVERRIDE") or __import__("time").strftime("%Y%m%d-%H%M%S")
    max_cases = payload.max_cases if payload else None
    browsers = payload.browsers if payload else None
    threading.Thread(target=_background_execute, args=(run_id, test_cases, max_cases, browsers), daemon=True).start()
    return {"message": "Execution started.", "run_id": run_id}

@app.get("/status/{run_id}")
def status(run_id: str):
    st = _status.get(run_id)
    if not st:
        return {"run_id": run_id, "state": "unknown"}
    return {"run_id": run_id, **st}

@app.post("/analyze")
def analyze(run_id: str | None = None):
    # Analyze a given run_id or latest run under artifacts
    if not run_id:
        # pick latest directory in artifacts
        runs = sorted([p for p in ARTIFACTS_DIR.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
        if not runs:
            raise HTTPException(status_code=400, detail="No runs found to analyze.")
        run_id = runs[0].name
    analyzer = AnalyzerAgent(reports_dir=str(REPORTS_DIR))
    report = analyzer.analyze_run(run_id, artifacts_dir=str(ARTIFACTS_DIR))
    (REPORTS_DIR / f"report-{run_id}.json").write_text(json.dumps(report, indent=2))
    (REPORTS_DIR / "report.json").write_text(json.dumps(report, indent=2))
    return {"message": "Analysis complete", "run_id": run_id}

@app.get("/report", response_model=ReportResponse)
def report():
    report_file = REPORTS_DIR / "report.json"
    if report_file.exists():
        return {"report": json.loads(report_file.read_text())}
    return {"report": {"message": "No report yet. Run /plan and /execute."}}