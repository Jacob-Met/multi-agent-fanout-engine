"""Independent native CLI and installed-browser receiving from a frozen oracle."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import time
import traceback


def pin(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def inventory(root):
    return {p.relative_to(root).as_posix(): pin(p) for p in sorted(root.rglob("*")) if p.is_file()}


def display(text):
    return "".join("\\u%04x" % ord(c) if (ord(c) < 32 and c not in "\t\n\r") or 127 <= ord(c) <= 159 else c
                   for c in text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--oracle", required=True, type=Path)
    parser.add_argument("--browser", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    candidate, oracle, out = args.candidate.resolve(), args.oracle.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / "streams").mkdir()
    report = {"schema": 1, "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "platform": platform.platform(), "python": sys.version, "python_executable": sys.executable,
              "candidate": str(candidate), "oracle": str(oracle), "browser_path": str(args.browser),
              "checks": [], "processes": [], "browser_courses": [], "qualification": "pending"}
    source_before, oracle_before = inventory(candidate), inventory(oracle)
    report["source_before"], report["oracle_before"] = source_before, oracle_before
    expected_bytes = (oracle / "expected.json").read_bytes()
    expected = json.loads(expected_bytes)
    anchors = json.loads((oracle / "expectations.json").read_text(encoding="utf-8"))
    database = next(oracle.glob("*.sqlite3"))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(candidate))
    sequence = 0

    def check(name, condition, detail=None):
        entry = {"name": name, "passed": bool(condition)}
        if detail is not None:
            entry["detail"] = detail
        report["checks"].append(entry)
        if not condition:
            raise ValueError(name)

    def run(name, extra, code, output=None, optimized=False):
        nonlocal sequence
        sequence += 1
        command = [sys.executable] + (["-O"] if optimized else []) + ["-B", "-m", "fanout_engine.review", *extra]
        proc = subprocess.run(command, cwd=candidate, env=env, capture_output=True, timeout=20)
        stem = "%02d-%s" % (sequence, name)
        (out / "streams" / (stem + ".stdout")).write_bytes(proc.stdout)
        (out / "streams" / (stem + ".stderr")).write_bytes(proc.stderr)
        report["processes"].append({"name": name, "command": command, "exit": proc.returncode,
                                    "stdout": stem + ".stdout", "stderr": stem + ".stderr"})
        check(name + ": exit", proc.returncode == code, {"expected": code, "actual": proc.returncode})
        check(name + ": stdout empty", proc.stdout == b"" or name == "help")
        if code == 0 and name != "help":
            check(name + ": stderr empty", proc.stderr == b"")
            check(name + ": complete output", output is not None and output.is_file() and output.stat().st_size > 100)
        elif code != 0:
            check(name + ": diagnostic", bool(proc.stderr) and b"Traceback" not in proc.stderr)
        return proc

    try:
        common = ["--database", str(database), "--project", anchors["project"]]
        html = out / "received # % λ.html"
        run("normal", common + ["--output", str(html)], 0, html)
        optimized = out / "optimized.html"
        run("optimized", common + ["--output", str(optimized)], 0, optimized, True)
        check("normal and -O exact HTML", html.read_bytes() == optimized.read_bytes())
        before_output = pin(html)
        run("occupied-output", common + ["--output", str(html)], 1)
        check("occupied output preserved", pin(html) == before_output)
        run("database-output", common + ["--output", str(database)], 1)
        sidecar = Path(str(database) + "-wal")
        check("sidecar absent initially", not sidecar.exists())
        run("reserved-sidecar", common + ["--output", str(sidecar)], 1)
        check("sidecar not created", not sidecar.exists())
        absent = out / "absent-project.html"
        run("absent-project", ["--database", str(database), "--project", "absent", "--output", str(absent)], 3)
        check("absent project publishes nothing", not absent.exists())
        bad = out / "bad.sqlite3"
        shutil.copyfile(database, bad)
        with sqlite3.connect(bad) as db:
            db.execute("UPDATE parts SET evidence_json='{' WHERE part_id='c_ready_child'")
        bad_pin = pin(bad)
        bad_html = out / "bad.html"
        run("late-malformed", ["--database", str(bad), "--project", anchors["project"], "--output", str(bad_html)], 2)
        check("late bad record leaves no partial HTML", not bad_html.exists())
        check("late bad input preserved", pin(bad) == bad_pin)
        recovery = out / "recovery.html"
        run("recovery", common + ["--output", str(recovery)], 0, recovery)
        check("recovery HTML exact", recovery.read_bytes() == html.read_bytes())
        run("help", ["--help"], 0)

        # Import the installed automation library only after real CLI receiving.
        from playwright.sync_api import sync_playwright
        requests = []
        console_errors = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=str(args.browser), headless=True,
                args=["--disable-background-networking", "--no-first-run", "--disable-component-update"])
            report["browser_version"] = browser.version
            try:
                context = browser.new_context(viewport={"width": 1440, "height": 1100},
                                              accept_downloads=True, offline=True)
                context.on("request", lambda request: requests.append(request.url))
                page = context.new_page()
                page.on("pageerror", lambda error: console_errors.append(str(error)))
                page.goto(html.as_uri(), wait_until="load", timeout=15000)
                page.screenshot(path=str(out / "desktop.png"), full_page=False)
                body = page.locator("body").text_content()
                check("page has exact project identity", anchors["project"] in body)
                check("page has exact native plan digest", expected["plan_digest"] in body)
                check("full literal Unicode/control instruction", display(anchors["literal_instruction"]) in body)
                check("literal markup did not become an element", "bold?" not in page.locator("b").all_text_contents()
                      and "evidence" not in page.locator("em").all_text_contents())
                check("evidence locator remains visible text", display(anchors["evidence"]["locator"]) in body)
                check("evidence finding remains visible text", display(anchors["evidence"]["finding"]) in body)
                for state in anchors["counts"]:
                    check("recorded state visible: " + state, state in body)
                check("page has no scripts", page.locator("script").count() == 0)
                hrefs = page.locator("a").evaluate_all("els => els.map(e => e.getAttribute('href'))")
                check("references are not external links", all(h and (h.startswith("#") or h.startswith("data:")) for h in hrefs))
                nav = page.locator("table a[href^='#']").evaluate_all(
                    "els => els.map(e => ({text:e.textContent.trim(),href:e.getAttribute('href')}))")
                own_nav = [x for x in nav if x["text"] in anchors["part_order"]]
                check("linked table retains complete authored order", [x["text"] for x in own_nav] == anchors["part_order"])
                for link in own_nav:
                    check("navigation target exists: " + link["text"],
                          page.locator("[id]").evaluate_all("(els, id) => els.some(e=>e.id===id)", link["href"][1:]))
                panels = page.locator("details").filter(has=page.get_by_text("Complete recorded part", exact=True))
                check("one full-object disclosure per part", panels.count() == len(expected["parts"]))
                for i, wanted in enumerate(expected["parts"]):
                    panel = panels.nth(i)
                    summary = panel.locator("summary")
                    check("disclosure is initially closed: " + wanted["id"], not panel.evaluate("e=>e.open"))
                    summary.focus()
                    summary.press("Enter")
                    check("keyboard disclosure opens: " + wanted["id"], panel.evaluate("e=>e.open"))
                    text = panel.inner_text()
                    start = text.find("{")
                    check("full native object: " + wanted["id"], start >= 0 and json.loads(text[start:]) == wanted)
                page.locator("table a[href^='#']").filter(has_text=anchors["part_order"][-1]).first.click()
                check("native fragment navigation", page.url.endswith(own_nav[-1]["href"]))
                with page.expect_download(timeout=10000) as pending:
                    page.get_by_role("link", name="Download exact inspection JSON", exact=True).click()
                download = pending.value
                download.save_as(str(out / "browser-download.json"))
                check("actual browser download is exact native UTF-8 plus LF", (out / "browser-download.json").read_bytes() == expected_bytes)
                page.set_viewport_size({"width": 390, "height": 844})
                page.goto(html.as_uri(), wait_until="load", timeout=15000)
                page.screenshot(path=str(out / "narrow.png"), full_page=False)
                report["narrow_viewport"] = page.evaluate("({width:innerWidth,scrollWidth:document.documentElement.scrollWidth})")
                moved = out / "relocated # % 雪"
                moved.mkdir()
                relocated = moved / "standalone.html"
                shutil.copyfile(html, relocated)
                page.close()
                page = context.new_page()
                page.goto(relocated.as_uri(), wait_until="load", timeout=15000)
                check("relocated standalone page reopens unchanged", page.locator("body").text_content() == body)
                check("no document HTTP requests while offline", not any(x.startswith(("http:", "https:")) for x in requests))
                check("no page JavaScript errors", not console_errors)
                report["browser_requests"] = requests
                report["page_errors"] = console_errors
                report["browser_courses"] = ["desktop", "all-keyboard-disclosures", "fragment-navigation",
                    "actual-data-download", "narrow-observation", "relocated-offline-reopen"]
                context.close()
            finally:
                browser.close()
        report["qualification"] = "ACCEPTED"
    except BaseException as error:
        report["qualification"] = "FAILED"
        report["error"] = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
    finally:
        report["source_after"], report["oracle_after"] = inventory(candidate), inventory(oracle)
        report["source_unchanged"] = source_before == report["source_after"]
        report["oracle_unchanged"] = oracle_before == report["oracle_after"]
        if not report["source_unchanged"] or not report["oracle_unchanged"]:
            report["qualification"] = "FAILED"
        report["passed_checks"] = sum(x["passed"] for x in report["checks"])
        report["failed_checks"] = sum(not x["passed"] for x in report["checks"])
        report["finished_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        (out / "receipt.json").write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: report[k] for k in ["qualification", "passed_checks", "failed_checks", "source_unchanged", "oracle_unchanged"]}))
    return 0 if report["qualification"] == "ACCEPTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
