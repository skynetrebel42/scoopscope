# ScoopScope — How It Works: Owner's Guide for Minh

Welcome to ScoopScope! This guide explains what ScoopScope does, how it works under the hood, and what makes its evidence-first architecture unique, all in plain, straightforward English.

---

## 1. What ScoopScope Does

Think of ScoopScope as **"Perplexity Plus for Everyday Fact Investigation"**.

When people read news stories, social media posts, or viral quotes, they often wonder: *"Is this actually true? Who said this? What do the real source documents say?"*

Traditional AI search engines often answer by summarizing web pages in their own words. But AI summaries can hallucinate, omit critical nuances, or point to dead links. 

**ScoopScope takes the opposite approach:**
- It never gives automated "True" or "False" verdict scores.
- It never invents quotes or citations.
- It finds real, authoritative web pages, retrieves the exact text, and highlights the **exact, verbatim sentences** so you can audit the evidence with your own eyes.

---

## 2. The Investigation Lifecycle: From Raw Text to Custom Report

Here is the exact journey every claim takes inside ScoopScope:

```
[ 1. Intake ] 
     │  Paste text or URL
     ▼
[ 2. Clarification ] 
     │  Up to 2 rounds: 3 clear options + free text
     ▼
[ 3. Confirmed Scope ] 
     │  Checkable question agreed & claims extracted
     ▼
[ 4. Bounded Search & Safe Fetch ] 
     │  Serper query (-filetype:pdf) + SSRF-pinned page retrieval
     ▼
[ 5. Cornell Notes & Deep Links ] 
     │  Exact verbatim quotes + W3C #:~:text= links + defensible dates
     ▼
[ 6. Workspace & Custom Report Studio ]
        Select quotes into Evidence Bank & synthesize tailored reports
```

### Stage 1: Intake
You paste a statement, headline, or claim into the input box (plus an optional source URL). 

### Stage 2: Clarification (Max 2 Rounds)
If a statement is vague or broad (e.g., *"Europe bans American beef"*), ScoopScope doesn't make assumptions. It asks a single clarifying question offering **exactly 3 coherent choices** (e.g., bovine hormones, chlorine washes, or general additives) plus a free-text box. This is capped at **2 rounds maximum** so you are never stuck in an endless loop.

### Stage 3: Confirmed Scope
Once clarified, ScoopScope displays a **Confirmed Inquiry Scope** card. You can edit this question directly at any time. If you edit the scope, ScoopScope automatically resets in-flight research to ensure your evidence always matches your active inquiry.

### Stage 4: Bounded Search & Safe Fetch
When you click **"Find sources"** on a claim:
1. ScoopScope creates targeted queries ending in `-filetype:pdf` (so the search engine skips unparseable PDF binaries).
2. It asks the Serper Google Search API for the top 5 relevant links (using at most 2 requests).
3. It selects up to 3 candidate pages and downloads them using a hardened, secure connection that finishes within a strict 90-second deadline.

### Stage 5: Cornell Notes & Deep Links
Once pages are fetched:
1. ScoopScope strips scripts and ads, leaving clean plain text.
2. It slices out 1 to 5 exact verbatim quotes matching your claim, calculating mathematical character coordinates.
3. It detects defensible publication dates using structured metadata.
4. It displays the evidence in a **two-column Cornell Notes layout**: the claim assertion on the left, and the verbatim quotes with publication dates and relevance notes on the right.
5. Every quote has a **"Find exact line in source ↗"** button that uses W3C Text Fragments to jump straight to the highlighted quote on the publisher's live webpage.

### Stage 6: Multi-Tab Workspace & Custom Report Studio
You can run multiple claims or start fresh inquiries in new session tabs without losing prior results. You can check the boxes next to your favorite quotes to collect them into an **Evidence Bank**, choose a vibe (**Objective Brief**, **Cornell Study**, **Fact Check**, or **Deep Dive**), and click **"Synthesize Custom Report"** to generate an executive briefing with complete citations.

---

## 3. Plain-English Glossary

Here are four technical terms ScoopScope uses and why they matter to you:

### 1. SSRF Pinning (Server-Side Request Forgery Pinning)
- **What it is**: When ScoopScope visits a web link, it resolves the destination IP address first, checks that it is a safe public address (not a private home or office network), and pins the internet socket directly to that IP.
- **Why it matters**: It prevents malicious websites from tricking ScoopScope into attacking internal network devices or reading sensitive local files.

### 2. Character-Offset Slice
- **What it is**: When ScoopScope quotes an article, it records the exact character coordinates (e.g., from character 1,240 to 1,385) in the downloaded text.
- **Why it matters**: It gives 100% mathematical proof (`extracted_text[start:end] == exact_passage`) that the quote is verbatim from the source, rather than rewritten or paraphrased by an AI.

### 3. JSON-LD Date Provenance
- **What it is**: ScoopScope looks for publication dates in the publisher's official machine-readable metadata (`JSON-LD`), HTML meta tags, or visible article bylines.
- **Why it matters**: Many news sites show the current server date in their HTTP headers, and URL numbers (like `/2024/05/`) can be misleading. ScoopScope only accepts dates that the publisher explicitly declared for that article.

### 4. W3C Text Fragment (`#:~:text=`)
- **What it is**: A modern web standard where a link includes a special snippet of text at the end.
- **Why it matters**: When you click the link in Chrome or Edge, the browser doesn't just open the page—it automatically scrolls right to the exact paragraph and highlights the quote in yellow.

### 5. Official Jurisdiction Guardrails (LA City vs. County & Municipalities)
- **What it is**: Deterministic classification of government websites (e.g., `lacity.gov` for City of LA vs `lacounty.gov` for LA County vs independent LA County city sites like `longbeach.gov` or `norwalkca.gov`) that flags civic ambiguity and boosts matching official records.
- **Why it matters**: Local news and social posts frequently confuse City hall with County supervisors or independent cities. ScoopScope prevents conflating municipal ordinances with countywide health or sheriff policies.

### 6. Deterministic Citations & Export Studio
- **What it is**: Instant one-click report export (Markdown, Plain Text, downloadable `.md`) and deterministic citation formatting (Standard Numbered, APA 7th ed with `(n.d.)`, MLA 9th ed with `Accessed <date>`) built strictly from verified page metadata with zero author or date hallucination.
- **Why it matters**: Journalists, students, and civic researchers need publication-ready citations they can trust. ScoopScope never invents authors or dates when sources omit them.

### 7. Automatic Workspace Save & Clear Workspace Reset
- **What it is**: Silent auto-saving of your entire multi-tab session into your browser's private local storage (`localStorage`) as you work, paired with an instant **"Clear Workspace"** button in the header.
- **Why it matters**: If you accidentally close your tab or refresh your browser, your entire investigation—including your active inquiries, confirmed scopes, Cornell notes evidence, and chosen quotes in the Evidence Bank—is instantly restored. When you're ready to start a completely clean investigation, one click resets the slate immediately without annoying popup prompts.

---

## 4. Shipped Milestones Log

- **Milestone 001 (1)**: Structured claim extraction vertical slice with Gemini schema and opinion/fact separation.
- **Milestone 002 (2A)**: Request ordering protection and timeout reconciliation (312s worst-case bounds).
- **Milestone 003 (2B)**: SearchProvider protocol contract and safe HTTP fetcher foundation with SSRF destination pinning.
- **Milestone 004 (2C)**: Serper search provider, bounded page retrieval (max 2 queries, 5 hits, 3 pages, 90s deadline), and verbatim character-offset passage extraction.
- **Milestone 005 (2C Review)**: Search failure preservation (F1), multi-claim tab ownership (F2), and cooperative extraction deadlines (F3).
- **Milestone 006 (3A)**: 2-round inquiry intake clarification, 3 coherent choices + free text, confirmed scope editing, and research invalidation.
- **Milestone 007 (3B)**: Sticky floating inquiry bar, Cornell notes paired layout, defensible date provenance, `-filetype:pdf` filtering, multi-tab workspace, and Custom Report Studio.
- **Milestone 008 (4A)**: Playbook repo standardization, documentation realignment, and `.gitignore` hygiene fix (Milestone 4A complete and published).
- **Milestone 009 (4A Post-Ship Cleanup)**: Archived completed 4A spec and legacy status file to `docs/archive/`, cleaned root scratch files, and verified clean repo state.
- **Milestone 010 (4C)**: Los Angeles City vs. County jurisdiction guardrails, deterministic official domain classification, civic clarification cards, Cornell notes jurisdiction badges, and 92 new tests (`94baeb2`, 256 passing tests total).
- **Milestone 011 (4C Close-Out & Handoff Initialization)**: Cumulative handoff architecture (`.handoff-builder.md` and `.handoff-planner.md`), mandatory close-out rules in `AGENTS.md`, and staged Milestone 4D spec.
- **Milestone 012 (4D)**: Custom Report Studio exports (Copy MD, Copy Plain Text, Download `.md`), deterministic Citation Style Selector (Standard, APA 7th ed with strict `(n.d.)`, MLA 9th ed with strict `Accessed <date>`) with zero author/date fabrication, and LA County independent municipal classification and search ranking prioritization (`0f5dddf`, 276 passing tests).
- **Milestone 013 (4E)**: Multi-tab workspace `localStorage` auto-save & reload restore, one-click Clear Workspace reset button, and transient spinner guardrails (`e054d1e`, 278 passing tests).
- **Milestone 014 (4F)**: Full Phase 4 live end-to-end headless Chrome browser smoke tests, FastAPI static/index serving contract tests, and Report Studio / workspace DOM synchronization polish (`b049fc0`, 280 passing tests).
- **Milestone 015 (4G)**: Playtest UX polish and multi-tab async search isolation, single collapsible Report Studio with cross-tab evidence counters, sequential list numbering, and Works Cited deduplication (`f75e8ee`, 282 passing tests).
- **Milestone 016 (4H)**: Empty-tab Report Studio hiding, tab bar flex wrapping eliminating Windows horizontal scrollbar, multi-claim results accordion with auto-collapse, closed-by-default technical audit drawer, and quote newline escape sanitization (`83e03bb`, 282 passing tests).
- **Milestone 017 (4G/4H Close-Out & Workflow Sync)**: 4G/4H milestone close-out, selector inventory integrity validation (`test_selector_inventory`), build loop automation workflows, and single-file Gemini planner pack generation (`scripts/pack.py`), 284 passing offline tests across 11 test suites.
- **Milestone 018 (5A)**: One-click "Copy Quote + Citation" action button in Cornell Notes paired evidence cards, deterministic citation styling (Standard, APA, MLA), zero date invention guardrails, and `KNOWN_ISSUES.md` baseline/backlog refresh (`fc05b33`, 285 passing tests across 11 test suites).

