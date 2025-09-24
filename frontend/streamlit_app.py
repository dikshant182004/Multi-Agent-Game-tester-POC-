import os
import time
import json
import httpx
import streamlit as st
from urllib.parse import urljoin

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

st.set_page_config(page_title="Game Tester", layout="wide")
st.title("Multi-Agent Game Tester")

with st.sidebar:
	st.write("API & Options")
	api = st.text_input("FastAPI URL", value=API_BASE)
	max_cases = st.number_input("Max cases", min_value=1, max_value=10, value=3)
	browsers = st.multiselect("Browsers", options=["chromium", "firefox"], default=["chromium"])
	if st.button("Use Settings"):
		st.session_state["api"] = api
		st.session_state["max_cases"] = int(max_cases)
		st.session_state["browsers"] = list(browsers)
		st.success(f"Using {api} with {max_cases} cases on {browsers}")

api = st.session_state.get("api", api)
max_cases = st.session_state.get("max_cases", int(max_cases))
browsers = st.session_state.get("browsers", list(browsers))
client = httpx.Client(timeout=60.0)

col1, col2 = st.columns(2)
with col1:
	st.subheader("1) Plan")
	if st.button("Generate Test Plan"):
		resp = client.post(f"{api}/plan")
		if resp.status_code == 200:
			data = resp.json()
			st.session_state["plan"] = data
			st.success("Plan generated")
		else:
			st.error(resp.text)
	plan = st.session_state.get("plan")
	if plan:
		st.write("Top 10")
		st.json(plan.get("top10", []))

with col2:
	st.subheader("2) Execute")
	if st.button("Run Tests"):
		payload = {"max_cases": max_cases, "browsers": browsers}
		resp = client.post(f"{api}/execute", json=payload)
		if resp.status_code == 200:
			data = resp.json()
			st.session_state["run_id"] = data.get("run_id", "")
			st.success(f"Run started: {st.session_state['run_id']}")
		else:
			st.error(resp.text)
	run_id = st.session_state.get("run_id")
	if run_id:
		st.write(f"Run ID: {run_id}")
		status = client.get(f"{api}/status/{run_id}").json()
		st.write("Status:", status)
		artifacts_url = f"{api}/artifacts/{run_id}/"
		st.write("Artifacts root:", artifacts_url)

st.subheader("3) Analyze & Report")
col3, col4 = st.columns(2)
with col3:
	if st.button("Analyze Latest/Run ID"):
		run_id = st.session_state.get("run_id")
		resp = client.post(f"{api}/analyze", json={"run_id": run_id} if run_id else None)
		if resp.status_code == 200:
			st.success(f"Analyzed run {resp.json().get('run_id')}")
		else:
			st.error(resp.text)
with col4:
	if st.button("Load Report"):
		rep = client.get(f"{api}/report").json()
		st.session_state["report"] = rep
		report = rep.get("report", {})
		st.json(report)

report = st.session_state.get("report", {}).get("report")
if report:
	st.subheader("Summary")
	sumry = report.get("summary", {})
	st.metric("Total", sumry.get("total", 0))
	c1, c2, c3 = st.columns(3)
	c1.metric("Pass", sumry.get("pass", 0))
	c2.metric("Fail", sumry.get("fail", 0))
	c3.metric("Flaky", sumry.get("flaky", 0))
	st.subheader("Tests")
	for t in report.get("tests", [])[:10]:
		with st.expander(f"{t.get('case_id')} - {t.get('verdict')}"):
			st.json({k: t[k] for k in ['verdict','reproducibility','triage_notes']})
			for browser, art in (t.get("evidence") or {}).items():
				st.write(browser)
				img = art.get("screenshot")
				if img:
					# Convert windows path to FastAPI static URL
					parts = img.replace('\\', '/').split('/')
					idx = parts.index('artifacts') if 'artifacts' in parts else None
					if idx is not None:
						rel = '/'.join(parts[idx:])
						st.image(urljoin(api + '/', rel))
				logf = art.get("log")
				if logf:
					parts = logf.replace('\\', '/').split('/')
					idx = parts.index('artifacts') if 'artifacts' in parts else None
					if idx is not None:
						rel = '/'.join(parts[idx:])
						try:
							logtxt = client.get(urljoin(api + '/', rel)).text
							st.code(logtxt, language="json")
						except Exception:
							pass
