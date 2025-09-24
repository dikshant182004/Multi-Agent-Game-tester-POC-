import os
import json
import time
import uuid
from pathlib import Path
from typing import List, Dict, Optional

TARGET_URL = "https://play.ezygamers.com/"
NEW_GAME_XPATH = "xpath=/html/body/div[1]/div[4]/button[2]"
DEFAULT_NAV_TIMEOUT_MS = int(os.getenv("PAGE_NAV_TIMEOUT_MS", "15000"))
DEFAULT_ACTION_TIMEOUT_MS = int(os.getenv("PAGE_ACTION_TIMEOUT_MS", "10000"))

class ExecutorAgent:
	def __init__(self, browser_name: str, artifacts_dir: str):
		self.browser_name = browser_name
		self.artifacts_dir = Path(artifacts_dir)

	def run_test(self, test_case: dict, run_id: str) -> Dict:
		from playwright.sync_api import sync_playwright

		case_id = test_case.get("id", str(uuid.uuid4()))
		case_dir = self.artifacts_dir / run_id / case_id / self.browser_name
		os.makedirs(case_dir, exist_ok=True)

		console_logs: List[dict] = []
		network_events: List[dict] = []
		step_logs: List[dict] = []

		result = {"status": "unknown", "details": ""}

		with sync_playwright() as p:
			browser = None
			context = None
			page = None
			try:
				browser = getattr(p, self.browser_name).launch(headless=True)
				context = browser.new_context(record_har_path=str(case_dir / "network.har"))
				context.set_default_navigation_timeout(DEFAULT_NAV_TIMEOUT_MS)
				context.set_default_timeout(DEFAULT_ACTION_TIMEOUT_MS)
				page = context.new_page()

				def _on_console(msg):
					mtype = msg.type() if callable(getattr(msg, "type", None)) else getattr(msg, "type", None)
					mtext = msg.text() if callable(getattr(msg, "text", None)) else getattr(msg, "text", None)
					console_logs.append({"type": mtype, "text": mtext})

				page.on("console", _on_console)
				page.on("requestfinished", lambda request: network_events.append({"url": request.url}))

				# 1) Navigate
				page.goto(TARGET_URL, wait_until="load")
				self._log(step_logs, "navigate", "ok", TARGET_URL)

				# 2) Language selection (best-effort)
				self._select_language(page, step_logs)

				# 3) Click New Game (provided XPath first, with retries)
				if not self._start_new_game(page, step_logs):
					raise RuntimeError("start new game failed")

				# 4) Wait for board/grid with tiles
				if not self._wait_for_board(page, step_logs):
					raise RuntimeError("board not visible")

				# 5) Execute steps: choose any pair summing to 10 (prefer not 5+5)
				steps = test_case.get("steps", [])
				performed = False
				for s in steps:
					if s.startswith("click_adjacent_sum:") or s.startswith("click_two_tiles_sum"):
						performed = self._click_two_tiles_sum(page, 10, step_logs)
						break
				if not performed:
					performed = self._click_two_tiles_sum(page, 10, step_logs)
				if not performed:
					raise RuntimeError("no sum-10 pair found")

				result["status"] = "completed"
			except Exception as e:
				result["status"] = "error"
				result["details"] = str(e)
			finally:
				# artifacts before closing
				try:
					if page is not None:
						shot = case_dir / "final.png"
						try:
							page.screenshot(path=str(shot), full_page=True)
							self._log(step_logs, "screenshot", "ok", "full_page")
						except Exception:
							page.screenshot(path=str(shot))
							self._log(step_logs, "screenshot", "ok", "viewport")
						dom = case_dir / "dom.html"
						dom.write_text(page.content())
						self._log(step_logs, "dom", "ok")
				except Exception as ae:
					self._log(step_logs, "artifact", "error", str(ae))
				try:
					if context: context.close()
					if browser: browser.close()
				except Exception:
					pass

		(case_dir / "console.json").write_text(json.dumps(console_logs, indent=2))
		(case_dir / "network.json").write_text(json.dumps(network_events, indent=2))
		(case_dir / "log.json").write_text(json.dumps(step_logs, indent=2))

		return {
			"case_id": case_id,
			"browser": self.browser_name,
			"result": result,
			"artifacts": {
				"screenshot": str(case_dir / "final.png"),
				"dom": str(case_dir / "dom.html"),
				"console": str(case_dir / "console.json"),
				"network": str(case_dir / "network.har"),
				"log": str(case_dir / "log.json"),
			},
		}

	def _log(self, step_logs: List[dict], action: str, status: str, detail: Optional[str] = None):
		entry = {"ts": time.time(), "action": action, "status": status}
		if detail is not None:
			entry["detail"] = detail
		step_logs.append(entry)

	def _select_language(self, page, step_logs: List[dict]):
		# Best-effort: click English if visible, else try common select
		try:
			loc = page.get_by_text("English", exact=False)
			if loc and loc.count() > 0:
				loc.nth(0).click()
				self._log(step_logs, "select_language", "ok", "English")
				return
		except Exception as e:
			self._log(step_logs, "select_language", "error", str(e))
		try:
			sel = page.locator(".lang-select, select#language").first
			if sel and sel.count() > 0:
				sel.select_option(label="English")
				self._log(step_logs, "select_language", "ok", "select element")
				return
		except Exception as e:
			self._log(step_logs, "select_language", "error", str(e))

	def _start_new_game(self, page, step_logs: List[dict]) -> bool:
		# Try the provided absolute XPath first, with small retries
		for _ in range(5):
			try:
				loc = page.locator(NEW_GAME_XPATH).first
				if loc and loc.count() > 0:
					try: loc.wait_for(state="visible", timeout=1500)
					except Exception: pass
					loc.click()
					self._log(step_logs, "click_new_game", "ok", NEW_GAME_XPATH)
					return True
			except Exception as e:
				self._log(step_logs, "click_new_game", "error", str(e))
			try:
				page.wait_for_timeout(400)
			except Exception:
				pass
		# Fallbacks by text/role
		candidates = [
			"//button[contains(translate(., 'NEW GAME', 'new game'),'new game')]",
			"//button[contains(translate(., 'START', 'start'),'start')]",
			"button.start-btn",
			"button.btn-primary",
			"button[class*='start']",
		]
		for sel in candidates:
			try:
				loc = page.locator(sel).first
				if loc and loc.count() > 0:
					loc.click()
					self._log(step_logs, "click_new_game", "ok", sel)
					return True
			except Exception as e:
				self._log(step_logs, "click_new_game", "error", str(e))
		return False

	def _wait_for_board(self, page, step_logs: List[dict]) -> bool:
		selectors = [".game-board", ".puzzle-grid", "div.game-board", "div.puzzle-grid"]
		for sel in selectors:
			try:
				page.locator(sel).first.wait_for(state="visible", timeout=DEFAULT_ACTION_TIMEOUT_MS)
				tiles = page.locator(".tile, .cell.tile-number")
				if tiles.count() > 0:
					self._log(step_logs, "board", "ok", f"{sel} tiles={tiles.count()}")
					return True
			except Exception:
				pass
		self._log(step_logs, "board", "error", "not visible")
		return False

	def _click_two_tiles_sum(self, page, target_sum: int, step_logs: List[dict]) -> bool:
		# Prefer non 5+5; retry a couple times
		for attempt in range(3):
			pair = page.evaluate(
				"(sum) => {\n"
				"  const els = Array.from(document.querySelectorAll('.tile, .cell.tile-number'));\n"
				"  const vals = els.map((e,i) => ({i, v: parseInt(e.getAttribute('data-value') || e.textContent.trim())}));\n"
				"  const pref = [[6,4],[7,3],[8,2],[9,1],[5,5]];\n"
				"  for (const [a1,b1] of pref){\n"
				"    for (let a=0;a<vals.length;a++){ for (let b=a+1;b<vals.length;b++){\n"
				"      const A=vals[a], B=vals[b];\n"
				"      if (!Number.isFinite(A.v) || !Number.isFinite(B.v)) continue;\n"
				"      if (A.v + B.v !== sum) continue;\n"
				"      if ((A.v===a1 && B.v===b1) || (A.v===b1 && B.v===a1)) return [A.i,B.i];\n"
				"    }}\n"
				"  }\n"
				"  return null;\n"
				"}", target_sum
			)
			if pair and isinstance(pair, list) and len(pair) == 2:
				for idx in pair:
					page.locator(".tile, .cell.tile-number").nth(idx).click()
				self._log(step_logs, "click_two_tiles_sum", "ok", f"pair={pair}")
				return True
			# small wait and retry
			try: page.wait_for_timeout(300)
			except Exception: pass
		return False

class OrchestratorAgent:
	def __init__(self, artifacts_dir: str, browsers: List[str] | None = None, max_cases: int | None = None):
		self.artifacts_dir = Path(artifacts_dir)
		self.browsers = browsers or [b.strip() for b in os.getenv("TEST_BROWSERS", "chromium").split(",") if b.strip()]
		self.max_cases = max_cases or int(os.getenv("MAX_EXECUTE_CASES", "10"))

	def run_tests(self, test_cases: List[dict], run_id: str | None = None) -> str:
		run_id = run_id or (time.strftime("%Y%m%d-%H%M%S") + f"-{uuid.uuid4().hex[:6]}")
		run_dir = self.artifacts_dir / run_id
		os.makedirs(run_dir, exist_ok=True)
		cases = list(test_cases)[: self.max_cases]
		executors = [ExecutorAgent(browser, str(self.artifacts_dir)) for browser in self.browsers]
		results: List[dict] = []
		for case in cases:
			for ex in executors:
				res = ex.run_test(case, run_id)
				results.append(res)
		(run_dir / "results.json").write_text(json.dumps(results, indent=2))
		return run_id
