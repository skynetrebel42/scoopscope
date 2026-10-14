/* ============================================================
   ScoopScope — Frontend Application Logic
   ============================================================ */

(function () {
    "use strict";

    // --- DOM references ---
    const form = document.getElementById("extraction-form");
    const inputText = document.getElementById("input-text");
    const sourceUrl = document.getElementById("source-url");
    const submitBtn = document.getElementById("submit-btn");
    const charCount = document.getElementById("char-count");

    const errorBanner = document.getElementById("error-banner");
    const errorTitle = document.getElementById("error-title");
    const errorDetail = document.getElementById("error-detail");
    const errorDismiss = document.getElementById("error-dismiss");
    const errorRetry = document.getElementById("error-retry");

    const resultsSection = document.getElementById("results-section");
    const resultsStatus = document.getElementById("results-status");
    const submittedText = document.getElementById("submitted-text");
    const submittedUrlRow = document.getElementById("submitted-url-row");
    const submittedUrl = document.getElementById("submitted-url");
    const claimsList = document.getElementById("claims-list");

    // --- State ---
    let currentSubmissionSeq = 0;
    let currentSubmissionId = null;
    let currentSourceUrl = null;

    // Research action state tracking to prevent stale overwrites and duplicate runs
    let activeResearchSeq = 0;
    let activeResearchClaimId = null;

    // --- Input edit invalidation (R4) ---
    function handleInputEdit() {
        // 1. Invalidate pending extraction so in-flight responses are discarded
        currentSubmissionSeq++;
        // 2. Clear extraction loading state
        setLoading(false);
        // 3. Invalidate active research ownership
        activeResearchSeq++;
        activeResearchClaimId = null;
        // 4. Mark existing rendered claims snapshot as outdated and disable research actions
        markSnapshotOutdated();
    }

    function markSnapshotOutdated() {
        if (!resultsSection.classList.contains("hidden")) {
            let staleBanner = document.getElementById("claims-outdated-banner");
            if (!staleBanner) {
                staleBanner = document.createElement("div");
                staleBanner.id = "claims-outdated-banner";
                staleBanner.className = "notice-banner notice-snippet-only";
                staleBanner.style.borderColor = "var(--border-color)";
                staleBanner.style.background = "var(--surface-color)";
                staleBanner.style.marginBottom = "1rem";
                staleBanner.innerHTML = "<strong>Draft edited:</strong> Input text or source URL has changed. These claims belong to the previous submission. Re-submit to research your updated draft.";
                resultsSection.insertBefore(staleBanner, resultsSection.firstChild);
            }
            // Disable all research buttons on this outdated snapshot
            const researchBtns = claimsList.querySelectorAll(".btn-research");
            researchBtns.forEach(btn => {
                btn.disabled = true;
                btn.title = "Input has changed. Submit to re-extract claims before researching.";
            });
            // Clear any active research loading indicators
            const loadingStates = claimsList.querySelectorAll(".research-loading-state");
            loadingStates.forEach(el => el.remove());
        }
    }

    // --- Character counter & input changes ---
    inputText.addEventListener("input", () => {
        charCount.textContent = inputText.value.length.toLocaleString();
        handleInputEdit();
    });

    sourceUrl.addEventListener("input", () => {
        handleInputEdit();
    });

    // --- Error handling ---
    function showError(title, detail) {
        errorTitle.textContent = title;
        errorDetail.textContent = detail || "";
        errorBanner.classList.remove("hidden");
        errorBanner.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function hideError() {
        errorBanner.classList.add("hidden");
    }

    errorDismiss.addEventListener("click", hideError);

    // --- Loading state ---
    function setLoading(loading) {
        if (loading) {
            submitBtn.classList.add("loading");
            submitBtn.setAttribute("aria-busy", "true");
        } else {
            submitBtn.classList.remove("loading");
            submitBtn.removeAttribute("aria-busy");
        }
    }

    // --- Safe Link Validator ---
    function isSafeHttpUrl(urlStr) {
        if (!urlStr || typeof urlStr !== "string") return false;
        try {
            const parsed = new URL(urlStr);
            return parsed.protocol === "http:" || parsed.protocol === "https:";
        } catch (_) {
            return false;
        }
    }

    // --- Render claims ---
    function renderResults(data, seq) {
        if (seq !== currentSubmissionSeq) {
            return;
        }

        const staleBanner = document.getElementById("claims-outdated-banner");
        if (staleBanner) {
            staleBanner.remove();
        }

        currentSubmissionId = data.submission_id || null;
        currentSourceUrl = data.source_url || null;
        activeResearchClaimId = null;
        activeResearchSeq++;

        // Show the submitted context.
        submittedText.textContent = data.submitted_text;

        if (data.source_url && isSafeHttpUrl(data.source_url)) {
            submittedUrl.textContent = data.source_url;
            submittedUrl.href = data.source_url;
            submittedUrlRow.classList.remove("hidden");
        } else {
            submittedUrlRow.classList.add("hidden");
        }

        // Status line.
        const count = data.claims.length;
        resultsStatus.textContent =
            count === 0
                ? "No claims found"
                : `${count} claim${count !== 1 ? "s" : ""} · ${new Date(data.extracted_at).toLocaleTimeString()}`;

        // Render claim cards.
        claimsList.innerHTML = "";

        if (count === 0) {
            const empty = document.createElement("p");
            empty.className = "evidence-notice";
            empty.textContent = "No extractable claims were found in the submitted text.";
            claimsList.appendChild(empty);
            resultsSection.classList.remove("hidden");
            return;
        }

        data.claims.forEach((claim, idx) => {
            const card = document.createElement("article");
            card.className = "claim-card";
            card.id = `claim-card-${claim.id}`;
            card.style.animationDelay = `${idx * 0.06}s`;

            // Top row: claim number & classification
            const topRow = document.createElement("div");
            topRow.className = "claim-top-row";

            const numSpan = document.createElement("span");
            numSpan.className = "claim-number";
            numSpan.textContent = `#${idx + 1}`;

            const typeSpan = document.createElement("span");
            typeSpan.className = `claim-type-tag ${claim.claim_type}`;
            typeSpan.textContent = claim.claim_type;

            topRow.appendChild(numSpan);
            topRow.appendChild(typeSpan);
            card.appendChild(topRow);

            // Normalized assertion
            const assertionDiv = document.createElement("div");
            assertionDiv.className = "claim-assertion";
            assertionDiv.textContent = claim.normalized_assertion;
            card.appendChild(assertionDiv);

            // Original wording quote
            const originalDiv = document.createElement("div");
            originalDiv.className = "claim-original";
            originalDiv.textContent = `"${claim.original_wording}"`;
            card.appendChild(originalDiv);

            // Details metadata
            const details = [
                { label: "Date", value: claim.explicit_date },
                { label: "Location", value: claim.explicit_location },
                { label: "Quantity", value: claim.explicit_quantity },
                { label: "Qualifications", value: claim.qualifications },
            ];
            const activeDetails = details.filter((d) => Boolean(d.value));
            if (activeDetails.length > 0) {
                const detailsDiv = document.createElement("div");
                detailsDiv.className = "claim-details";
                activeDetails.forEach((d) => {
                    const span = document.createElement("span");
                    span.className = "claim-detail";

                    const lbl = document.createElement("span");
                    lbl.className = "detail-label";
                    lbl.textContent = `${d.label}: `;

                    span.appendChild(lbl);
                    span.appendChild(document.createTextNode(d.value));
                    detailsDiv.appendChild(span);
                });
                card.appendChild(detailsDiv);
            }

            // Milestone 2C: Research action row
            const actionsDiv = document.createElement("div");
            actionsDiv.className = "claim-actions";

            const researchBtn = document.createElement("button");
            researchBtn.type = "button";
            researchBtn.className = "btn-research";
            researchBtn.id = `btn-research-${claim.id}`;
            researchBtn.setAttribute("data-claim-id", claim.id);
            researchBtn.textContent = "Find sources";

            researchBtn.addEventListener("click", () => {
                executeResearch(claim, researchBtn, card);
            });

            actionsDiv.appendChild(researchBtn);
            card.appendChild(actionsDiv);

            // Container for research results
            const researchContainer = document.createElement("div");
            researchContainer.className = "claim-research-container hidden";
            researchContainer.id = `research-container-${claim.id}`;
            card.appendChild(researchContainer);

            claimsList.appendChild(card);
        });

        resultsSection.classList.remove("hidden");
        resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    // --- Research action logic ---
    async function executeResearch(claim, button, card) {
        // Prevent duplicate clicks if this claim or another research is already active
        if (activeResearchClaimId === claim.id) {
            return;
        }

        hideError();
        const researchSeq = ++activeResearchSeq;
        activeResearchClaimId = claim.id;

        const container = card.querySelector(`#research-container-${claim.id}`);
        container.innerHTML = "";
        container.classList.remove("hidden");

        // Button loading state
        button.disabled = true;
        button.textContent = "Researching…";

        // Research loading indicator
        const loadingIndicator = document.createElement("div");
        loadingIndicator.className = "research-loading-state";
        const spinner = document.createElement("span");
        spinner.className = "research-spinner";
        const loadText = document.createElement("span");
        loadText.textContent = "Searching web and safely retrieving candidate pages (up to 90s)…";
        loadingIndicator.appendChild(spinner);
        loadingIndicator.appendChild(loadText);
        container.appendChild(loadingIndicator);

        const payload = {
            submission_id: currentSubmissionId || "adhoc_submission",
            claim_id: claim.id,
            claim_text: claim.normalized_assertion || claim.original_wording,
            claim_type: claim.claim_type,
            explicit_location: claim.explicit_location,
            explicit_date: claim.explicit_date,
            source_url: currentSourceUrl,
        };

        try {
            const res = await fetch("/api/research", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            // Discard if newer submission or research took over
            if (researchSeq !== activeResearchSeq) {
                return;
            }

            let data;
            try {
                data = await res.json();
            } catch (_) {
                if (researchSeq !== activeResearchSeq) return;
                showResearchError(container, "Response error", "Server returned an unparseable response.");
                return;
            }

            if (researchSeq !== activeResearchSeq) {
                return;
            }

            if (!res.ok) {
                const title = data.error || `Error ${res.status}`;
                const detail = data.detail || "Unable to gather sources for this claim.";
                showResearchError(container, title, detail);
                return;
            }

            renderResearchResults(container, data);
        } catch (err) {
            if (researchSeq !== activeResearchSeq) return;
            showResearchError(container, "Network error", "Could not complete research request. Is the server running?");
        } finally {
            if (researchSeq === activeResearchSeq && activeResearchClaimId === claim.id) {
                activeResearchClaimId = null;
            }
            const loading = container.querySelector(".research-loading-state");
            if (loading) {
                loading.remove();
            }
            // Restore button state: disabled with title if snapshot is outdated, otherwise enabled
            if (document.getElementById("claims-outdated-banner")) {
                button.disabled = true;
                button.textContent = "Find sources";
                button.title = "Input has changed. Submit to re-extract claims before researching.";
            } else {
                button.disabled = false;
                button.textContent = "Find sources";
                button.removeAttribute("title");
            }
        }
    }

    function showResearchError(container, title, detail) {
        container.innerHTML = "";
        const errBox = document.createElement("div");
        errBox.className = "notice-banner notice-snippet-only";
        errBox.style.borderColor = "var(--error-border)";
        errBox.style.background = "var(--error-bg)";
        errBox.style.color = "var(--error-text)";

        const strong = document.createElement("strong");
        strong.textContent = `${title}: `;
        errBox.appendChild(strong);
        errBox.appendChild(document.createTextNode(detail));

        container.appendChild(errBox);
    }

    // --- Render Research Results (Search Hits & Retrieved Passages) ---
    function renderResearchResults(container, data) {
        container.innerHTML = "";

        const panel = document.createElement("div");
        panel.className = "claim-research-panel";

        // 1. Summary Bar
        const summaryBar = document.createElement("div");
        summaryBar.className = "research-summary-bar";

        const statsRow = document.createElement("div");
        statsRow.style.fontWeight = "600";
        statsRow.style.color = "var(--text-primary)";
        statsRow.textContent = data.status_message;
        summaryBar.appendChild(statsRow);

        if (data.search_failure_message) {
            const failBanner = document.createElement("div");
            failBanner.className = "notice-banner";
            failBanner.style.borderColor = "var(--error-border)";
            failBanner.style.background = "var(--error-bg)";
            failBanner.style.color = "var(--error-text)";
            failBanner.style.marginTop = "0.5rem";
            const strong = document.createElement("strong");
            strong.textContent = "Search provider unavailable: ";
            failBanner.appendChild(strong);
            failBanner.appendChild(document.createTextNode(data.search_failure_message));
            summaryBar.appendChild(failBanner);
        }

        if (data.queries_used && data.queries_used.length > 0) {
            const queryRow = document.createElement("div");
            queryRow.style.display = "flex";
            queryRow.style.flexWrap = "wrap";
            queryRow.style.gap = "0.4rem";
            queryRow.style.alignItems = "center";

            const qLabel = document.createElement("span");
            qLabel.textContent = "Queries:";
            queryRow.appendChild(qLabel);

            data.queries_used.forEach((q) => {
                const chip = document.createElement("span");
                chip.className = "query-chip";
                chip.textContent = `"${q.query_text}" (${q.query_intent})`;
                queryRow.appendChild(chip);
            });
            summaryBar.appendChild(queryRow);
        }
        panel.appendChild(summaryBar);

        // 2. Search Hits (Unexamined Snippets)
        const hitsSection = document.createElement("div");
        hitsSection.className = "search-hits-group";

        const hitsLabel = document.createElement("div");
        hitsLabel.className = "section-label";
        hitsLabel.textContent = "Search Engine Hits (Unexamined Candidate Links)";
        hitsSection.appendChild(hitsLabel);

        const snippetNotice = document.createElement("div");
        snippetNotice.className = "notice-banner notice-snippet-only";
        snippetNotice.textContent = "A search snippet only indicates an external index match. Snippets are unverified candidate links and NEVER count as examined evidence.";
        hitsSection.appendChild(snippetNotice);

        const hitsList = document.createElement("div");
        hitsList.className = "hits-list";
        hitsList.style.marginTop = "0.5rem";

        if (!data.search_hits || data.search_hits.length === 0) {
            const noHits = document.createElement("p");
            noHits.className = "hit-snippet";
            if (data.search_failure_message) {
                noHits.textContent = `Search unavailable: ${data.search_failure_message}`;
            } else {
                noHits.textContent = "No search hits returned by search provider.";
            }
            hitsList.appendChild(noHits);
        } else {
            data.search_hits.forEach((hit) => {
                const card = document.createElement("div");
                card.className = "hit-card";

                const header = document.createElement("div");
                header.className = "hit-header";

                const link = document.createElement("a");
                link.className = "hit-title";
                link.textContent = hit.title || hit.url;
                if (isSafeHttpUrl(hit.url)) {
                    link.href = hit.url;
                    link.target = "_blank";
                    link.rel = "noopener noreferrer";
                } else {
                    link.href = "#";
                }
                header.appendChild(link);

                const badge = document.createElement("span");
                badge.className = "badge-tag badge-snippet-only";
                badge.textContent = `Snippet Only #${hit.rank}`;
                header.appendChild(badge);
                card.appendChild(header);

                if (hit.snippet) {
                    const snip = document.createElement("div");
                    snip.className = "hit-snippet";
                    snip.textContent = hit.snippet;
                    card.appendChild(snip);
                }

                hitsList.appendChild(card);
            });
        }
        hitsSection.appendChild(hitsList);
        panel.appendChild(hitsSection);

        // 3. Retrieved Candidate Sources & Verbatim Passages
        const sourcesSection = document.createElement("div");
        sourcesSection.className = "retrieved-sources-group";

        const sourcesLabel = document.createElement("div");
        sourcesLabel.className = "section-label";
        sourcesLabel.textContent = "Retrieved Sources & Candidate Passages";
        sourcesSection.appendChild(sourcesLabel);

        const evidenceNotice = document.createElement("div");
        evidenceNotice.className = "notice-banner notice-candidate-evidence";
        evidenceNotice.textContent = "Candidate passages are exact verbatim excerpts from safely retrieved sources. (No supported/contradicted verdict is rendered in this milestone).";
        sourcesSection.appendChild(evidenceNotice);

        const sourcesList = document.createElement("div");
        sourcesList.className = "sources-list";
        sourcesList.style.marginTop = "0.5rem";

        if (!data.retrieved_sources || data.retrieved_sources.length === 0) {
            const noSources = document.createElement("p");
            noSources.className = "hit-snippet";
            noSources.textContent = "No candidate pages were retrieved.";
            sourcesList.appendChild(noSources);
        } else {
            data.retrieved_sources.forEach((src) => {
                const card = document.createElement("div");
                card.className = "source-card";

                const header = document.createElement("div");
                header.className = "source-header";

                const displayUrl = src.final_url || src.initial_url;
                const link = document.createElement("a");
                link.className = "source-title";
                link.textContent = displayUrl;
                if (isSafeHttpUrl(displayUrl)) {
                    link.href = displayUrl;
                    link.target = "_blank";
                    link.rel = "noopener noreferrer";
                }

                const badge = document.createElement("span");
                badge.className = "badge-tag";

                if (src.status === "retrieved") {
                    badge.classList.add("badge-retrieved");
                    badge.textContent = `Retrieved (${src.http_status_code || 200})`;
                } else if (src.status === "ssrf_blocked") {
                    badge.classList.add("badge-ssrf");
                    badge.textContent = "SSRF Blocked";
                } else {
                    badge.classList.add("badge-inaccessible");
                    badge.textContent = `Inaccessible (${src.status})`;
                }

                header.appendChild(link);
                header.appendChild(badge);
                card.appendChild(header);

                // Audit metadata row
                const metaRow = document.createElement("div");
                metaRow.className = "source-meta-row";
                if (src.resolved_ip) {
                    const ipSpan = document.createElement("span");
                    ipSpan.textContent = `IP: ${src.resolved_ip}`;
                    metaRow.appendChild(ipSpan);
                }
                if (src.response_size_bytes) {
                    const sizeSpan = document.createElement("span");
                    sizeSpan.textContent = `Size: ${(src.response_size_bytes / 1024).toFixed(1)} KB`;
                    metaRow.appendChild(sizeSpan);
                }
                if (src.redirect_count > 0) {
                    const redirSpan = document.createElement("span");
                    redirSpan.textContent = `Redirects: ${src.redirect_count}`;
                    metaRow.appendChild(redirSpan);
                }
                card.appendChild(metaRow);

                // Error message if fetch failed
                if (src.error_message) {
                    const errP = document.createElement("div");
                    errP.className = "source-error-msg";
                    errP.textContent = src.error_message;
                    card.appendChild(errP);
                }

                // Matched passages from this source
                const matchingPassages = (data.candidate_passages || []).filter(
                    (p) => p.source_id === src.source_id
                );

                if (src.status === "retrieved") {
                    if (matchingPassages.length > 0) {
                        matchingPassages.forEach((p) => {
                            const pBox = document.createElement("div");
                            pBox.className = "passage-box";

                            const pText = document.createElement("blockquote");
                            pText.className = "passage-text";
                            pText.textContent = `"${p.exact_passage}"`;
                            pBox.appendChild(pText);

                            if (p.relevance_note) {
                                const relNote = document.createElement("div");
                                relNote.className = "passage-relevance";
                                relNote.textContent = `Relevance: ${p.relevance_note}`;
                                pBox.appendChild(relNote);
                            }

                            // Provenance notice
                            const provNotice = document.createElement("div");
                            provNotice.className = "source-meta-row";
                            provNotice.textContent = `Published: Unknown · Event: Unknown · Dependence: Unknown`;
                            pBox.appendChild(provNotice);

                            // Surrounding context toggle
                            if (p.context_surrounding && p.context_surrounding !== p.exact_passage) {
                                const ctxToggle = document.createElement("button");
                                ctxToggle.type = "button";
                                ctxToggle.className = "passage-context-toggle";
                                ctxToggle.textContent = "Show surrounding context";

                                const ctxBox = document.createElement("div");
                                ctxBox.className = "passage-context-box hidden";
                                ctxBox.textContent = p.context_surrounding;

                                ctxToggle.addEventListener("click", () => {
                                    const isHidden = ctxBox.classList.contains("hidden");
                                    ctxBox.classList.toggle("hidden", !isHidden);
                                    ctxToggle.textContent = isHidden ? "Hide surrounding context" : "Show surrounding context";
                                });

                                pBox.appendChild(ctxToggle);
                                pBox.appendChild(ctxBox);
                            }

                            card.appendChild(pBox);
                        });
                    } else {
                        const noP = document.createElement("p");
                        noP.className = "hit-snippet";
                        noP.textContent = "No specific assertion passages identified in retrieved body.";
                        card.appendChild(noP);
                    }

                    // Collapsible complete decoded text viewer
                    if (src.extracted_text) {
                        const viewToggle = document.createElement("button");
                        viewToggle.type = "button";
                        viewToggle.className = "text-viewer-toggle";
                        viewToggle.textContent = "Inspect full extracted page text";

                        const rawBox = document.createElement("div");
                        rawBox.className = "raw-page-text-box hidden";
                        rawBox.textContent = src.extracted_text;

                        viewToggle.addEventListener("click", () => {
                            const isHidden = rawBox.classList.contains("hidden");
                            rawBox.classList.toggle("hidden", !isHidden);
                            viewToggle.textContent = isHidden ? "Hide extracted page text" : "Inspect full extracted page text";
                        });

                        card.appendChild(viewToggle);
                        card.appendChild(rawBox);
                    }
                }

                sourcesList.appendChild(card);
            });
        }

        sourcesSection.appendChild(sourcesList);
        panel.appendChild(sourcesSection);

        container.appendChild(panel);
    }

    // --- Submission logic with request-ordering protection ---
    async function executeSubmission() {
        hideError();

        const text = inputText.value.trim();
        if (!text) {
            showError("Empty input", "Please enter text containing at least one claim.");
            return;
        }

        const seq = ++currentSubmissionSeq;
        activeResearchSeq++;
        activeResearchClaimId = null;
        setLoading(true);

        // Clear previous results while new request is in flight to guarantee clean state ownership
        resultsSection.classList.add("hidden");

        const body = {
            text: inputText.value,
            source_url: sourceUrl.value.trim() || null,
        };

        try {
            const res = await fetch("/api/extract", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });

            if (seq !== currentSubmissionSeq) {
                return;
            }

            let data;
            try {
                data = await res.json();
            } catch (parseErr) {
                if (seq !== currentSubmissionSeq) return;
                showError("Response error", "Server returned an unparseable response.");
                return;
            }

            if (seq !== currentSubmissionSeq) {
                return;
            }

            if (!res.ok) {
                showError(
                    data.error || `Error ${res.status}`,
                    data.detail || "Something went wrong."
                );
                return;
            }

            renderResults(data, seq);
        } catch (err) {
            if (seq !== currentSubmissionSeq) return;
            showError("Network error", "Could not reach the server. Is it running?");
        } finally {
            if (seq === currentSubmissionSeq) {
                setLoading(false);
            }
        }
    }

    // --- Submit listener ---
    form.addEventListener("submit", (e) => {
        e.preventDefault();
        executeSubmission();
    });

    // --- Try Again recovery action ---
    if (errorRetry) {
        errorRetry.addEventListener("click", () => {
            executeSubmission();
        });
    }

    // Expose for testing if running in test environment
    if (typeof window !== "undefined") {
        window.__ScoopScope = {
            get currentSeq() { return currentSubmissionSeq; },
            get activeResearchSeq() { return activeResearchSeq; },
            get activeResearchClaimId() { return activeResearchClaimId; },
            executeSubmission,
            renderResults,
            executeResearch,
            renderResearchResults,
            showError,
            hideError,
            setLoading,
            handleInputEdit,
            markSnapshotOutdated,
        };
    }
})();
