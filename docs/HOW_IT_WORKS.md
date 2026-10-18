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
