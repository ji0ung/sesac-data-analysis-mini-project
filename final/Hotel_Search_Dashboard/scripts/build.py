#!/usr/bin/env python3
"""Bundle editable sources into one offline HTML file. No third-party dependencies."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]

def render():
    page = (ROOT / "src/dashboard.html").read_text(encoding="utf-8")
    css = (ROOT / "src/dashboard.css").read_text(encoding="utf-8")
    code = (ROOT / "src/dashboard.js").read_text(encoding="utf-8")
    data = json.loads((ROOT / "data/dashboard_slices.json").read_text(encoding="utf-8"))
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    assert code.count("{{DATA_PACK}}") == 1
    code = code.replace("{{DATA_PACK}}", payload)
    values = {"DASHBOARD_CSS": css, "DASHBOARD_JS": code}
    for name in ("simulation_scope", "simulation_calibration", "simulation_impacts", "research", "survey", "topic", "team", "intent", "hypotheses", "lessons", "augmentation", "limitations", "optimization"):
        values["SLIDE_" + name.upper()] = (ROOT / f"slides/{name}.html").read_text(encoding="utf-8")
    for key, value in values.items():
        token = "{{" + key + "}}"
        assert page.count(token) == 1, f"Expected exactly one {token}"
        page = page.replace(token, value)
    return page

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if index.html differs from sources")
    args = parser.parse_args()
    output = ROOT / "index.html"
    content = render()
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != content:
            sys.exit("index.html is stale. Run scripts/build.py and commit the rebuilt file.")
        print("PASS: index.html matches source files")
    else:
        output.write_text(content, encoding="utf-8")
        print(f"Built {output}")
