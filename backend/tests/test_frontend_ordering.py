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
    print(report_text.encode("ascii", errors="replace").decode("ascii"))
    print("--- END FRONTEND TEST REPORT ---\n")

    # Check for overall success marker
    assert "ALL TESTS PASSED" in report_text, f"Frontend tests failed:\n{report_text}"
    assert "FAIL:" not in report_text, f"Frontend test assertion failed:\n{report_text}"


def test_localstorage_persistence_static_contract():
    """Verify Milestone 4E static contracts in frontend/index.html and frontend/app.js."""
    project_root = Path(__file__).resolve().parent.parent.parent
    index_html_path = project_root / "frontend" / "index.html"
    app_js_path = project_root / "frontend" / "app.js"

    assert index_html_path.is_file(), f"Missing index.html at {index_html_path}"
    assert app_js_path.is_file(), f"Missing app.js at {app_js_path}"

    index_html = index_html_path.read_text(encoding="utf-8")
    app_js = app_js_path.read_text(encoding="utf-8")

    # 1. index.html contains id="btn-clear-workspace" inside #session-tabs-bar
    bar_start = index_html.find('id="session-tabs-bar"')
    assert bar_start != -1, "Could not find #session-tabs-bar in index.html"
    form_start = index_html.find('id="extraction-form"')
    assert form_start != -1 and form_start > bar_start, "Could not find #extraction-form following #session-tabs-bar"
    session_tabs_content = index_html[bar_start:form_start]
    assert 'id="btn-clear-workspace"' in session_tabs_content or "id='btn-clear-workspace'" in session_tabs_content, (
        "frontend/index.html does not contain id=\"btn-clear-workspace\" inside #session-tabs-bar"
    )

    # 2. app.js defines WORKSPACE_STORAGE_KEY = "scoopscope_workspace_v1", saveWorkspaceToStorage(), loadWorkspaceFromStorage(), clearWorkspace()
    assert 'WORKSPACE_STORAGE_KEY = "scoopscope_workspace_v1"' in app_js or "WORKSPACE_STORAGE_KEY = 'scoopscope_workspace_v1'" in app_js, (
        'frontend/app.js must define WORKSPACE_STORAGE_KEY = "scoopscope_workspace_v1"'
    )
    assert re.search(r'\bfunction\s+saveWorkspaceToStorage\b', app_js) or re.search(r'\bsaveWorkspaceToStorage\s*=', app_js), (
        "frontend/app.js must define saveWorkspaceToStorage()"
    )
    assert re.search(r'\bfunction\s+loadWorkspaceFromStorage\b', app_js) or re.search(r'\bloadWorkspaceFromStorage\s*=', app_js), (
        "frontend/app.js must define loadWorkspaceFromStorage()"
    )
    assert re.search(r'\bfunction\s+clearWorkspace\b', app_js) or re.search(r'\bclearWorkspace\s*=', app_js), (
        "frontend/app.js must define clearWorkspace()"
    )


@pytest.mark.anyio
async def test_localstorage_persistence_in_browser(tmp_path: Path):
    """Run headless Chrome against a persistence test harness to verify:
    1. Live persistence of multi-tab sessions, Cornell notes, selectedQuotes, and citation style.
    2. Reload restoration of tabs, sticky bar, evidence bank checkboxes, and APA works cited.
    3. Transient flag reset (isClarifying=false, isResearching=false, progress banner hidden).
    4. Graceful fallback on corrupt JSON.
    5. One-click Clear Workspace (#btn-clear-workspace) reset.
    """
    browser = _find_browser()
    if not browser:
        pytest.skip("Neither Chrome nor Edge found on host.")

    project_root = Path(__file__).resolve().parent.parent.parent
    app_js_uri = (project_root / "frontend" / "app.js").resolve().as_uri()
    style_css_uri = (project_root / "frontend" / "style.css").resolve().as_uri()

    runner_html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>ScoopScope Persistence Test Harness</title>
    <link rel="stylesheet" href="{style_css_uri}">
    <style>
        #test-report {{
            margin-top: 1rem;
            padding: 1rem;
            background: #111520;
            border: 1px solid #3ecfb4;
            border-radius: 8px;
            font-family: monospace;
            white-space: pre-wrap;
        }}
        .test-pass {{ color: #3ecfb4; }}
        .test-fail {{ color: #eb5757; }}
    </style>
</head>
<body>
    <div id="test-report">Initializing persistence tests...</div>

    <div class="app-container" style="opacity: 0.1; pointer-events: none;">
        <header class="app-header">
            <h1 class="logo-text">ScoopScope</h1>
        </header>

        <main class="main-content">
            <!-- Sticky Floating Inquiry Bar -->
            <div id="sticky-inquiry-bar" class="sticky-inquiry-bar hidden">
                <div class="sticky-inquiry-header">
                    <div class="sticky-inquiry-pill">
                        <span id="sticky-inquiry-text" class="sticky-inquiry-text">No active inquiry</span>
                    </div>
                    <button id="btn-sticky-edit" type="button" class="btn-sticky-edit">Edit ↑</button>
                </div>
                <div id="loading-progress-banner" class="loading-progress-banner hidden" role="status">
                    <span id="loading-progress-message" class="loading-progress-message">Loading…</span>
                </div>
            </div>

            <!-- Session Tabs Bar -->
            <div id="session-tabs-bar" class="session-tabs-bar hidden" role="tablist">
                <div id="session-tabs-list" class="session-tabs-list"></div>
                <button id="btn-new-session" type="button" class="btn-new-session">+ New</button>
                <button id="btn-clear-workspace" class="btn-clear-workspace" type="button">Clear Workspace</button>
            </div>

            <form id="extraction-form" class="input-card">
                <textarea id="input-text" class="form-textarea" rows="4"></textarea>
                <input id="claim-input" type="hidden" value="" />
                <span id="char-count">0</span>
                <input id="source-url" class="form-input" type="url" />
                <button id="submit-btn" type="submit" class="btn-primary">Clarify & Investigate</button>
            </form>

            <div id="error-banner" class="error-banner hidden">
                <strong id="error-title"></strong>
                <p id="error-detail"></p>
                <button id="error-retry" type="button">Try Again</button>
                <button id="error-dismiss">&times;</button>
            </div>

            <section id="clarification-section" class="clarification-card hidden">
                <span id="clarification-round-badge"></span>
                <h2 id="clarification-question"></h2>
                <div id="clarification-choices-group"></div>
                <input id="clarification-freetext" />
                <button id="clarification-submit-btn">Submit</button>
                <div id="clarification-broad-container" class="hidden">
                    <button id="btn-broad-inquiry">Broad</button>
                </div>
            </section>

            <section id="results-section" class="results-section hidden">
                <div id="confirmed-scope-card" class="confirmed-scope-card">
                    <span id="scope-purpose-badge"></span>
                    <input id="scope-question-input" type="text" />
                    <button id="scope-update-btn">Update</button>
                    <div id="unresolved-scope-container" class="hidden">
                        <ul id="unresolved-list"></ul>
                    </div>
                    <div id="limitation-note-banner" class="hidden">
                        <span id="limitation-note-text"></span>
                    </div>
                </div>
                <div class="results-header">
                    <span id="results-status"></span>
                </div>
                <blockquote id="submitted-text"></blockquote>
                <div id="submitted-url-row" class="hidden">
                    <a id="submitted-url"></a>
                </div>
                <div id="claims-list"></div>
            </section>

            <section id="report-studio-section" class="hidden"></section>
        </main>
    </div>

    <script src="{app_js_uri}"></script>

    <script>
    (async function() {{
        const report = document.getElementById("test-report");
        const logs = [];
        let passed = 0;

        function log(msg) {{
            logs.push(msg);
            report.textContent = logs.join("\\n");
        }}

        function assert(cond, msg) {{
            if (!cond) {{
                throw new Error("FAIL: " + msg);
            }}
            passed++;
            log("PASS: " + msg);
        }}

        const delay = (ms) => new Promise((res) => setTimeout(res, ms));

        try {{
            // Clean slate
            localStorage.clear();

            const scope = window.__ScoopScope;
            assert(scope !== undefined, "__ScoopScope is exposed");
            assert(typeof scope.saveWorkspaceToStorage === "function", "saveWorkspaceToStorage function exists");
            assert(typeof scope.loadWorkspaceFromStorage === "function", "loadWorkspaceFromStorage function exists");
            assert(typeof scope.clearWorkspace === "function", "clearWorkspace function exists");
            assert(scope.WORKSPACE_STORAGE_KEY === "scoopscope_workspace_v1", "WORKSPACE_STORAGE_KEY is scoopscope_workspace_v1");

            // ==========================================
            // TEST 1: Live Persistence Across Reload
            // ==========================================
            log("\\n--- TEST 1: Live Persistence Across Reload ---");

            // Populate Session 1 with claim and research
            const mockExtractData = {{
                submission_id: "sub_persist_1",
                submitted_text: "City of Los Angeles issued tree canopy goals for 2028.",
                source_url: "https://lacity.gov/trees",
                purpose: "check_claim",
                interpreted_question: "Did LA issue tree canopy goals for 2028?",
                claims: [
                    {{
                        id: "claim_tree_1",
                        claim_type: "factual",
                        normalized_assertion: "Los Angeles adopted a 2028 tree canopy target.",
                        original_wording: "City of Los Angeles issued tree canopy goals for 2028.",
                        explicit_date: "2028",
                        explicit_location: "Los Angeles"
                    }}
                ]
            }};

            scope.renderResults(mockExtractData, scope.currentSeq);

            // Mock research data for Session 1
            const mockResearchData = {{
                claim_id: "claim_tree_1",
                status_message: "Completed in 0.4s",
                completed_in_seconds: 0.4,
                candidate_passages: [
                    {{
                        passage_id: "psg_tree_1",
                        source_id: "src_tree_1",
                        source_url: "https://lacity.gov/trees/report",
                        exact_passage: "The Urban Forestry Division set a target of 30 percent canopy by 2028.",
                        context_surrounding: "The Urban Forestry Division set a target of 30 percent canopy by 2028.",
                        publication_date: "2024-02-10",
                        jurisdiction_tag: "LA City Official",
                        relevance_explanation: "Verifies the 2028 tree canopy target.",
                        relevance_note: "Direct match"
                    }}
                ],
                retrieved_sources: [
                    {{
                        domain: "lacity.gov",
                        url: "https://lacity.gov/trees/report",
                        title: "Urban Forestry 2028 Goals",
                        publication_date: "2024-02-10",
                        jurisdiction_tag: "LA City Official",
                        status: "retrieved"
                    }}
                ],
                search_hits: [],
                suggested_next_queries: ["LA urban forestry budget 2024"],
                inquiry_synthesis: "LA City Urban Forestry has adopted a 30 percent canopy goal by 2028."
            }};

            const claimCard = document.getElementById("claim-card-claim_tree_1");
            assert(claimCard !== null, "Claim card rendered in DOM");
            const resContainer = claimCard.querySelector(".claim-research-container");
            const researchBtn = claimCard.querySelector(".btn-research");

            // Execute research rendering and switch citation style to APA
            scope.claimResearchTabs["claim_tree_1"] = [{{
                id: "run_tree_init",
                title: "Tab 1: Initial Inquiry",
                query: "Los Angeles adopted a 2028 tree canopy target.",
                data: mockResearchData,
                timestamp: Date.now()
            }}];
            scope.activeClaimTabId["claim_tree_1"] = "run_tree_init";

            const qKey = "claim_tree_1_https://lacity.gov/trees/report_undefined_undefined";
            scope.selectedQuotes[qKey] = {{
                checked: true,
                passage: mockResearchData.candidate_passages[0],
                claimId: "claim_tree_1"
            }};
            scope.activeCitationStyle = "apa";

            resContainer.classList.remove("hidden");
            scope.renderClaimResearchTabsWorkspace(resContainer, mockExtractData.claims[0], researchBtn, claimCard);

            // Open a second session tab with draft input text
            const btnNew = document.getElementById("btn-new-session");
            btnNew.click();
            const inputEl = document.getElementById("input-text");
            inputEl.value = "Draft inquiry for session two";
            inputEl.dispatchEvent(new Event("input"));

            // Trigger save
            scope.saveWorkspaceToStorage();

            const savedRaw = localStorage.getItem("scoopscope_workspace_v1");
            assert(savedRaw !== null, "localStorage has scoopscope_workspace_v1 saved");
            const savedObj = JSON.parse(savedRaw);
            assert(savedObj.version === 1, "Saved workspace version is 1");
            assert(savedObj.sessions.length === 2, "Saved workspace has 2 sessions");
            assert(Array.isArray(savedObj.sessions[0].selectedQuotes), "selectedQuotes is serialized as JSON array");
            assert(savedObj.citationStyle === "apa", "Saved citation style is apa");

            // Simulate reload with pre-seeded data containing forced transient loading flags
            savedObj.sessions[0].isClarifying = true;
            savedObj.sessions[0].isResearching = true;
            localStorage.setItem("scoopscope_workspace_v1", JSON.stringify(savedObj));

            // Reload from storage
            const loadedSuccess = scope.loadWorkspaceFromStorage();
            assert(loadedSuccess === true, "loadWorkspaceFromStorage succeeded");

            const sessionTabsList = document.getElementById("session-tabs-list");
            const restoredBtns = sessionTabsList.querySelectorAll(".session-tab-btn");
            assert(restoredBtns.length === 2, "Both session tabs restored in DOM");

            // Verify transient loading banner is sanitized to hidden
            const banner = document.getElementById("loading-progress-banner");
            assert(banner.classList.contains("hidden"), "Transient loading banner forced to hidden on restore");

            // Switch to Session 1 tab
            restoredBtns[0].click();
            await delay(30);

            const stickyBar = document.getElementById("sticky-inquiry-bar");
            assert(!stickyBar.classList.contains("hidden"), "Sticky inquiry bar restored for Session 1");
            assert(claimCard.querySelector(".cornell-pair-row") !== null, "Cornell notes row restored in Session 1");
            const cb = claimCard.querySelector(".quote-select-checkbox");
            assert(cb !== null && cb.checked === true, "Evidence bank quote checkbox state restored to checked");

            // Verify APA Works Cited citation style restored
            const citationSelect = claimCard.querySelector(".citation-style-select");
            assert(citationSelect !== null, "Citation select rendered");
            assert(citationSelect.value === "apa", "Citation style restored to apa in selector");

            // ==========================================
            // TEST 2: Corrupt JSON Graceful Fallback
            // ==========================================
            log("\\n--- TEST 2: Corrupt JSON Fallback ---");
            localStorage.setItem("scoopscope_workspace_v1", "{{corrupt-json-string-not-valid");

            // Must not throw an unhandled exception
            let corruptHandled = false;
            try {{
                const res = scope.loadWorkspaceFromStorage();
                corruptHandled = true;
            }} catch (e) {{
                corruptHandled = false;
            }}
            assert(corruptHandled === true, "Corrupted localStorage does not throw an unhandled exception");

            const postCorruptBtns = sessionTabsList.querySelectorAll(".session-tab-btn");
            assert(postCorruptBtns.length === 1, "App initialized with 1 clean session tab after corruption");
            assert(postCorruptBtns[0].textContent.includes("Session 1"), "Clean tab title is Session 1");

            // ==========================================
            // TEST 3: One-Click Clear Workspace
            // ==========================================
            log("\\n--- TEST 3: One-Click Clear Workspace ---");

            // Setup multiple sessions
            btnNew.click();
            inputEl.value = "Session to be wiped";
            inputEl.dispatchEvent(new Event("input"));
            scope.saveWorkspaceToStorage();
            assert(sessionTabsList.querySelectorAll(".session-tab-btn").length === 2, "Multiple session tabs exist before clear");

            const clearBtn = document.getElementById("btn-clear-workspace");
            assert(clearBtn !== null, "#btn-clear-workspace exists");

            // Click clear workspace
            clearBtn.click();
            await delay(30);

            const afterClearStorage = localStorage.getItem("scoopscope_workspace_v1");
            let cleanStorageValid = false;
            if (afterClearStorage === null) {{
                cleanStorageValid = true;
            }} else {{
                const parsedClean = JSON.parse(afterClearStorage);
                cleanStorageValid = parsedClean.sessions.length === 1;
            }}
            assert(cleanStorageValid === true, "Storage is either removed or holds a single clean Session 1");

            const postClearBtns = sessionTabsList.querySelectorAll(".session-tab-btn");
            assert(postClearBtns.length === 1, "Only 1 session tab remains in #session-tabs-list");
            assert(postClearBtns[0].textContent.includes("Session 1"), "Remaining tab is Session 1");
            assert(inputEl.value === "", "#input-text is empty");

            const claimInputEl = document.getElementById("claim-input");
            if (claimInputEl) {{
                assert(claimInputEl.value === "", "#claim-input is empty");
            }}

            const resultsSec = document.getElementById("results-section");
            assert(resultsSec.classList.contains("hidden"), "#results-section is hidden");

            const reportSec = document.getElementById("report-studio-section");
            assert(reportSec.classList.contains("hidden"), "#report-studio-section is hidden");

            log("\\n=================================================");
            log(`ALL PERSISTENCE TESTS PASSED: ${{passed}} assertions passed.`);
            log("=================================================");
            report.className = "test-pass";

        }} catch (err) {{
            log("\\n=================================================");
            log(`TEST RUN FAILED: ${{err.message}}`);
            log("=================================================");
            report.className = "test-fail";
        }}
    }})();
    </script>
</body>
</html>
"""

    runner_file = tmp_path / "test_persistence_runner.html"
    runner_file.write_text(runner_html_content, encoding="utf-8")

    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--allow-file-access-from-files",
        "--virtual-time-budget=6000",
        "--dump-dom",
        str(runner_file),
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
    print("\n--- PERSISTENCE TEST REPORT ---")
    print(report_text.encode("ascii", errors="replace").decode("ascii"))
    print("--- END PERSISTENCE TEST REPORT ---\n")

    assert "ALL PERSISTENCE TESTS PASSED" in report_text, f"Persistence tests failed:\n{report_text}"
    assert "FAIL:" not in report_text, f"Persistence test assertion failed:\n{report_text}"


def test_fastapi_live_static_and_index_serving():
    """Verify FastAPI GET / serves index.html with all Phase 4 DOM elements and static assets."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200, f"GET / failed with {resp.status_code}"
    html = resp.text
    assert 'id="session-tabs-bar"' in html, "Missing #session-tabs-bar in served index.html"
    assert 'id="btn-clear-workspace"' in html, "Missing #btn-clear-workspace in served index.html"
    assert 'id="input-text"' in html, "Missing #input-text in served index.html"
    assert 'id="citation-style-select"' in html, "Missing #citation-style-select in served index.html"
    assert 'id="custom-report-section"' in html, "Missing #custom-report-section in served index.html"

    # Verify static assets serve cleanly
    resp_js = client.get("/app.js")
    assert resp_js.status_code == 200, f"GET /app.js failed with {resp_js.status_code}"
    assert "scoopscope_workspace_v1" in resp_js.text

    resp_css = client.get("/style.css")
    assert resp_css.status_code == 200, f"GET /style.css failed with {resp_css.status_code}"
    assert "session-tabs-bar" in resp_css.text


@pytest.mark.anyio
async def test_phase4_full_journey_smoke_in_browser(tmp_path: Path):
    """Exercise complete integrated Phase 4 user journey on real DOM elements:
    1. Type query in visible <textarea id="input-text"> -> saves draft to localStorage in inputText.
    2. Render researched claim with official LA Local City source (santamonica.gov) -> Cornell Cue card renders official badge & publication date.
    3. Check quote checkbox in Cornell Notes -> quote selected into Report Studio (#custom-report-section), section is visible (not .hidden).
    4. Switch #citation-style-select to 'mla' and 'apa' -> visible Works Cited list and report reflect format, #custom-report-section remains visible.
    5. Open new session tab (#btn-new-session), type draft in <textarea id="input-text">, reload (loadWorkspaceFromStorage()), switch back to Session 1 -> 100% restored.
    6. Click #btn-clear-workspace -> <textarea id="input-text"> is empty, #custom-report-section hidden, #results-section hidden, single clean 'Session 1' tab.
    """
    browser = _find_browser()
    if not browser:
        pytest.skip("Neither Chrome nor Edge found on host.")

    project_root = Path(__file__).resolve().parent.parent.parent
    index_html_path = project_root / "frontend" / "index.html"
    assert index_html_path.is_file(), f"Missing index.html at {index_html_path}"
    index_html_content = index_html_path.read_text(encoding="utf-8")

    app_js_uri = (project_root / "frontend" / "app.js").resolve().as_uri()
    style_css_uri = (project_root / "frontend" / "style.css").resolve().as_uri()

    # Extract body content from index.html (excluding app.js script tag)
    body_match = re.search(r"<body[^>]*>(.*?)</body>", index_html_content, re.DOTALL)
    assert body_match is not None, "Could not extract body content from index.html"
    body_inner = body_match.group(1)
    body_inner = re.sub(r'<script\s+src=["\']app\.js["\'][^>]*></script>', '', body_inner)

    runner_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>ScoopScope Phase 4 Smoke Runner</title>
    <link rel="stylesheet" href="{style_css_uri}">
    <style>
        #test-report {{
            margin-top: 1rem;
            padding: 1rem;
            background: #111520;
            border: 1px solid #3ecfb4;
            border-radius: 8px;
            font-family: monospace;
            white-space: pre-wrap;
        }}
        .test-pass {{ color: #3ecfb4; }}
        .test-fail {{ color: #eb5757; }}
    </style>
</head>
<body>
    <div id="test-report">Initializing Phase 4 smoke test...</div>

    {body_inner}

    <script src="{app_js_uri}"></script>

    <script>
    (async function() {{
        const report = document.getElementById("test-report");
        const logs = [];
        let passed = 0;

        function log(msg) {{
            logs.push(msg);
            report.textContent = logs.join("\\n");
        }}

        function assert(cond, msg) {{
            if (!cond) {{
                throw new Error("FAIL: " + msg);
            }}
            passed++;
            log("PASS: " + msg);
        }}

        const delay = (ms) => new Promise((res) => setTimeout(res, ms));

        try {{
            localStorage.clear();

            const scope = window.__ScoopScope;
            assert(scope !== undefined, "__ScoopScope is exposed");

            // 1. Type query in visible textarea#input-text -> saves draft in localStorage inputText
            log("\\n--- 1. Visible Textarea Input & LocalStorage Sync ---");
            const inputTextEl = document.getElementById("input-text");
            assert(inputTextEl !== null, "Textarea #input-text exists in DOM");
            inputTextEl.value = "Santa Monica City Council adopted local sustainability resolution.";
            inputTextEl.dispatchEvent(new Event("input", {{ bubbles: true }}));
            await delay(30);

            const savedRaw = localStorage.getItem("scoopscope_workspace_v1");
            assert(savedRaw !== null, "localStorage has scoopscope_workspace_v1 key");
            const savedState = JSON.parse(savedRaw);
            assert(savedState.sessions && savedState.sessions[0].inputText.includes("Santa Monica City Council"), "Draft query persisted in active session inputText");

            // 2. Render researched claim with official LA Local City source (santamonica.gov)
            log("\\n--- 2. Researched Claim & Cornell Notes Official Badges ---");
            const mockExtract = {{
                submission_id: "sub_sm_1",
                submitted_text: "Santa Monica City Council adopted local sustainability resolution.",
                source_url: "https://santamonica.gov/climate",
                purpose: "check_claim",
                interpreted_question: "Did Santa Monica adopt a sustainability resolution?",
                claims: [
                    {{
                        id: "claim_sm_1",
                        claim_type: "factual",
                        normalized_assertion: "Santa Monica approved climate resolution 2024.",
                        original_wording: "Santa Monica City Council adopted local sustainability resolution.",
                        explicit_date: "2024",
                        explicit_location: "Santa Monica"
                    }}
                ]
            }};
            scope.renderResults(mockExtract, scope.currentSeq);

            const mockResearch = {{
                claim_id: "claim_sm_1",
                status_message: "Completed in 0.3s",
                completed_in_seconds: 0.3,
                retrieved_sources: [
                    {{
                        source_id: "src_sm_1",
                        initial_url: "https://santamonica.gov/climate/action-plan",
                        final_url: "https://santamonica.gov/climate/action-plan",
                        domain: "santamonica.gov",
                        title: "Santa Monica Climate Action Plan",
                        publication_date: "2024-06-15",
                        retrieval_timestamp: "2024-10-18T14:00:00Z",
                        status: "fetched",
                        jurisdiction_tag: "LA Local City Official",
                        jurisdiction_code: "la_local_city"
                    }}
                ],
                candidate_passages: [
                    {{
                        passage_id: "psg_sm_1",
                        source_id: "src_sm_1",
                        source_url: "https://santamonica.gov/climate/action-plan",
                        source_title: "Santa Monica Climate Action Plan",
                        exact_passage: "On June 15, 2024, the City Council enacted the Zero-Carbon Municipal Operations resolution.",
                        context_surrounding: "On June 15, 2024, the City Council enacted the Zero-Carbon Municipal Operations resolution.",
                        relevance_explanation: "Direct proof of municipal sustainability adoption.",
                        publication_date: "2024-06-15",
                        jurisdiction_badge: "LA Local City Official",
                        jurisdiction_code: "la_local_city"
                    }}
                ]
            }};

            const card = document.getElementById("claim-card-claim_sm_1");
            assert(card !== null, "Claim card rendered in DOM");
            const resContainer = card.querySelector(".claim-research-container");
            const resBtn = card.querySelector(".btn-research");

            scope.claimResearchTabs["claim_sm_1"] = [{{
                id: "run_sm_1",
                title: "Tab 1: Initial Inquiry",
                query: mockExtract.claims[0].normalized_assertion,
                data: mockResearch,
                timestamp: Date.now()
            }}];
            scope.activeClaimTabId["claim_sm_1"] = "run_sm_1";
            resContainer.classList.remove("hidden");
            scope.renderClaimResearchTabsWorkspace(resContainer, mockExtract.claims[0], resBtn, card);

            const jurisBadge = card.querySelector(".jurisdiction-badge");
            assert(jurisBadge !== null, "Official jurisdiction badge rendered in Cornell Notes cue card");
            assert(jurisBadge.textContent.includes("LA Local City Official"), "Badge shows 'LA Local City Official'");
            assert(jurisBadge.classList.contains("jurisdiction-la_local_city"), "Badge has class jurisdiction-la_local_city");

            const dateBadge = card.querySelector(".cue-date-badge");
            assert(dateBadge !== null && dateBadge.textContent.includes("2024-06-15"), "Publication date rendered in cue card");

            // 3. Check quote checkbox in Cornell Notes card to select into Report Studio (#custom-report-section)
            log("\\n--- 3. Check Quote & Reveal Report Studio (#custom-report-section) ---");
            const quoteCb = card.querySelector(".quote-select-checkbox");
            assert(quoteCb !== null, "Quote checkbox rendered in Cornell Notes bullet");
            quoteCb.checked = true;
            quoteCb.dispatchEvent(new Event("change", {{ bubbles: true }}));
            await delay(30);

            const customReportSec = document.getElementById("custom-report-section");
            assert(customReportSec !== null, "#custom-report-section exists in DOM");
            assert(!customReportSec.classList.contains("hidden"), "#custom-report-section is visible (not .hidden)");

            // 4. Switch #citation-style-select to 'mla' and 'apa'
            log("\\n--- 4. Citation Style Switching (MLA & APA) ---");
            const citationSelect = document.getElementById("citation-style-select");
            assert(citationSelect !== null, "#citation-style-select exists in DOM");

            // Switch to MLA
            citationSelect.value = "mla";
            citationSelect.dispatchEvent(new Event("change", {{ bubbles: true }}));
            await delay(30);

            assert(!customReportSec.classList.contains("hidden"), "#custom-report-section remains visible on MLA switch");
            const reportBody = customReportSec.querySelector(".report-content-body");
            assert(reportBody !== null, "Report content body exists in #custom-report-section");
            assert(reportBody.textContent.includes("Works Cited"), "Report contains Works Cited section");
            assert(reportBody.textContent.includes("Accessed") && reportBody.textContent.includes("[LA Local City Official]"), "MLA format reflected with Accessed date and jurisdiction tag");

            // Switch to APA
            citationSelect.value = "apa";
            citationSelect.dispatchEvent(new Event("change", {{ bubbles: true }}));
            await delay(30);

            assert(!customReportSec.classList.contains("hidden"), "#custom-report-section remains visible on APA switch");
            assert(reportBody.textContent.includes("(2024)") && reportBody.textContent.includes("[LA Local City Official]"), "APA format reflected with (2024) and jurisdiction tag");

            // 5. Open new session tab (#btn-new-session), type draft in #input-text, reload, switch back
            log("\\n--- 5. Multi-Tab Session Reload & Session 1 Restoration ---");
            const btnNewSess = document.getElementById("btn-new-session");
            assert(btnNewSess !== null, "#btn-new-session exists in DOM");
            btnNewSess.click();
            await delay(30);

            inputTextEl.value = "County of Los Angeles public health ordinance.";
            inputTextEl.dispatchEvent(new Event("input", {{ bubbles: true }}));
            await delay(30);

            // Re-run loadWorkspaceFromStorage() to simulate reload
            scope.loadWorkspaceFromStorage();
            await delay(30);

            const sessionTabs = document.querySelectorAll(".session-tab-btn");
            assert(sessionTabs.length === 2, "2 session tabs restored after reload");
            sessionTabs[0].click(); // Switch back to Session 1
            await delay(30);

            assert(inputTextEl.value.includes("Santa Monica City Council"), "Session 1 inputText restored");
            const restoredBadge = document.querySelector(".jurisdiction-badge");
            assert(restoredBadge !== null && restoredBadge.textContent.includes("LA Local City Official"), "Session 1 official jurisdiction badge restored");
            const restoredCb = document.querySelector(".quote-select-checkbox");
            assert(restoredCb !== null && restoredCb.checked === true, "Session 1 checked quote restored");
            assert(!customReportSec.classList.contains("hidden"), "Session 1 #custom-report-section is visible");
            assert(citationSelect.value === "apa", "Active citation style 'apa' restored");

            // 6. Click #btn-clear-workspace and verify
            log("\\n--- 6. One-Click Clear Workspace Reset ---");
            const clearBtn = document.getElementById("btn-clear-workspace");
            assert(clearBtn !== null, "#btn-clear-workspace exists in DOM");
            clearBtn.click();
            await delay(30);

            assert(inputTextEl.value === "", "inputText is empty after clear workspace");
            const claimInputEl = document.getElementById("claim-input");
            assert(claimInputEl && claimInputEl.value === "", "claimInput is empty after clear workspace");
            assert(customReportSec.classList.contains("hidden"), "#custom-report-section is hidden after clear workspace");
            const resultsSec = document.getElementById("results-section");
            assert(resultsSec.classList.contains("hidden"), "#results-section is hidden after clear workspace");
            const remainingTabs = document.querySelectorAll(".session-tab-btn");
            assert(remainingTabs.length === 1 && remainingTabs[0].textContent.includes("Session 1"), "Only single clean Session 1 tab remains");

            log("\\nALL PHASE 4 SMOKE TESTS PASSED (" + passed + " assertions)");
        }} catch (err) {{
            report.className = "test-fail";
            report.textContent = "FAIL: " + err.message + "\\n" + (err.stack || "");
        }}
    }})();
    </script>
</body>
</html>"""

    runner_file = tmp_path / "phase4_smoke_runner.html"
    runner_file.write_text(runner_html, encoding="utf-8")

    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--allow-file-access-from-files",
        "--virtual-time-budget=8000",
        "--dump-dom",
        str(runner_file),
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
    print("\n--- PHASE 4 SMOKE TEST REPORT ---")
    print(report_text.encode("ascii", errors="replace").decode("ascii"))
    print("--- END PHASE 4 SMOKE TEST REPORT ---\n")

    assert "ALL PHASE 4 SMOKE TESTS PASSED" in report_text, f"Phase 4 smoke tests failed:\n{report_text}"
    assert "FAIL:" not in report_text, f"Phase 4 smoke test assertion failed:\n{report_text}"


def test_inflight_search_isolation_across_session_tabs(tmp_path: Path):
    """
    Milestone 4G (Decision 017):
    Verify that an in-flight async search/clarify request started in Session 1
    does NOT bleed into Session 2 when the user switches tabs before the response resolves.
    When the response finishes:
    - Session 2's active DOM must remain completely clean/blank (zero bleed).
    - Session 1 must store the completed data in memory and localStorage.
    - Switching back to Session 1 displays Session 1's completed results cleanly.
    """
    browser = _find_browser()
    if not browser:
        pytest.skip("Neither Chrome nor Edge found on host.")

    project_root = Path(__file__).resolve().parent.parent.parent
    index_html_path = project_root / "frontend" / "index.html"
    index_html_content = index_html_path.read_text(encoding="utf-8")

    app_js_uri = (project_root / "frontend" / "app.js").resolve().as_uri()
    style_css_uri = (project_root / "frontend" / "style.css").resolve().as_uri()

    body_match = re.search(r"<body[^>]*>(.*?)</body>", index_html_content, re.DOTALL)
    assert body_match is not None, "Could not extract body content from index.html"
    body_inner = body_match.group(1)
    body_inner = re.sub(r'<script\s+src=["\']app\.js["\'][^>]*></script>', '', body_inner)

    runner_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Milestone 4G Tab Isolation Test</title>
    <link rel="stylesheet" href="{style_css_uri}">
    <style>
        #test-report {{
            margin-top: 1rem;
            padding: 1rem;
            background: #111520;
            border: 1px solid #3ecfb4;
            border-radius: 8px;
            font-family: monospace;
            white-space: pre-wrap;
        }}
        .test-pass {{ color: #3ecfb4; }}
        .test-fail {{ color: #eb5757; }}
    </style>
</head>
<body>
    <div id="test-report">Initializing Tab Isolation test...</div>

    {body_inner}

    <script src="{app_js_uri}"></script>

    <script>
    (async function() {{
        const report = document.getElementById("test-report");
        const logs = [];
        let passed = 0;

        function log(msg) {{
            logs.push(msg);
            report.textContent = logs.join("\\n");
        }}

        function assert(condition, message) {{
            if (!condition) {{
                throw new Error("Assertion failed: " + message);
            }}
            passed++;
            log("  [PASS " + passed + "] " + message);
        }}

        function delay(ms) {{
            return new Promise(resolve => setTimeout(resolve, ms));
        }}

        try {{
            const scope = window.__ScoopScope;
            assert(scope !== undefined, "__ScoopScope is exposed");

            // Mock fetch to simulate delayed server response (150ms delay)
            const origFetch = window.fetch;
            window.fetch = async function(url, options) {{
                if (url.includes("/api/clarify")) {{
                    await delay(150);
                    return {{
                        ok: true,
                        status: 200,
                        json: async () => ({{
                            clarification_needed: false,
                            submission_id: "sub_delay_1",
                            submitted_text: "Session 1 delayed statement",
                            confirmed_scope_question: "What did Session 1 assert?",
                            claims: [
                                {{
                                    id: "claim_sess1_del",
                                    normalized_assertion: "Session 1 claim resolved in background.",
                                    quote: "Session 1 delayed statement",
                                    confidence: 0.95
                                }}
                            ]
                        }})
                    }};
                }}
                return origFetch(url, options);
            }};

            // 1. Session 1 is active. Submit an inquiry.
            log("\\n--- 1. Submit Inquiry in Session 1 with Delayed Response ---");
            const inputTextEl = document.getElementById("input-text");
            inputTextEl.value = "Session 1 delayed statement";
            inputTextEl.dispatchEvent(new Event("input", {{ bubbles: true }}));

            const form = document.getElementById("extraction-form");
            form.dispatchEvent(new Event("submit", {{ bubbles: true, cancelable: true }}));

            // 2. Switch to Session 2 while request is in flight (after 30ms)
            await delay(30);
            log("\\n--- 2. Switch to Session 2 (+ New) While Request In Flight ---");
            const btnNewSess = document.getElementById("btn-new-session");
            btnNewSess.click();
            await delay(30);

            const activeSessId = scope.activeSessionId;
            const tabs = document.querySelectorAll(".session-tab-btn");
            assert(tabs.length === 2, "2 session tabs exist");
            assert(tabs[1].classList.contains("active"), "Session 2 tab is currently active");
            assert(inputTextEl.value === "", "Session 2 input is empty");
            const resultsSec = document.getElementById("results-section");
            assert(resultsSec.classList.contains("hidden"), "Session 2 results-section is hidden while Session 1 is in-flight");

            // 3. Wait for Session 1's mock fetch to complete (200ms)
            log("\\n--- 3. Await Background Completion of Session 1 Request ---");
            await delay(200);

            // Verify Session 2 has NOT been corrupted
            assert(resultsSec.classList.contains("hidden"), "Session 2 results-section is STILL hidden (zero bleed from Session 1)");
            const claimsList = document.getElementById("claims-list");
            assert(claimsList.children.length === 0, "Session 2 claims-list is empty (zero bleed from Session 1)");
            assert(inputTextEl.value === "", "Session 2 inputText is still empty (zero bleed from Session 1)");

            // 4. Switch back to Session 1 and verify Session 1's results appear
            log("\\n--- 4. Switch Back to Session 1 to Verify Results Persisted ---");
            tabs[0].click(); // Click Session 1 tab
            await delay(50);

            assert(!resultsSec.classList.contains("hidden"), "Session 1 results-section is now visible");
            const card = document.getElementById("claim-card-claim_sess1_del");
            assert(card !== null, "Session 1 claim card rendered cleanly in DOM upon tab switch");
            assert(inputTextEl.value.includes("Session 1 delayed statement"), "Session 1 inputText restored");

            // Switch back to Session 2 again and verify clean state
            log("\\n--- 5. Switch Back to Session 2 to Confirm Idempotence ---");
            const updatedTabs = document.querySelectorAll(".session-tab-btn");
            updatedTabs[1].click();
            await delay(50);

            assert(resultsSec.classList.contains("hidden"), "Session 2 results-section is hidden when switched back");
            assert(inputTextEl.value === "", "Session 2 input remains empty");

            log("\\nALL TAB ISOLATION TESTS PASSED (" + passed + " assertions)");
        }} catch (err) {{
            report.className = "test-fail";
            report.textContent = "FAIL: " + err.message + "\\n" + (err.stack || "");
        }}
    }})();
    </script>
</body>
</html>"""

    runner_file = tmp_path / "tab_isolation_runner.html"
    runner_file.write_text(runner_html, encoding="utf-8")

    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--allow-file-access-from-files",
        "--virtual-time-budget=6000",
        "--dump-dom",
        str(runner_file),
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
    print("\n--- TAB ISOLATION TEST REPORT ---")
    print(report_text.encode("ascii", errors="replace").decode("ascii"))
    print("--- END TAB ISOLATION TEST REPORT ---\n")

    assert "ALL TAB ISOLATION TESTS PASSED" in report_text, f"Tab isolation tests failed:\n{report_text}"
    assert "FAIL:" not in report_text, f"Tab isolation test assertion failed:\n{report_text}"


def test_single_collapsible_report_studio_and_clean_empty_state(tmp_path: Path):
    """
    Milestone 4G (Decision 017):
    Verify:
    1. On initial load and on a fresh tab (+ New) with 0 quotes / 0 results,
       both #report-studio-section and #custom-report-section are hidden,
       and #confirmed-scope-card / #confirmed-scope-banner are hidden.
    2. Exactly ONE visible Report Studio container exists in the DOM when results load.
    3. The Report Studio options body starts collapsed until toggled by #btn-toggle-report-studio.
    4. Works Cited deduplicates identical source URLs (2 quotes from same URL appear as 1 citation).
    5. Ordered list items render sequential numbering (1., 2.) rather than repeating 1. on every item.
    """
    browser = _find_browser()
    if not browser:
        pytest.skip("Neither Chrome nor Edge found on host.")

    project_root = Path(__file__).resolve().parent.parent.parent
    index_html_path = project_root / "frontend" / "index.html"
    index_html_content = index_html_path.read_text(encoding="utf-8")

    app_js_uri = (project_root / "frontend" / "app.js").resolve().as_uri()
    style_css_uri = (project_root / "frontend" / "style.css").resolve().as_uri()

    body_match = re.search(r"<body[^>]*>(.*?)</body>", index_html_content, re.DOTALL)
    assert body_match is not None, "Could not extract body content from index.html"
    body_inner = body_match.group(1)
    body_inner = re.sub(r'<script\s+src=["\']app\.js["\'][^>]*></script>', '', body_inner)

    runner_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Milestone 4G Collapsible Report Studio Test</title>
    <link rel="stylesheet" href="{style_css_uri}">
    <style>
        #test-report {{
            margin-top: 1rem;
            padding: 1rem;
            background: #111520;
            border: 1px solid #3ecfb4;
            border-radius: 8px;
            font-family: monospace;
            white-space: pre-wrap;
        }}
        .test-pass {{ color: #3ecfb4; }}
        .test-fail {{ color: #eb5757; }}
    </style>
</head>
<body>
    <div id="test-report">Initializing Collapsible Report Studio test...</div>

    {body_inner}

    <script src="{app_js_uri}"></script>

    <script>
    (async function() {{
        const report = document.getElementById("test-report");
        const logs = [];
        let passed = 0;

        function log(msg) {{
            logs.push(msg);
            report.textContent = logs.join("\\n");
        }}

        function assert(condition, message) {{
            if (!condition) {{
                throw new Error("Assertion failed: " + message);
            }}
            passed++;
            log("  [PASS " + passed + "] " + message);
        }}

        function delay(ms) {{
            return new Promise(resolve => setTimeout(resolve, ms));
        }}

        try {{
            const scope = window.__ScoopScope;
            assert(scope !== undefined, "__ScoopScope is exposed");

            // 1. Initial Load Empty State Check
            log("\\n--- 1. Initial Clean Empty State Check ---");
            const customReportSec = document.getElementById("custom-report-section");
            const reportStudioSec = document.getElementById("report-studio-section");
            assert(customReportSec && customReportSec.classList.contains("hidden"), "#custom-report-section is hidden on initial load");
            if (reportStudioSec) {{
                assert(reportStudioSec.classList.contains("hidden"), "#report-studio-section is hidden on initial load");
            }}

            const confirmedScope = document.getElementById("confirmed-scope-card");
            assert(confirmedScope && confirmedScope.classList.contains("hidden"), "#confirmed-scope-card is hidden on initial load");
            const resultsSec = document.getElementById("results-section");
            assert(resultsSec && resultsSec.classList.contains("hidden"), "#results-section is hidden on initial load");

            // 2. Open Fresh Session Tab (+ New) -> Empty State Preserved
            log("\\n--- 2. Fresh Session Tab (+ New) Empty State ---");
            const btnNewSess = document.getElementById("btn-new-session");
            btnNewSess.click();
            await delay(30);

            assert(customReportSec.classList.contains("hidden"), "#custom-report-section is hidden on fresh tab");
            if (reportStudioSec) {{
                assert(reportStudioSec.classList.contains("hidden"), "#report-studio-section is hidden on fresh tab");
            }}
            assert(resultsSec.classList.contains("hidden"), "#results-section is hidden on fresh tab");

            // 3. Render Claims & Research Results with 2 quotes from SAME URL + 1 from another
            log("\\n--- 3. Render Research Results with Multi-Quote Same Source ---");
            const mockExtract = {{
                claims: [
                    {{
                        id: "claim_multi_1",
                        normalized_assertion: "City adopted zero-carbon targets.",
                        quote: "City adopted zero-carbon targets.",
                        confidence: 0.95
                    }}
                ]
            }};
            scope.renderResults(mockExtract, scope.currentSeq);

            const mockResearch = {{
                claim_id: "claim_multi_1",
                status_message: "Completed in 0.2s",
                completed_in_seconds: 0.2,
                retrieved_sources: [
                    {{
                        source_id: "src_1",
                        initial_url: "https://santamonica.gov/climate/plan",
                        final_url: "https://santamonica.gov/climate/plan",
                        domain: "santamonica.gov",
                        title: "Santa Monica Climate Plan",
                        publication_date: "2024-06-15",
                        jurisdiction_tag: "LA Local City Official"
                    }},
                    {{
                        source_id: "src_2",
                        initial_url: "https://lacounty.gov/sustainability",
                        final_url: "https://lacounty.gov/sustainability",
                        domain: "lacounty.gov",
                        title: "LA County Sustainability Plan",
                        publication_date: "2024-05-10",
                        jurisdiction_tag: "LA County Official"
                    }}
                ],
                candidate_passages: [
                    {{
                        passage_id: "psg_1a",
                        source_id: "src_1",
                        source_url: "https://santamonica.gov/climate/plan",
                        source_title: "Santa Monica Climate Plan",
                        exact_passage: "Passage 1 from Santa Monica City Council.",
                        publication_date: "2024-06-15",
                        jurisdiction_tag: "LA Local City Official"
                    }},
                    {{
                        passage_id: "psg_1b",
                        source_id: "src_1",
                        source_url: "https://santamonica.gov/climate/plan",
                        source_title: "Santa Monica Climate Plan",
                        exact_passage: "Passage 2 from the same Santa Monica page.",
                        publication_date: "2024-06-15",
                        jurisdiction_tag: "LA Local City Official"
                    }},
                    {{
                        passage_id: "psg_2",
                        source_id: "src_2",
                        source_url: "https://lacounty.gov/sustainability",
                        source_title: "LA County Sustainability Plan",
                        exact_passage: "Passage 3 from County of Los Angeles.",
                        publication_date: "2024-05-10",
                        jurisdiction_tag: "LA County Official"
                    }}
                ]
            }};

            const card = document.getElementById("claim-card-claim_multi_1");
            const resContainer = card.querySelector(".claim-research-container");
            const resBtn = card.querySelector(".btn-research");
            scope.claimResearchTabs["claim_multi_1"] = [{{
                id: "run_multi_1",
                title: "Tab 1: Initial Inquiry",
                query: mockExtract.claims[0].normalized_assertion,
                data: mockResearch,
                timestamp: Date.now()
            }}];
            scope.activeClaimTabId["claim_multi_1"] = "run_multi_1";
            resContainer.classList.remove("hidden");
            scope.renderClaimResearchTabsWorkspace(resContainer, mockExtract.claims[0], resBtn, card);
            await delay(30);

            // 4. Verify exactly ONE visible Report Studio container in the DOM
            log("\\n--- 4. Verify Single Visible Report Studio in DOM ---");
            const visibleStudios = Array.from(document.querySelectorAll(".custom-report-section, #custom-report-section, #report-studio-section, .report-builder-panel"))
                .filter(el => !el.classList.contains("hidden") && el.offsetParent !== null);
            // Must have exactly 1 visible top-level report studio container
            const topLevelReportContainers = Array.from(document.querySelectorAll("#custom-report-section, #report-studio-section"))
                .filter(el => !el.classList.contains("hidden"));
            assert(topLevelReportContainers.length === 1, "Exactly ONE top-level Report Studio section is visible in DOM");

            // 5. Verify Collapsible Body Starts Collapsed
            log("\\n--- 5. Verify Report Studio Controls Start Collapsed ---");
            const toggleBtn = document.getElementById("btn-toggle-report-studio") || document.querySelector(".btn-toggle-report-studio");
            assert(toggleBtn !== null, "Collapsible toggle button #btn-toggle-report-studio exists");
            const collapsibleBody = document.getElementById("report-studio-collapsible-body") || document.querySelector(".report-studio-body");
            assert(collapsibleBody !== null, "Collapsible body #report-studio-collapsible-body exists");
            assert(collapsibleBody.classList.contains("hidden"), "Report studio controls start collapsed (.hidden)");

            // Click toggle button to expand
            toggleBtn.click();
            await delay(30);
            assert(!collapsibleBody.classList.contains("hidden"), "Report studio controls expand when toggle clicked");

            // 6. Verify Works Cited Deduplicates Identical Source URLs
            log("\\n--- 6. Verify Works Cited URL Deduplication & Sequential Numbering ---");
            const reportBody = customReportSec.querySelector(".report-content-body");
            assert(reportBody !== null, "Report content body exists");
            const reportText = reportBody.textContent;

            // In Works Cited, santamonica.gov should appear once in the Works Cited list
            const worksCitedIdx = reportText.indexOf("Works Cited");
            assert(worksCitedIdx !== -1, "Works Cited section exists in report body");
            const worksCitedSectionText = reportText.slice(worksCitedIdx);

            const smMatches = (worksCitedSectionText.match(/santamonica\\.gov/g) || []).length;
            assert(smMatches === 1, "santamonica.gov appears exactly ONCE in Works Cited (deduplicated across 2 quotes)");

            // 7. Verify Sequential List Numbering in Markdown
            log("\\n--- 7. Verify Sequential List Numbering in HTML Rendering ---");
            const sampleListMd = "1. First point\\n\\n2. Second point\\n\\n3. Third point";
            const renderedHtml = scope.renderMarkdown ? scope.renderMarkdown(sampleListMd) : window.renderMarkdown(sampleListMd);
            assert(!renderedHtml.includes("</ol><ol>"), "Consecutive numbered list items with blank lines do not split into separate <ol> tags");
            assert(renderedHtml.includes("<ol") && renderedHtml.includes("<li>First point</li>"), "Rendered HTML contains valid ordered list");

            log("\\nALL SINGLE COLLAPSIBLE REPORT STUDIO TESTS PASSED (" + passed + " assertions)");
        }} catch (err) {{
            report.className = "test-fail";
            report.textContent = "FAIL: " + err.message + "\\n" + (err.stack || "");
        }}
    }})();
    </script>
</body>
</html>"""

    runner_file = tmp_path / "collapsible_report_studio_runner.html"
    runner_file.write_text(runner_html, encoding="utf-8")

    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--allow-file-access-from-files",
        "--virtual-time-budget=6000",
        "--dump-dom",
        str(runner_file),
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
    print("\n--- COLLAPSIBLE REPORT STUDIO TEST REPORT ---")
    print(report_text.encode("ascii", errors="replace").decode("ascii"))
    print("--- END COLLAPSIBLE REPORT STUDIO TEST REPORT ---\n")

    assert "ALL SINGLE COLLAPSIBLE REPORT STUDIO TESTS PASSED" in report_text, f"Report studio tests failed:\n{report_text}"
    assert "FAIL:" not in report_text, f"Report studio test assertion failed:\n{report_text}"


