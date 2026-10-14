"""Post-v1 browser continuation; expected native values remain the frozen oracle."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import shutil
import sys
import traceback


def pin(path):
    b = path.read_bytes()
    return {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}


def inventory(root):
    return {p.relative_to(root).as_posix(): pin(p) for p in sorted(root.rglob("*")) if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["candidate", "oracle", "html", "browser", "out"]:
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=False)
    html, oracle, candidate = args.html.resolve(), args.oracle.resolve(), args.candidate.resolve()
    original_html = pin(html)
    before_source, before_oracle = inventory(candidate), inventory(oracle)
    expected_bytes = (oracle / "expected.json").read_bytes()
    expected = json.loads(expected_bytes)
    anchors = json.loads((oracle / "expectations.json").read_text(encoding="utf-8"))
    receipt = {"schema": 2, "scope": "Browser-only continuation after a documented v1 receiver presentation assumption.",
               "original_v1_preserved": True, "expectation_changes": False,
               "expected_profile": pin(oracle / "expected.json"), "html_before": original_html,
               "platform": platform.platform(), "python": sys.version, "browser": str(args.browser),
               "checks": [], "requests": [], "page_errors": [], "accepted": False}

    def check(name, value, detail=None):
        item = {"name": name, "passed": bool(value)}
        if detail is not None:
            item["detail"] = detail
        receipt["checks"].append(item)
        if not value:
            raise ValueError(name)

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=str(args.browser), headless=True,
                args=["--disable-background-networking", "--no-first-run", "--disable-component-update"])
            receipt["browser_version"] = browser.version
            try:
                context = browser.new_context(viewport={"width": 1440, "height": 1100},
                                              accept_downloads=True, offline=True)
                context.on("request", lambda r: receipt["requests"].append(r.url))
                page = context.new_page()
                page.on("pageerror", lambda e: receipt["page_errors"].append(str(e)))
                page.goto(html.as_uri(), wait_until="load", timeout=15000)
                body = page.locator("body").text_content()
                (root / "desktop-body.txt").write_text(body, encoding="utf-8", newline="")
                page.screenshot(path=str(root / "desktop.png"), full_page=False)
                counts = page.locator(".count").evaluate_all(
                    "els => Object.fromEntries(els.map(e=>[e.querySelector('span').textContent,Number(e.querySelector('strong').textContent)]))")
                check("visible complete native counts", counts == anchors["counts"], counts)
                ready = json.loads(page.get_by_text("Queued and dependency-ready IDs", exact=True).evaluate(
                    "e=>e.nextElementSibling.textContent"))
                blocked = json.loads(page.get_by_text("Blocked queued IDs", exact=True).evaluate(
                    "e=>e.nextElementSibling.textContent"))
                check("visible ready IDs", ready == anchors["ready"], ready)
                check("visible blocked IDs", blocked == anchors["blocked"], blocked)
                check("no script elements", page.locator("script").count() == 0)
                hrefs = page.locator("a").evaluate_all("es=>es.map(e=>e.getAttribute('href'))")
                check("no external links", all(x and x.startswith(("#", "data:")) for x in hrefs))
                articles = page.locator("article")
                check("one authored part article each", articles.count() == len(expected["parts"]))
                visible_fields = {
                    "Tags": "tags", "Declared dependencies": "depends_on", "Direct unmet dependencies": "unmet_dependencies",
                    "Worker reference": "worker_id", "Task reference": "task_id", "Recorded route": "route",
                    "Artifact reference": "artifact_ref", "Recorded evidence": "evidence",
                    "Recorded update timestamp": "updated_at", "Idempotency key": "idempotency_key",
                }
                for i, wanted in enumerate(expected["parts"]):
                    article = articles.nth(i)
                    check("article identity/order: " + wanted["id"], article.locator("h3").inner_text() == wanted["id"])
                    for label, key in visible_fields.items():
                        visible = article.get_by_text(label, exact=True).evaluate("e=>e.nextElementSibling.textContent")
                        check("visible " + key + ": " + wanted["id"], json.loads(visible) == wanted[key])
                nav = page.locator("table a[href^='#']").evaluate_all(
                    "es=>es.map(e=>({text:e.textContent.trim(),href:e.getAttribute('href')}))")
                own_nav = [x for x in nav if x["text"] in anchors["part_order"]]
                check("linked table retains authored order", [x["text"] for x in own_nav] == anchors["part_order"])
                panels = page.locator("details").filter(has=page.get_by_text("Complete recorded part", exact=True))
                check("full-object disclosure count", panels.count() == len(expected["parts"]))
                for i, wanted in enumerate(expected["parts"]):
                    panel = panels.nth(i)
                    check("initial disclosure closed: " + wanted["id"], not panel.evaluate("e=>e.open"))
                    summary = panel.locator("summary")
                    summary.focus()
                    summary.press("Enter")
                    check("keyboard disclosure open: " + wanted["id"], panel.evaluate("e=>e.open"))
                    text = panel.inner_text()
                    pos = text.find("{")
                    check("full native object: " + wanted["id"], pos >= 0 and json.loads(text[pos:]) == wanted)
                page.locator("table a[href^='#']").filter(has_text=anchors["part_order"][-1]).first.click()
                check("native fragment navigation", page.url.endswith(own_nav[-1]["href"]))
                with page.expect_download(timeout=10000) as pending:
                    page.get_by_role("link", name="Download exact inspection JSON", exact=True).click()
                download = pending.value
                download.save_as(str(root / "browser-download.json"))
                check("browser-downloaded native bytes exact", (root / "browser-download.json").read_bytes() == expected_bytes)
                page.set_viewport_size({"width": 390, "height": 844})
                page.goto(html.as_uri(), wait_until="load", timeout=15000)
                page.screenshot(path=str(root / "narrow.png"), full_page=False)
                receipt["narrow_observation"] = page.evaluate("({width:innerWidth,scrollWidth:document.documentElement.scrollWidth})")
                moved = root / "relocated # % 雪"
                moved.mkdir()
                relocated = moved / "standalone.html"
                shutil.copyfile(html, relocated)
                page.close()
                page = context.new_page()
                page.on("pageerror", lambda e: receipt["page_errors"].append(str(e)))
                page.goto(relocated.as_uri(), wait_until="load", timeout=15000)
                check("relocated offline page text identical", page.locator("body").text_content() == body)
                check("no document HTTP requests", not any(x.startswith(("http:", "https:")) for x in receipt["requests"]))
                check("no errors on either observed page", not receipt["page_errors"])
                context.close()
            finally:
                browser.close()
        receipt["accepted"] = True
    except BaseException as error:
        receipt["error"] = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
    finally:
        receipt["source_before"], receipt["source_after"] = before_source, inventory(candidate)
        receipt["oracle_before"], receipt["oracle_after"] = before_oracle, inventory(oracle)
        receipt["html_after"] = pin(html)
        receipt["source_unchanged"] = receipt["source_before"] == receipt["source_after"]
        receipt["oracle_unchanged"] = receipt["oracle_before"] == receipt["oracle_after"]
        receipt["html_unchanged"] = receipt["html_before"] == receipt["html_after"]
        receipt["accepted"] = receipt["accepted"] and all(receipt[k] for k in ["source_unchanged", "oracle_unchanged", "html_unchanged"])
        receipt["passed_checks"] = sum(x["passed"] for x in receipt["checks"])
        receipt["failed_checks"] = sum(not x["passed"] for x in receipt["checks"])
        (root / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: receipt[k] for k in ["accepted", "passed_checks", "failed_checks", "source_unchanged", "oracle_unchanged", "html_unchanged"]}))
    return 0 if receipt["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
