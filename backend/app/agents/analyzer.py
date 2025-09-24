import json
from pathlib import Path
from typing import Dict, List

class AnalyzerAgent:
	def __init__(self, reports_dir: str):
		self.reports_dir = Path(reports_dir)

	def analyze_run(self, run_id: str, artifacts_dir: str) -> Dict:
		art_dir = Path(artifacts_dir) / run_id
		results_file = art_dir / "results.json"
		if not results_file.exists():
			return {"run_id": run_id, "summary": {"total": 0}, "tests": []}
		all_results: List[dict] = json.loads(results_file.read_text())
		# Group by case_id
		by_case: Dict[str, List[dict]] = {}
		for r in all_results:
			by_case.setdefault(r["case_id"], []).append(r)
		report_tests: List[dict] = []
		for case_id, runs in by_case.items():
			statuses = [r["result"]["status"] for r in runs]
			pass_count = statuses.count("completed")
			error_count = statuses.count("error")
			flaky = pass_count > 0 and error_count > 0
			verdict = "pass" if error_count == 0 else ("flaky" if flaky else "fail")
			artifacts = {r["browser"]: r.get("artifacts", {}) for r in runs}
			report_tests.append({
				"case_id": case_id,
				"runs": runs,
				"verdict": verdict,
				"evidence": artifacts,
				"reproducibility": {
					"attempts": len(runs),
					"successes": pass_count,
					"consistency": round(pass_count / max(1, len(runs)), 2),
				},
				"triage_notes": "Errors observed" if error_count else "No errors",
			})
		summary = {
			"total": len(report_tests),
			"pass": sum(1 for t in report_tests if t["verdict"] == "pass"),
			"fail": sum(1 for t in report_tests if t["verdict"] == "fail"),
			"flaky": sum(1 for t in report_tests if t["verdict"] == "flaky"),
		}
		return {"run_id": run_id, "summary": summary, "tests": report_tests}
