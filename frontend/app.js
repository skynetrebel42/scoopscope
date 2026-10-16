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

    // Milestone 3A: Clarification DOM elements
    const clarificationSection = document.getElementById("clarification-section");
    const clarificationRoundBadge = document.getElementById("clarification-round-badge");
    const clarificationQuestion = document.getElementById("clarification-question");
    const clarificationChoicesGroup = document.getElementById("clarification-choices-group");
    const clarificationFreetext = document.getElementById("clarification-freetext");
    const clarificationSubmitBtn = document.getElementById("clarification-submit-btn");
    const clarificationBroadContainer = document.getElementById("clarification-broad-container");
    const btnBroadInquiry = document.getElementById("btn-broad-inquiry");

    // Milestone 3A: Confirmed Scope DOM elements
    const confirmedScopeCard = document.getElementById("confirmed-scope-card");
    const scopePurposeBadge = document.getElementById("scope-purpose-badge");
    const scopeQuestionInput = document.getElementById("scope-question-input");
    const scopeUpdateBtn = document.getElementById("scope-update-btn");
    const unresolvedScopeContainer = document.getElementById("unresolved-scope-container");
    const unresolvedList = document.getElementById("unresolved-list");
    const limitationNoteBanner = document.getElementById("limitation-note-banner");
    const limitationNoteText = document.getElementById("limitation-note-text");
    const evidenceStageNotice = document.getElementById("evidence-stage-notice");

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

    // Milestone 3A: Clarification & Scope state
    let currentClarificationData = null;
    let clarificationExchanges = [];
    let currentConfirmedScopeQuestion = "";
    let scopeQuestionManuallyEdited = false;
    let currentClaims = [];

    // Research action state tracking to prevent stale overwrites and duplicate runs
    let activeResearchSeq = 0;
    let activeResearchClaimId = null;

    // --- Input edit invalidation (R4 + Milestone 3A) ---
    function handleInputEdit() {
        // 1. Invalidate pending extraction/clarification so in-flight responses are discarded
        currentSubmissionSeq++;
        // 2. Clear loading states
        setLoading(false);
        setClarificationLoading(false);
        // 3. Invalidate active research ownership
        activeResearchSeq++;
        activeResearchClaimId = null;
        // 4. Hide active clarification
        if (clarificationSection) {
            clarificationSection.classList.add("hidden");
        }
        clarificationExchanges = [];
        // 5. Mark existing rendered claims snapshot as outdated and disable research actions
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

    // --- Loading states ---
    function setLoading(loading) {
        if (loading) {
            submitBtn.classList.add("loading");
            submitBtn.setAttribute("aria-busy", "true");
        } else {
            submitBtn.classList.remove("loading");
            submitBtn.removeAttribute("aria-busy");
        }
    }

    function setClarificationLoading(loading) {
        if (!clarificationSubmitBtn) return;
        if (loading) {
            clarificationSubmitBtn.classList.add("loading");
            clarificationSubmitBtn.setAttribute("aria-busy", "true");
            clarificationSubmitBtn.disabled = true;
            if (clarificationChoicesGroup) {
                const choiceBtns = clarificationChoicesGroup.querySelectorAll(".btn-choice");
                choiceBtns.forEach(b => b.disabled = true);
            }
            if (btnBroadInquiry) {
                btnBroadInquiry.disabled = true;
            }
            if (clarificationFreetext) {
                clarificationFreetext.disabled = true;
            }
        } else {
            clarificationSubmitBtn.classList.remove("loading");
            clarificationSubmitBtn.removeAttribute("aria-busy");
            clarificationSubmitBtn.disabled = false;
            if (clarificationChoicesGroup) {
                const choiceBtns = clarificationChoicesGroup.querySelectorAll(".btn-choice");
                choiceBtns.forEach(b => b.disabled = false);
            }
            if (btnBroadInquiry) {
                btnBroadInquiry.disabled = false;
            }
            if (clarificationFreetext) {
                clarificationFreetext.disabled = false;
            }
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

    // --- Clarification Section Logic (Milestone 3A) ---
    function renderClarification(data, seq) {
        if (seq !== currentSubmissionSeq) return;

        currentClarificationData = data;
        const staleBanner = document.getElementById("claims-outdated-banner");
        if (staleBanner) staleBanner.remove();

        resultsSection.classList.add("hidden");
        if (clarificationSection) {
            clarificationSection.classList.remove("hidden");
        }

        if (clarificationRoundBadge) {
            clarificationRoundBadge.textContent = `Round ${data.round_index} of 2`;
        }
        if (clarificationQuestion) {
            clarificationQuestion.textContent = data.question || "Which aspect of this statement would you like to investigate?";
        }

        if (clarificationChoicesGroup) {
            clarificationChoicesGroup.innerHTML = "";
            const choices = data.choices || [];
            choices.forEach((choiceText, idx) => {
                const choiceBtn = document.createElement("button");
                choiceBtn.type = "button";
                choiceBtn.className = "btn-choice";
                choiceBtn.id = `btn-choice-${idx + 1}`;
                choiceBtn.textContent = choiceText;
                choiceBtn.addEventListener("click", () => {
                    executeClarificationChoice(choiceText, null, false);
                });
                clarificationChoicesGroup.appendChild(choiceBtn);
            });
        }

        if (clarificationFreetext) {
            clarificationFreetext.value = "";
        }

        if (clarificationBroadContainer) {
            clarificationBroadContainer.classList.remove("hidden");
        }

        if (clarificationSection) {
            clarificationSection.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }

    async function executeClarificationChoice(choiceText, freeText, explicitBroad) {
        if (!currentClarificationData) return;

        hideError();
        const seq = ++currentSubmissionSeq;
        activeResearchSeq++;
        activeResearchClaimId = null;

        // Record exchange
        clarificationExchanges.push({
            round_index: currentClarificationData.round_index,
            question: currentClarificationData.question || "Which aspect would you like to investigate?",
            selected_choice: choiceText || null,
            free_text: freeText || null,
        });

        setClarificationLoading(true);

        const nextRound = currentClarificationData.round_index + 1;
        const body = {
            text: inputText.value,
            source_url: sourceUrl.value.trim() || null,
            round_index: nextRound,
            exchanges: clarificationExchanges,
            explicit_broad: Boolean(explicitBroad),
        };

        try {
            const res = await fetch("/api/clarify", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });

            if (seq !== currentSubmissionSeq) return;

            let data;
            try {
                data = await res.json();
            } catch (parseErr) {
                if (seq !== currentSubmissionSeq) return;
                showError("Response error", "Server returned an unparseable response.");
                return;
            }

            if (seq !== currentSubmissionSeq) return;

            if (!res.ok) {
                showError(
                    data.error || `Error ${res.status}`,
                    data.detail || "Clarification failed."
                );
                return;
            }

            if (data.clarification_needed) {
                renderClarification(data, seq);
            } else {
                if (clarificationSection) {
                    clarificationSection.classList.add("hidden");
                }
                renderResults(data, seq);
            }
        } catch (err) {
            if (seq !== currentSubmissionSeq) return;
            showError("Network error", "Could not reach the server during clarification.");
        } finally {
            if (seq === currentSubmissionSeq) {
                setClarificationLoading(false);
            }
        }
    }

    // --- Render Confirmed Scope and Checkable Claims ---
    function renderResults(data, seq) {
        if (seq !== currentSubmissionSeq) {
            return;
        }

        const staleBanner = document.getElementById("claims-outdated-banner");
        if (staleBanner) {
            staleBanner.remove();
        }

        if (clarificationSection) {
            clarificationSection.classList.add("hidden");
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

        scopeQuestionManuallyEdited = false;
        const claims = data.subclaims || data.claims || [];
        currentClaims = claims;
        const count = claims.length;

        // Milestone 3A: Confirmed Scope Card population
        if (confirmedScopeCard) {
            currentConfirmedScopeQuestion = data.interpreted_question || (claims[0] && claims[0].normalized_assertion) || data.submitted_text || "";
            if (scopeQuestionInput) {
                scopeQuestionInput.value = currentConfirmedScopeQuestion;
            }
            if (scopePurposeBadge) {
                if (data.purpose === "check_claim") {
                    scopePurposeBadge.textContent = "Check a claim";
                } else if (data.purpose === "understand_context") {
                    scopePurposeBadge.textContent = "Understand context";
                } else if (data.purpose === "trace_origin") {
                    scopePurposeBadge.textContent = "Trace origin";
                } else {
                    scopePurposeBadge.textContent = "Checkable claim";
                }
            }

            if (unresolvedScopeContainer && unresolvedList) {
                unresolvedList.innerHTML = "";
                const uncertainties = data.material_uncertainties || [];
                if (uncertainties.length > 0) {
                    uncertainties.forEach(u => {
                        const li = document.createElement("li");
                        li.className = "unresolved-item";
                        li.textContent = u;
                        unresolvedList.appendChild(li);
                    });
                    unresolvedScopeContainer.classList.remove("hidden");
                } else {
                    unresolvedScopeContainer.classList.add("hidden");
                }
            }

            if (limitationNoteBanner && limitationNoteText) {
                if (data.limitation_note) {
                    limitationNoteText.textContent = data.limitation_note;
                    limitationNoteBanner.classList.remove("hidden");
                } else {
                    limitationNoteBanner.classList.add("hidden");
                }
            }

            confirmedScopeCard.classList.remove("hidden");
        }

        // Status line
        resultsStatus.textContent =
            count === 0
                ? "No checkable claims found"
                : `${count} checkable claim${count !== 1 ? "s" : ""} · Scope confirmed`;

        // Render claim cards
        claimsList.innerHTML = "";

        if (count === 0) {
            const empty = document.createElement("p");
            empty.className = "evidence-notice";
            empty.textContent = "No extractable checkable claims were found in the submitted inquiry.";
            claimsList.appendChild(empty);
            resultsSection.classList.remove("hidden");
            return;
        }

        claims.forEach((claim, idx) => {
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
            const isFactual = claim.claim_type === "factual";
            typeSpan.className = `claim-type-tag ${isFactual ? "factual checkable-claim" : claim.claim_type}`;
            if (isFactual) {
                typeSpan.textContent = "Checkable claim";
                typeSpan.title = "Checkable claim: A statement asserting a verifiable fact. This is a classification, not a verified finding.";
            } else {
                typeSpan.textContent = claim.claim_type;
            }

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
            researchContainer.className = "claim-research-container research-results-container hidden";
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

        const claims = currentClaims || [];
        const claimText = (claims.length > 1 && !scopeQuestionManuallyEdited)
            ? (claim.normalized_assertion || claim.original_wording)
            : (currentConfirmedScopeQuestion || claim.normalized_assertion || claim.original_wording);

        const payload = {
            submission_id: currentSubmissionId || "adhoc_submission",
            claim_id: claim.id,
            claim_text: claimText,
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

    // --- Submission logic with request-ordering protection (Milestone 3A) ---
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
        clarificationExchanges = [];
        setLoading(true);

        // Clear previous results while new request is in flight to guarantee clean state ownership
        resultsSection.classList.add("hidden");
        if (clarificationSection) {
            clarificationSection.classList.add("hidden");
        }

        const body = {
            text: inputText.value,
            source_url: sourceUrl.value.trim() || null,
            round_index: 1,
            exchanges: [],
            explicit_broad: false,
        };

        try {
            const res = await fetch("/api/clarify", {
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

            if (data.clarification_needed) {
                renderClarification(data, seq);
            } else {
                renderResults(data, seq);
            }
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

    // --- Milestone 3A Clarification & Scope Listeners ---
    if (clarificationSubmitBtn) {
        clarificationSubmitBtn.addEventListener("click", () => {
            const ft = clarificationFreetext ? clarificationFreetext.value.trim() : "";
            if (!ft) return;
            executeClarificationChoice(null, ft, false);
        });
    }

    if (clarificationFreetext) {
        clarificationFreetext.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                const ft = clarificationFreetext.value.trim();
                if (!ft) return;
                executeClarificationChoice(null, ft, false);
            }
        });
    }

    if (btnBroadInquiry) {
        btnBroadInquiry.addEventListener("click", () => {
            executeClarificationChoice(null, null, true);
        });
    }

    function handleScopeQuestionEdit() {
        scopeQuestionManuallyEdited = true;
        activeResearchSeq++;
        activeResearchClaimId = null;

        if (scopeQuestionInput) {
            currentConfirmedScopeQuestion = scopeQuestionInput.value.trim();
        }

        // Clear any in-flight loading state or rendered .research-results-container panels on claim cards
        if (claimsList) {
            const containers = claimsList.querySelectorAll(".research-results-container, .claim-research-container");
            containers.forEach(container => {
                container.innerHTML = "";
                container.classList.add("hidden");
            });
            const loadingStates = claimsList.querySelectorAll(".research-loading-state");
            loadingStates.forEach(el => el.remove());
            const researchBtns = claimsList.querySelectorAll(".btn-research");
            researchBtns.forEach(btn => {
                if (!document.getElementById("claims-outdated-banner")) {
                    btn.disabled = false;
                    btn.textContent = "Find sources";
                    btn.removeAttribute("title");
                }
            });
        }
    }

    if (scopeQuestionInput) {
        scopeQuestionInput.addEventListener("input", () => {
            handleScopeQuestionEdit();
        });
    }

    if (scopeUpdateBtn) {
        scopeUpdateBtn.addEventListener("click", () => {
            handleScopeQuestionEdit();
            scopeUpdateBtn.textContent = "Saved";
            setTimeout(() => {
                scopeUpdateBtn.textContent = "Update";
            }, 1200);
        });
    }

    // Expose for testing if running in test environment
    if (typeof window !== "undefined") {
        window.__ScoopScope = {
            get currentSeq() { return currentSubmissionSeq; },
            get activeResearchSeq() { return activeResearchSeq; },
            get activeResearchClaimId() { return activeResearchClaimId; },
            get clarificationExchanges() { return clarificationExchanges; },
            get currentConfirmedScopeQuestion() { return currentConfirmedScopeQuestion; },
            get scopeQuestionManuallyEdited() { return scopeQuestionManuallyEdited; },
            get currentClaims() { return currentClaims; },
            handleScopeQuestionEdit,
            executeSubmission,
            renderResults,
            renderClarification,
            executeClarificationChoice,
            executeResearch,
            renderResearchResults,
            showError,
            hideError,
            setLoading,
            setClarificationLoading,
            handleInputEdit,
            markSnapshotOutdated,
        };
    }
})();
