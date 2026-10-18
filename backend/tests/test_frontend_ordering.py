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
