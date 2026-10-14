"""Frontend request-ordering and state-ownership tests.

Runs headless Chrome against frontend/test_runner.html to verify:
1. Submit A then B; B finishes first, A finishes second -> only B displayed
2. Repeat with A failing after B succeeds -> only B displayed, error banner hidden
3. B fails after A pending -> B error displayed, A claims hidden
4. Try Again action recovery -> routes through sequence protection, renders on success
5. Concurrent loading ownership -> only active submission controls loading state
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
import pytest

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def _find_browser() -> str | None:
    for path in CHROME_PATHS:
        if Path(path).is_file():
            return path
    return None


@pytest.mark.anyio
async def test_frontend_request_ordering_in_browser():
    browser = _find_browser()
    if not browser:
        pytest.skip("Neither Chrome nor Edge found on host.")

    runner_html = (
        Path(__file__).resolve().parent.parent.parent
        / "frontend"
        / "test_runner.html"
    )
    assert runner_html.is_file(), f"Runner not found: {runner_html}"

    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--allow-file-access-from-files",
        "--virtual-time-budget=5000",
        "--dump-dom",
        str(runner_html),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    stdout = result.stdout
    match = re.search(r'<div id="test-report"[^>]*>(.*?)</div>', stdout, re.DOTALL)
    assert match is not None, f"Could not find #test-report in DOM output: {stdout[:500]}"
    report_text = match.group(1)
    print("\n--- FRONTEND TEST REPORT ---")
    print(report_text)
    print("--- END FRONTEND TEST REPORT ---\n")

    # Check for overall success marker
    assert "ALL TESTS PASSED" in report_text, f"Frontend tests failed:\n{report_text}"
    assert "FAIL:" not in report_text, f"Frontend test assertion failed:\n{report_text}"
