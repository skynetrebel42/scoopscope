/* ============================================================
   ScoopScope — Frontend Application Logic
   ============================================================ */

(function () {
    "use strict";

    // Milestone 4E: Storage Key Constant (Decision 014)
    const WORKSPACE_STORAGE_KEY = "scoopscope_workspace_v1";

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

    // Milestone 3B: Sticky Floating Inquiry Bar
    const stickyInquiryBar = document.getElementById("sticky-inquiry-bar");
    const stickyInquiryText = document.getElementById("sticky-inquiry-text");
    const btnStickyEdit = document.getElementById("btn-sticky-edit");

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

    // Top-Level Session Inquiry Tabs (Milestone 3B Multi-Tab Upgrade)
    const sessionTabsBar = document.getElementById("session-tabs-bar");
    const sessionTabsList = document.getElementById("session-tabs-list");
    const btnNewSession = document.getElementById("btn-new-session");
    const btnClearWorkspace = document.getElementById("btn-clear-workspace");

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

    // Milestone 3B Multi-Tab & Evidence Bank State
    let sessionInquiries = [];
    let activeSessionId = null;
    let claimResearchTabs = {};
    let activeClaimTabId = {};
    let selectedQuotes = {};
    let activeCitationStyle = "standard";

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
        hideLoadingProgress();
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
        const claimInput = document.getElementById("claim-input");
        if (claimInput) claimInput.value = inputText.value;
        handleInputEdit();
        updateActiveSessionState();
        saveWorkspaceToStorage();
    });

    const claimInputInit = document.getElementById("claim-input");
    if (claimInputInit) {
        claimInputInit.addEventListener("input", () => {
            if (inputText) inputText.value = claimInputInit.value;
            charCount.textContent = claimInputInit.value.length.toLocaleString();
            handleInputEdit();
            updateActiveSessionState();
            saveWorkspaceToStorage();
        });
    }

    sourceUrl.addEventListener("input", () => {
        handleInputEdit();
        updateActiveSessionState();
        saveWorkspaceToStorage();
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

    // --- Loading Progress Banner & Sticky Bar (Milestone 3B) ---
    function updateStickyInquiryBar(text) {
        if (!stickyInquiryBar || !stickyInquiryText) return;
        const clean = (text || "").trim();
        if (clean) {
            stickyInquiryText.textContent = clean;
            stickyInquiryBar.classList.remove("hidden");
        } else {
            stickyInquiryBar.classList.add("hidden");
        }
    }

    if (btnStickyEdit) {
        btnStickyEdit.addEventListener("click", () => {
            const formEl = document.getElementById("extraction-form") || document.getElementById("input-section");
            if (formEl) {
                formEl.classList.remove("compact-collapsed");
            }
            if (scopeQuestionInput && confirmedScopeCard && !confirmedScopeCard.classList.contains("hidden")) {
                confirmedScopeCard.scrollIntoView({ behavior: "smooth", block: "center" });
                scopeQuestionInput.focus();
            } else if (clarificationSection && !clarificationSection.classList.contains("hidden")) {
                clarificationSection.scrollIntoView({ behavior: "smooth", block: "start" });
            } else if (inputText) {
                inputText.scrollIntoView({ behavior: "smooth", block: "center" });
                inputText.focus();
            }
        });
    }

    const btnEditInquiry = document.getElementById("btn-edit-inquiry");
    if (btnEditInquiry) {
        btnEditInquiry.addEventListener("click", () => {
            const formEl = document.getElementById("extraction-form") || document.getElementById("input-section");
            if (formEl) {
                formEl.classList.remove("compact-collapsed");
            }
            if (inputText) {
                inputText.scrollIntoView({ behavior: "smooth", block: "center" });
                inputText.focus();
            }
        });
    }

    function buildTextFragmentUrl(sourceUrl, quoteText) {
        if (!sourceUrl || typeof sourceUrl !== "string") return "";
        if (!quoteText || typeof quoteText !== "string") return sourceUrl;

        const cleanBase = sourceUrl.split("#")[0];
        const normalized = quoteText.replace(/[\r\n\t]+/g, " ").replace(/^["']|["']$/g, "").trim();
        const words = normalized.split(/\s+/).filter(Boolean);
        if (words.length === 0) return cleanBase;

        let fragment = "";
        if (words.length <= 8) {
            fragment = encodeURIComponent(words.join(" "));
        } else {
            const startWords = encodeURIComponent(words.slice(0, 6).join(" "));
            const endWords = encodeURIComponent(words.slice(-6).join(" "));
            fragment = `${startWords},${endWords}`;
        }
        return `${cleanBase}#:~:text=${fragment}`;
    }

    function showLoadingProgress(message) {
        const banner = document.getElementById("loading-progress-banner");
        const msgEl = document.getElementById("loading-progress-message");
        if (banner && msgEl) {
            msgEl.textContent = message;
            banner.classList.remove("hidden");
        }
        if (stickyInquiryBar) {
            stickyInquiryBar.classList.remove("hidden");
        }
    }

    function hideLoadingProgress() {
        const banner = document.getElementById("loading-progress-banner");
        if (banner) {
            banner.classList.add("hidden");
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

        if (activeSessionId) {
            const sess = sessionInquiries.find(s => s.id === activeSessionId);
            if (sess) {
                sess.data = data;
                sess.isClarification = true;
                sess.clarificationExchanges = clarificationExchanges;
            }
            renderSessionTabs();
        }

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

        const originSessionId = activeSessionId;
        const originSession = originSessionId ? sessionInquiries.find(s => s.id === originSessionId) : null;

        hideError();
        const seq = ++currentSubmissionSeq;
        activeResearchSeq++;
        activeResearchClaimId = null;

        // Record exchange
        const exch = {
            round_index: currentClarificationData.round_index,
            question: currentClarificationData.question || "Which aspect would you like to investigate?",
            selected_choice: choiceText || null,
            free_text: freeText || null,
        };
        clarificationExchanges.push(exch);
        if (originSession) {
            originSession.clarificationExchanges = clarificationExchanges;
        }

        setClarificationLoading(true);
        showLoadingProgress("Updating inquiry scope…");

        const nextRound = currentClarificationData.round_index + 1;
        const body = {
            text: inputText.value,
            source_url: sourceUrl ? (sourceUrl.value.trim() || null) : null,
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
                const hasSwitched = Boolean(originSessionId && activeSessionId && activeSessionId !== originSessionId);
                if (!hasSwitched) {
                    showError("Response error", "Server returned an unparseable response.");
                }
                return;
            }

            if (seq !== currentSubmissionSeq) return;

            if (!res.ok) {
                const hasSwitched = Boolean(originSessionId && activeSessionId && activeSessionId !== originSessionId);
                if (!hasSwitched) {
                    showError(
                        data.error || `Error ${res.status}`,
                        data.detail || "Clarification failed."
                    );
                }
                return;
            }

            if (originSession) {
                if (data.clarification_needed) {
                    originSession.data = data;
                    originSession.isClarification = true;
                    originSession.clarificationExchanges = clarificationExchanges;
                } else {
                    originSession.data = data;
                    originSession.isClarification = false;
                    originSession.scopeQuestion = data.confirmed_scope_question || data.interpreted_question || (data.claims && data.claims[0] && data.claims[0].normalized_assertion) || currentConfirmedScopeQuestion;
                    originSession.claims = data.claims || [];
                }
                originSession.isClarifying = false;
            }

            const hasSwitched = Boolean(originSessionId && activeSessionId && activeSessionId !== originSessionId);
            if (!hasSwitched) {
                if (data.clarification_needed) {
                    renderClarification(data, seq);
                } else {
                    if (clarificationSection) {
                        clarificationSection.classList.add("hidden");
                    }
                    renderResults(data, seq);
                }
                renderSessionTabs();
                saveWorkspaceToStorage();
            } else {
                renderSessionTabs();
                saveWorkspaceToStorage();
            }
        } catch (err) {
            if (seq !== currentSubmissionSeq) return;
            const hasSwitched = Boolean(originSessionId && activeSessionId && activeSessionId !== originSessionId);
            if (!hasSwitched) {
                showError("Network error", "Could not reach the server during clarification.");
            }
        } finally {
            const hasSwitched = Boolean(originSessionId && activeSessionId && activeSessionId !== originSessionId);
            if (!hasSwitched && seq === currentSubmissionSeq) {
                setClarificationLoading(false);
                hideLoadingProgress();
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

        if (activeSessionId) {
            const sess = sessionInquiries.find(s => s.id === activeSessionId);
            if (sess) {
                sess.data = data;
                sess.isClarification = false;
                sess.claims = claims;
                sess.scopeQuestion = currentConfirmedScopeQuestion;
            }
            renderSessionTabs();
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
            const isCausal = claim.claim_type === "causal";
            typeSpan.className = `claim-type-tag ${isFactual ? "factual checkable-claim" : isCausal ? "causal checkable-claim" : claim.claim_type}`;
            if (isFactual) {
                typeSpan.textContent = "Checkable claim";
                typeSpan.title = "Checkable claim: A statement asserting a verifiable fact. This is a classification, not a verified finding.";
            } else if (isCausal) {
                typeSpan.textContent = "Checkable claim (causal)";
                typeSpan.title = "Checkable claim (causal): A statement asserting a causal link. This is a classification, not a verified finding.";
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
    async function executeResearch(claim, button, card, customQueryText = null) {
        // Prevent duplicate clicks if this claim or another research is already active
        if (activeResearchClaimId === claim.id) {
            return;
        }

        const originSessionId = activeSessionId;
        const originSession = sessionInquiries.find(s => s.id === originSessionId);
        if (!originSession) return;

        hideError();
        const researchSeq = ++activeResearchSeq;
        activeResearchClaimId = claim.id;

        const container = card.querySelector(`#research-container-${claim.id}`) || card.querySelector(".claim-research-container");
        if (container) {
            container.innerHTML = "";
            container.classList.remove("hidden");
        }

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
        if (container) {
            container.appendChild(loadingIndicator);
        }

        showLoadingProgress("Searching sources, extracting verbatim quotes, and analyzing how they fit your inquiry…");

        let claimText = "";
        if (customQueryText) {
            claimText = customQueryText;
            currentConfirmedScopeQuestion = customQueryText;
            scopeQuestionManuallyEdited = true;
            if (scopeQuestionInput) {
                scopeQuestionInput.value = customQueryText;
            }
        } else {
            const claims = currentClaims || [];
            claimText = (claims.length > 1 && !scopeQuestionManuallyEdited)
                ? (claim.normalized_assertion || claim.original_wording)
                : (currentConfirmedScopeQuestion || claim.normalized_assertion || claim.original_wording);
        }

        updateStickyInquiryBar(claimText);

        const payload = {
            submission_id: currentSubmissionId || "adhoc_submission",
            claim_id: claim.id,
            claim_text: claimText,
            claim_type: claim.claim_type,
            explicit_location: claim.explicit_location,
            explicit_date: claim.explicit_date,
            source_url: currentSourceUrl,
            override_query: customQueryText || null,
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
                if (activeSessionId === originSessionId && container) {
                    showResearchError(container, "Response error", "Server returned an unparseable response.");
                }
                return;
            }

            if (researchSeq !== activeResearchSeq) {
                return;
            }

            if (!res.ok) {
                if (activeSessionId === originSessionId && container) {
                    const title = data.error || `Error ${res.status}`;
                    const detail = data.detail || "Unable to gather sources for this claim.";
                    showResearchError(container, title, detail);
                }
                return;
            }

            // Milestone 3B Multi-Tab: Append new run strictly to originSession
            if (!originSession.claimResearchTabs) {
                originSession.claimResearchTabs = {};
            }
            if (!originSession.claimResearchTabs[claim.id]) {
                originSession.claimResearchTabs[claim.id] = [];
            }
            const runs = originSession.claimResearchTabs[claim.id];
            let tabTitle = "";
            if (runs.length === 0) {
                tabTitle = "Tab 1: Initial Inquiry";
            } else {
                let qDisplay = (customQueryText || claimText).trim();
                if (qDisplay.length > 24) {
                    qDisplay = qDisplay.slice(0, 22) + "…";
                }
                tabTitle = `Tab ${runs.length + 1}: ${qDisplay}`;
            }

            const newRun = {
                id: "run_" + Date.now() + "_" + Math.random().toString(36).slice(2, 6),
                title: tabTitle,
                query: customQueryText || claimText,
                data: data,
                timestamp: Date.now(),
            };
            runs.push(newRun);

            if (!originSession.activeClaimTabId) {
                originSession.activeClaimTabId = {};
            }
            originSession.activeClaimTabId[claim.id] = newRun.id;

            if (!originSession.selectedQuotes) {
                originSession.selectedQuotes = {};
            }
            // Auto-select substantive candidate quotes in originSession
            (data.candidate_passages || []).forEach(p => {
                const qKey = getQuoteKey(claim.id, p);
                if (originSession.selectedQuotes[qKey] === undefined) {
                    originSession.selectedQuotes[qKey] = {
                        checked: true,
                        passage: p,
                        claimId: claim.id,
                    };
                }
            });

            if (activeSessionId === originSessionId) {
                claimResearchTabs = originSession.claimResearchTabs;
                activeClaimTabId = originSession.activeClaimTabId;
                selectedQuotes = originSession.selectedQuotes;
                updateActiveSessionState();
                saveWorkspaceToStorage();
                if (container && card) {
                    renderClaimResearchTabsWorkspace(container, claim, button, card);
                }
                const formEl = document.getElementById("extraction-form") || document.getElementById("input-section");
                if (formEl) formEl.classList.add("compact-collapsed");
            } else {
                saveWorkspaceToStorage();
                renderSessionTabs();
            }
        } catch (err) {
            if (researchSeq !== activeResearchSeq) return;
            if (activeSessionId === originSessionId && container) {
                showResearchError(container, "Network error", "Could not complete research request. Is the server running?");
            }
        } finally {
            if (activeSessionId === originSessionId) {
                hideLoadingProgress();
                if (researchSeq === activeResearchSeq && activeResearchClaimId === claim.id) {
                    activeResearchClaimId = null;
                }
                if (container) {
                    const loading = container.querySelector(".research-loading-state");
                    if (loading) {
                        loading.remove();
                    }
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

    // --- Quote and Markdown Helpers ---
    function getQuoteKey(claimId, p) {
        return `${claimId}_${p.source_url}_${p.start_offset}_${p.end_offset}`;
    }

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function formatInline(text) {
        let t = escapeHtml(text);
        t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
        t = t.replace(/\*([^*]+)\*/g, "<em>$1</em>");
        t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
        return t;
    }

    function renderMarkdown(md) {
        if (!md) return "";
        const lines = md.split("\n");
        let html = "";
        let inList = false;
        let listType = null;

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];

            if (line.startsWith("#### ")) {
                if (inList) { html += listType === "ol" ? "</ol>" : "</ul>"; inList = false; }
                html += `<h4>${escapeHtml(line.slice(5))}</h4>`;
                continue;
            }
            if (line.startsWith("### ")) {
                if (inList) { html += listType === "ol" ? "</ol>" : "</ul>"; inList = false; }
                html += `<h3>${escapeHtml(line.slice(4))}</h3>`;
                continue;
            }
            if (line.startsWith("## ")) {
                if (inList) { html += listType === "ol" ? "</ol>" : "</ul>"; inList = false; }
                html += `<h2>${escapeHtml(line.slice(3))}</h2>`;
                continue;
            }
            if (line.startsWith("# ")) {
                if (inList) { html += listType === "ol" ? "</ol>" : "</ul>"; inList = false; }
                html += `<h1>${escapeHtml(line.slice(2))}</h1>`;
                continue;
            }
            if (line.trim() === "---" || line.trim() === "***") {
                if (inList) { html += listType === "ol" ? "</ol>" : "</ul>"; inList = false; }
                html += "<hr>";
                continue;
            }
            if (line.startsWith("> ")) {
                if (inList) { html += listType === "ol" ? "</ol>" : "</ul>"; inList = false; }
                html += `<blockquote>${formatInline(line.slice(2))}</blockquote>`;
                continue;
            }
            if (/^[-*]\s+/.test(line)) {
                if (!inList || listType !== "ul") {
                    if (inList) html += listType === "ol" ? "</ol>" : "</ul>";
                    html += "<ul>";
                    inList = true;
                    listType = "ul";
                }
                html += `<li>${formatInline(line.replace(/^[-*]\s+/, ""))}</li>`;
                continue;
            }
            if (/^\d+\.\s+/.test(line)) {
                const match = line.match(/^(\d+)\.\s+/);
                const startNum = match ? match[1] : "1";
                if (!inList || listType !== "ol") {
                    if (inList) html += listType === "ol" ? "</ol>" : "</ul>";
                    const startAttr = startNum !== "1" ? ` start="${startNum}"` : "";
                    html += `<ol${startAttr}>`;
                    inList = true;
                    listType = "ol";
                }
                html += `<li>${formatInline(line.replace(/^\d+\.\s+/, ""))}</li>`;
                continue;
            }
            if (inList && line.trim() === "") {
                // Lookahead: check if next non-empty line continues list
                let nextIdx = i + 1;
                while (nextIdx < lines.length && lines[nextIdx].trim() === "") {
                    nextIdx++;
                }
                if (nextIdx < lines.length) {
                    const nextTrim = lines[nextIdx].trim();
                    if (listType === "ol" && /^\d+\.\s+/.test(nextTrim)) {
                        continue;
                    }
                    if (listType === "ul" && /^[-*]\s+/.test(nextTrim)) {
                        continue;
                    }
                }
                html += listType === "ol" ? "</ol>" : "</ul>";
                inList = false;
                continue;
            }
            if (inList && /^\s{2,}\S/.test(line)) {
                html += `<br><span style="display:inline-block; margin-left:1.5rem;">${formatInline(line.trim())}</span>`;
                continue;
            }
            if (line.trim()) {
                if (inList) { html += listType === "ol" ? "</ol>" : "</ul>"; inList = false; }
                html += `<p>${formatInline(line)}</p>`;
            }
        }
        if (inList) {
            html += listType === "ol" ? "</ol>" : "</ul>";
        }
        return html;
    }

    function createSectionCheckbox(id, labelText, defaultChecked) {
        const wrapper = document.createElement("label");
        wrapper.className = "report-checkbox-label";
        const input = document.createElement("input");
        input.type = "checkbox";
        input.id = id;
        input.checked = defaultChecked;
        wrapper.appendChild(input);
        wrapper.appendChild(document.createTextNode(labelText));
        return { wrapper, input };
    }

    let primaryGeneratedMarkdown = "";
    let primaryReportSources = [];

    function renderCustomReport() {
        const customSec = document.getElementById("custom-report-section");
        const reportStudio = document.getElementById("report-studio-section");
        const checked = Object.values(selectedQuotes).filter(item => item && item.checked);

        if (checked.length === 0) {
            if (customSec) customSec.classList.add("hidden");
            if (reportStudio) reportStudio.classList.add("hidden");
            return;
        }

        if (customSec) customSec.classList.remove("hidden");
        if (reportStudio) reportStudio.classList.remove("hidden");

        const count = checked.length;
        const uniqueSources = new Set(checked.map(item => item.passage.source_url)).size;
        const text = `${count} quote${count === 1 ? "" : "s"} from ${uniqueSources} source${uniqueSources === 1 ? "" : "s"} selected across tabs`;
        document.querySelectorAll(".evidence-counter-badge").forEach(el => {
            el.textContent = text;
        });

        document.querySelectorAll("#citation-style-select, .citation-style-select").forEach(sel => {
            sel.value = activeCitationStyle || "standard";
        });

        const seenUrls = new Set();
        primaryReportSources = [];
        for (const item of checked) {
            const p = item.passage;
            const normUrl = (p.source_url || "").trim().toLowerCase();
            const dedupeKey = normUrl || (p.source_title || "");
            if (dedupeKey && seenUrls.has(dedupeKey)) {
                continue;
            }
            if (dedupeKey) {
                seenUrls.add(dedupeKey);
            }
            let domain = "";
            if (p.source_url) {
                try {
                    domain = new URL(p.source_url, "http://localhost").hostname.replace(/^www\./, "");
                } catch (_) {
                    domain = p.source_url;
                }
            }
            primaryReportSources.push({
                url: p.source_url,
                domain: domain,
                title: p.source_title || domain || "Source Record",
                publication_date: p.publication_date,
                retrieval_date: p.retrieval_timestamp || new Date().toISOString().split("T")[0],
                jurisdiction_tag: p.jurisdiction_tag || p.jurisdiction_badge || "",
                jurisdiction_code: p.jurisdiction_code || "",
            });
        }

        const outputCard = document.getElementById("custom-report-output-card") || (customSec && customSec.querySelector(".report-output-card"));
        const outputBody = outputCard ? outputCard.querySelector(".report-content-body") : null;

        if (outputCard && outputBody) {
            const inquiryTitle = currentConfirmedScopeQuestion || (checked[0] && checked[0].passage && (checked[0].passage.relevance_explanation || checked[0].passage.exact_passage)) || "Investigation Findings";
            const passagesList = checked.map(c => `- "${c.passage.exact_passage}" ([Source](${c.passage.source_url}))`).join("\n");
            const worksCitedText = primaryReportSources.map((s, idx) => `${idx + 1}. ${formatCitation(s, activeCitationStyle || "standard")}`).join("\n");

            primaryGeneratedMarkdown = `# Investigation Report: ${inquiryTitle}\n\n## Topic & Inquiry Synthesis\nRetrieved verbatim evidence addressing terms in the inquiry. Review the extracted quotes below.\n\n## Structured Evidence Bank\n${passagesList}\n\n## Works Cited\n${worksCitedText}`;

            outputBody.innerHTML = renderMarkdown(primaryGeneratedMarkdown);
            outputCard.classList.remove("hidden");
        }
    }

    function updateAllEvidenceCounters() {
        const checked = Object.values(selectedQuotes).filter(item => item && item.checked);
        const count = checked.length;
        const uniqueSources = new Set(checked.map(item => item.passage.source_url)).size;
        const text = `${count} quote${count === 1 ? "" : "s"} from ${uniqueSources} source${uniqueSources === 1 ? "" : "s"} selected across tabs`;
        document.querySelectorAll(".evidence-counter-badge").forEach(el => {
            el.textContent = text;
        });

        const customReportSec = document.getElementById("custom-report-section");
        const reportStudioSec = document.getElementById("report-studio-section");
        if (count > 0) {
            if (customReportSec) customReportSec.classList.remove("hidden");
            if (reportStudioSec) reportStudioSec.classList.remove("hidden");
            renderCustomReport();
        } else {
            if (customReportSec) customReportSec.classList.add("hidden");
            if (reportStudioSec) reportStudioSec.classList.add("hidden");
        }
    }

    // --- Milestone 4D Report Export & Citation Helpers ---
    function stripMarkdownToPlainText(md) {
        if (!md) return "";
        return md
            .replace(/```[\s\S]*?```/g, "")
            .replace(/^#{1,6}\s+(.*)$/gm, "$1")
            .replace(/\*\*(.*?)\*\*/g, "$1")
            .replace(/\*(.*?)\*/g, "$1")
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1 ($2)")
            .replace(/^>\s+/gm, "")
            .replace(/^[-*]\s+/gm, "• ")
            .replace(/^[*-]{3,}$/gm, "---")
            .trim();
    }

    function downloadFile(filename, content, mimeType) {
        const blob = new Blob([content], { type: mimeType || "text/markdown;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => { URL.revokeObjectURL(url); }, 1000);
    }

    function formatCitation(source, style) {
        let domain = source.domain;
        if (!domain && source.url) {
            try {
                domain = new URL(source.url, "http://localhost").hostname.replace(/^www\./, "");
            } catch (_) {
                domain = source.url;
            }
        }
        const title = source.title || domain || "Source Record";
        const pub = source.publication_date;
        const ret = source.retrieval_date || "Retrieved during investigation";
        const jurisBadge = source.jurisdiction_tag ? ` [${source.jurisdiction_tag}]` : "";
        const cleanStyle = (style || "standard").toLowerCase();

        if (cleanStyle === "apa") {
            const dateStr = (pub && pub.length >= 4) ? `(${pub.slice(0, 4)})` : "(n.d.)";
            return `${title}. ${dateStr}. *${domain}*. [${source.url}](${source.url})${jurisBadge}`;
        } else if (cleanStyle === "mla") {
            const dateStr = pub ? `${pub}, ` : "";
            return `"${title}." *${domain}*, ${dateStr}[${source.url}](${source.url}). Accessed ${ret}.${jurisBadge}`;
        } else {
            const pubStr = pub || "Date unknown";
            return `**${domain}** — [${title}](${source.url})${jurisBadge}\n   - *Published*: ${pubStr} | *Retrieval*: ${ret}`;
        }
    }

    function updateReportWorksCited(markdown, sources, style) {
        if (!markdown) return "";
        const worksCitedLines = ["## Works Cited & Bibliography\n"];
        if (!sources || sources.length === 0) {
            worksCitedLines.push("*No sources recorded.*");
        } else {
            const seen = new Set();
            const deduped = [];
            for (const s of sources) {
                const norm = (s.url || "").trim().toLowerCase() || (s.title || "");
                if (norm && seen.has(norm)) continue;
                if (norm) seen.add(norm);
                deduped.push(s);
            }
            deduped.forEach((s, idx) => {
                worksCitedLines.push(`${idx + 1}. ${formatCitation(s, style)}`);
            });
        }
        const worksCitedText = worksCitedLines.join("\n");
        if (/(?:##\s+Works\s+Cited|##\s+Bibliography)/i.test(markdown)) {
            return markdown.replace(/(?:##\s+Works\s+Cited|##\s+Bibliography)[\s\S]*$/i, worksCitedText);
        }
        return markdown + "\n\n" + worksCitedText;
    }

    // Expose helpers globally for test runner inspection
    window.stripMarkdownToPlainText = stripMarkdownToPlainText;
    window.formatCitation = formatCitation;
    window.updateReportWorksCited = updateReportWorksCited;

    // --- Report & Evidence Bank Studio Panel Builder ---
    function renderReportBuilderPanel(claim, data) {
        const reportPanel = document.createElement("div");
        reportPanel.className = "report-builder-panel";

        // Header with title and counter
        const header = document.createElement("div");
        header.className = "report-builder-header";

        const titleWrap = document.createElement("div");
        titleWrap.className = "report-builder-title";
        titleWrap.innerHTML = `<span aria-hidden="true">📄</span> Generate Page Report & Evidence Bank`;
        header.appendChild(titleWrap);

        const counterWrap = document.createElement("div");
        counterWrap.className = "report-counter-wrap";

        const counterBadge = document.createElement("span");
        counterBadge.className = "evidence-counter-badge";
        counterWrap.appendChild(counterBadge);

        const selectAllBtn = document.createElement("button");
        selectAllBtn.type = "button";
        selectAllBtn.className = "btn-counter-toggle";
        selectAllBtn.textContent = "Select All";
        selectAllBtn.addEventListener("click", () => {
            Object.keys(selectedQuotes).forEach(k => {
                if (selectedQuotes[k]) selectedQuotes[k].checked = true;
            });
            document.querySelectorAll(".quote-select-checkbox").forEach(cb => { cb.checked = true; });
            updateAllEvidenceCounters();
            updateActiveSessionState();
            saveWorkspaceToStorage();
        });
        counterWrap.appendChild(selectAllBtn);

        const clearBtn = document.createElement("button");
        clearBtn.type = "button";
        clearBtn.className = "btn-counter-toggle";
        clearBtn.textContent = "Clear";
        clearBtn.addEventListener("click", () => {
            Object.keys(selectedQuotes).forEach(k => {
                if (selectedQuotes[k]) selectedQuotes[k].checked = false;
            });
            document.querySelectorAll(".quote-select-checkbox").forEach(cb => { cb.checked = false; });
            updateAllEvidenceCounters();
            updateActiveSessionState();
            saveWorkspaceToStorage();
        });
        counterWrap.appendChild(clearBtn);

        header.appendChild(counterWrap);
        reportPanel.appendChild(header);

        // Controls grid: Vibe Selector, Citation Style Selector & Section Checkboxes
        const controls = document.createElement("div");
        controls.className = "report-builder-controls";

        // Vibe Selector
        const vibeGroup = document.createElement("div");
        vibeGroup.className = "report-control-group";
        const vibeLabel = document.createElement("label");
        vibeLabel.className = "report-control-label";
        vibeLabel.textContent = "Report Vibe / Style";
        vibeGroup.appendChild(vibeLabel);

        const vibeSelect = document.createElement("select");
        vibeSelect.className = "report-vibe-select";
        const vibes = [
            { value: "objective_brief", label: "Objective Briefing — Concise, neutral executive overview" },
            { value: "cornell_study", label: "Cornell Study Guide — Cues, key takeaways, and synthesis for learning" },
            { value: "fact_check", label: "Fact-Check Breakdown — What the evidence supports, contradicts, or leaves unknown" },
            { value: "deep_dive", label: "Topic Deep-Dive — Contextual narrative connecting all selected sources" },
        ];
        vibes.forEach(v => {
            const opt = document.createElement("option");
            opt.value = v.value;
            opt.textContent = v.label;
            vibeSelect.appendChild(opt);
        });
        vibeGroup.appendChild(vibeSelect);
        controls.appendChild(vibeGroup);

        // Citation Style Selector (Milestone 4D Upgrade)
        const citationGroup = document.createElement("div");
        citationGroup.className = "report-control-group";
        const citationLabel = document.createElement("label");
        citationLabel.className = "report-control-label";
        citationLabel.textContent = "Citation Style (Works Cited)";
        citationGroup.appendChild(citationLabel);

        const citationSelect = document.createElement("select");
        citationSelect.className = "report-citation-select citation-style-select";
        const citationOptions = [
            { value: "standard", label: "Standard Numbered — [1] Title — Domain (Date) [Jurisdiction]" },
            { value: "apa", label: "APA (7th Edition) — Author/Title. (Year or n.d.). Site. URL [Jurisdiction]" },
            { value: "mla", label: "MLA (9th Edition) — \"Title.\" Site, Date, URL. Accessed Date [Jurisdiction]" },
        ];
        citationOptions.forEach(optData => {
            const opt = document.createElement("option");
            opt.value = optData.value;
            opt.textContent = optData.label;
            citationSelect.appendChild(opt);
        });
        citationSelect.value = activeCitationStyle || "standard";
        citationGroup.appendChild(citationSelect);
        controls.appendChild(citationGroup);

        // Section checkboxes
        const sectionsGroup = document.createElement("div");
        sectionsGroup.className = "report-control-group";
        const sectionsLabel = document.createElement("label");
        sectionsLabel.className = "report-control-label";
        sectionsLabel.textContent = "Included Report Sections";
        sectionsGroup.appendChild(sectionsLabel);

        const sectionsGrid = document.createElement("div");
        sectionsGrid.className = "report-sections-grid";

        const chkSummary = createSectionCheckbox("include_summary", "Topic & Inquiry Synthesis", true);
        const chkEvidenceBank = createSectionCheckbox("include_evidence_bank", "Structured Evidence Bank", true);
        const chkWorksCited = createSectionCheckbox("include_works_cited", "Works Cited / Bibliography", true);
        const chkOpenQuestions = createSectionCheckbox("include_open_questions", "Unresolved Next Questions", true);

        sectionsGrid.appendChild(chkSummary.wrapper);
        sectionsGrid.appendChild(chkEvidenceBank.wrapper);
        sectionsGrid.appendChild(chkWorksCited.wrapper);
        sectionsGrid.appendChild(chkOpenQuestions.wrapper);

        sectionsGroup.appendChild(sectionsGrid);
        controls.appendChild(sectionsGroup);
        reportPanel.appendChild(controls);

        // Custom focus input
        const focusGroup = document.createElement("div");
        focusGroup.className = "report-control-group";
        const focusLabel = document.createElement("label");
        focusLabel.className = "report-control-label";
        focusLabel.textContent = "Custom Focus / Angle (Optional)";
        focusGroup.appendChild(focusLabel);

        const focusInput = document.createElement("input");
        focusInput.type = "text";
        focusInput.className = "report-focus-input";
        focusInput.placeholder = "Cater report to a specific question, angle, or audience…";
        focusGroup.appendChild(focusInput);
        reportPanel.appendChild(focusGroup);

        // Generate Button
        const generateBtn = document.createElement("button");
        generateBtn.type = "button";
        generateBtn.className = "btn-generate-report";
        generateBtn.innerHTML = `<span>Synthesize Custom Report & Evidence Bank</span> <span aria-hidden="true">&rarr;</span>`;
        reportPanel.appendChild(generateBtn);

        // Output Card
        const outputCard = document.createElement("div");
        outputCard.className = "report-output-card hidden";

        const outputActions = document.createElement("div");
        outputActions.className = "report-output-actions";

        const copyBtn = document.createElement("button");
        copyBtn.type = "button";
        copyBtn.className = "btn-report-action btn-copy-report";
        copyBtn.textContent = "Copy Markdown";
        outputActions.appendChild(copyBtn);

        const copyPlainBtn = document.createElement("button");
        copyPlainBtn.type = "button";
        copyPlainBtn.className = "btn-report-action btn-copy-plaintext-report";
        copyPlainBtn.textContent = "Copy Plain Text";
        outputActions.appendChild(copyPlainBtn);

        const downloadBtn = document.createElement("button");
        downloadBtn.type = "button";
        downloadBtn.className = "btn-report-action btn-download-report";
        downloadBtn.textContent = "Download .md Report";
        outputActions.appendChild(downloadBtn);

        const printBtn = document.createElement("button");
        printBtn.type = "button";
        printBtn.className = "btn-report-action btn-print-report";
        printBtn.textContent = "Print / Save PDF";
        printBtn.addEventListener("click", () => {
            window.print();
        });
        outputActions.appendChild(printBtn);

        outputCard.appendChild(outputActions);

        const outputBody = document.createElement("div");
        outputBody.className = "report-content-body";
        outputCard.appendChild(outputBody);

        reportPanel.appendChild(outputCard);

        let lastGeneratedMarkdown = "";
        let activeReportSources = [];

        copyBtn.addEventListener("click", async () => {
            if (!lastGeneratedMarkdown) return;
            try {
                await navigator.clipboard.writeText(lastGeneratedMarkdown);
            } catch (_) {}
            copyBtn.textContent = "Copied Markdown!";
            setTimeout(() => { copyBtn.textContent = "Copy Markdown"; }, 1500);
        });

        copyPlainBtn.addEventListener("click", async () => {
            if (!lastGeneratedMarkdown) return;
            const plain = stripMarkdownToPlainText(lastGeneratedMarkdown);
            try {
                await navigator.clipboard.writeText(plain);
            } catch (_) {}
            copyPlainBtn.textContent = "Copied Plain Text!";
            setTimeout(() => { copyPlainBtn.textContent = "Copy Plain Text"; }, 1500);
        });

        downloadBtn.addEventListener("click", () => {
            if (!lastGeneratedMarkdown) return;
            const filename = `scoopscope-report-${Date.now()}.md`;
            downloadFile(filename, lastGeneratedMarkdown, "text/markdown");
            downloadBtn.textContent = "Downloaded!";
            setTimeout(() => { downloadBtn.textContent = "Download .md Report"; }, 1500);
        });

        citationSelect.addEventListener("change", () => {
            activeCitationStyle = citationSelect.value;
            saveWorkspaceToStorage();
            document.querySelectorAll(".citation-style-select, #citation-style-select").forEach(sel => {
                sel.value = activeCitationStyle;
            });
            if (lastGeneratedMarkdown && activeReportSources.length > 0) {
                lastGeneratedMarkdown = updateReportWorksCited(lastGeneratedMarkdown, activeReportSources, citationSelect.value);
                outputBody.innerHTML = renderMarkdown(lastGeneratedMarkdown);
            }
            renderCustomReport();
        });

        generateBtn.addEventListener("click", async () => {
            const checkedItems = Object.values(selectedQuotes).filter(item => item && item.checked);
            if (checkedItems.length === 0) {
                alert("Please select at least one quote to include in the report.");
                return;
            }

            generateBtn.disabled = true;
            generateBtn.textContent = "Synthesizing Report…";

            const reqBody = {
                inquiry_title: currentConfirmedScopeQuestion || claim.normalized_assertion || claim.original_wording || "Investigation Findings",
                report_vibe: vibeSelect.value,
                citation_style: citationSelect.value,
                include_summary: chkSummary.input.checked,
                include_evidence_bank: chkEvidenceBank.input.checked,
                include_works_cited: chkWorksCited.input.checked,
                include_open_questions: chkOpenQuestions.input.checked,
                custom_focus: focusInput.value.trim() || null,
                selected_passages: checkedItems.map(item => ({
                    passage_id: item.passage.passage_id,
                    exact_passage: item.passage.exact_passage,
                    context_surrounding: item.passage.context_surrounding,
                    source_url: item.passage.source_url,
                    relevance_explanation: item.passage.relevance_explanation || item.passage.relevance_note,
                    publication_date: item.passage.publication_date,
                    updated_date: item.passage.updated_date,
                    retrieval_timestamp: item.passage.retrieval_timestamp,
                    source_title: item.passage.source_title,
                    jurisdiction_tag: item.passage.jurisdiction_tag,
                    jurisdiction_code: item.passage.jurisdiction_code,
                })),
                sources: (data.retrieved_sources || []).map(s => ({
                    url: s.final_url || s.initial_url,
                    domain: s.domain,
                    title: s.title,
                    publication_date: s.publication_date,
                    retrieval_date: s.retrieval_timestamp,
                    status: s.status,
                    jurisdiction_tag: s.jurisdiction_tag,
                    jurisdiction_code: s.jurisdiction_code,
                })),
            };

            try {
                const res = await fetch("/api/report", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(reqBody),
                });
                const repData = await res.json();
                if (!res.ok) {
                    alert(repData.detail || "Report generation failed.");
                    return;
                }
                activeReportSources = reqBody.sources;
                lastGeneratedMarkdown = repData.markdown_content;
                outputBody.innerHTML = renderMarkdown(repData.markdown_content);
                outputCard.classList.remove("hidden");
                outputCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
            } catch (err) {
                alert("Could not connect to report server.");
            } finally {
                generateBtn.disabled = false;
                generateBtn.innerHTML = `<span>Synthesize Custom Report & Evidence Bank</span> <span aria-hidden="true">&rarr;</span>`;
            }
        });

        return reportPanel;
    }

    // --- Render Research Results (Milestone 3B Cornell Notes Layout) ---
    function renderResearchResults(container, data, claim, button, card) {
        container.innerHTML = "";

        const panel = document.createElement("div");
        panel.className = "claim-research-panel";

        // 1. Top Summary Header (Full Width): "How the Evidence Fits Your Inquiry" displaying inquiry_synthesis
        const synthesisCard = document.createElement("div");
        synthesisCard.className = "inquiry-synthesis-card";

        const synthTitle = document.createElement("div");
        synthTitle.className = "synthesis-card-title";
        synthTitle.innerHTML = `<span aria-hidden="true">✦</span> How the Evidence Fits Your Inquiry`;
        synthesisCard.appendChild(synthTitle);

        const synthText = document.createElement("p");
        synthText.className = "inquiry-synthesis-text";
        synthText.textContent = data.inquiry_synthesis || "Retrieved verbatim passages addressing terms in the inquiry. Review the extracted quotes below.";
        synthesisCard.appendChild(synthText);

        panel.appendChild(synthesisCard);

        // 2. Two-Column Cornell Notes Body (.cornell-notes-grid)
        const passages = (data.candidate_passages || []).slice(0, 5);
        if (passages.length === 0) {
            const noPassagesBox = document.createElement("div");
            noPassagesBox.className = "passage-box";
            const noPassagesMsg = document.createElement("p");
            noPassagesMsg.className = "hit-snippet";
            noPassagesMsg.style.margin = "0";
            noPassagesMsg.textContent = "No substantive candidate quotes matching the inquiry were identified in retrieved pages.";
            noPassagesBox.appendChild(noPassagesMsg);
            panel.appendChild(noPassagesBox);
        } else {
            const cornellGrid = document.createElement("div");
            cornellGrid.className = "cornell-notes-grid";

            // Two-column header row
            const headerRow = document.createElement("div");
            headerRow.className = "cornell-notes-header-row";

            const cueHead = document.createElement("div");
            cueHead.className = "cornell-col-header";
            cueHead.textContent = "KEY CUES & SOURCES";

            const quoteHead = document.createElement("div");
            quoteHead.className = "cornell-col-header";
            quoteHead.textContent = "SUPPORTING VERBATIM QUOTES";

            headerRow.appendChild(cueHead);
            headerRow.appendChild(quoteHead);
            cornellGrid.appendChild(headerRow);

            passages.forEach((p, idx) => {
                const bulletIndex = idx + 1;
                const quoteKey = getQuoteKey(claim.id, p);

                let domainDisplay = p.source_url;
                try {
                    const parsed = new URL(p.source_url);
                    domainDisplay = parsed.hostname.replace(/^www\./, "");
                } catch (_) {}

                const pairRow = document.createElement("div");
                pairRow.className = "cornell-pair-row";

                // --- Left Column: Cue Card ---
                const cueCell = document.createElement("div");
                cueCell.className = "cornell-cue-cell";

                const cueCard = document.createElement("div");
                cueCard.className = "cornell-cue-card";

                const cueTop = document.createElement("div");
                cueTop.className = "cue-card-top";

                const cueBadge = document.createElement("span");
                cueBadge.className = "cue-index-badge";
                cueBadge.textContent = `[${bulletIndex}]`;
                cueTop.appendChild(cueBadge);

                const cueLabel = document.createElement("span");
                cueLabel.className = "cue-label";
                cueLabel.textContent = "How This Fits";
                cueTop.appendChild(cueLabel);
                cueCard.appendChild(cueTop);

                const cueFit = document.createElement("div");
                cueFit.className = "cue-fit-text";
                cueFit.textContent = p.relevance_explanation || p.relevance_note || "Directly relevant context quote.";
                cueCard.appendChild(cueFit);

                const cueMeta = document.createElement("div");
                cueMeta.className = "cue-source-meta";

                const cueDomain = document.createElement("a");
                cueDomain.className = "cue-domain-badge";
                cueDomain.textContent = domainDisplay;
                if (isSafeHttpUrl(p.source_url)) {
                    cueDomain.href = p.source_url;
                    cueDomain.target = "_blank";
                    cueDomain.rel = "noopener noreferrer";
                }
                cueMeta.appendChild(cueDomain);

                const cueDate = document.createElement("span");
                cueDate.className = "cue-date-badge";
                if (p.publication_date) {
                    let dText = `Published: ${p.publication_date}`;
                    if (p.updated_date && p.updated_date !== p.publication_date) {
                        dText += ` (Updated: ${p.updated_date})`;
                    }
                    cueDate.textContent = dText;
                } else {
                    cueDate.textContent = "Publication date: Unknown";
                }
                cueMeta.appendChild(cueDate);

                // Milestone 4C: Deterministic Official Jurisdiction Badge
                let jurisTag = p.jurisdiction_badge || p.jurisdiction_tag || (data.retrieved_sources && (data.retrieved_sources.find(s => s.source_id === p.source_id || s.initial_url === p.source_url || s.final_url === p.source_url) || {}).jurisdiction_tag);
                let jurisCode = p.jurisdiction_code || (data.retrieved_sources && (data.retrieved_sources.find(s => s.source_id === p.source_id || s.initial_url === p.source_url || s.final_url === p.source_url) || {}).jurisdiction_code);
                if (jurisTag === "LA Local City Official" && !jurisCode) {
                    jurisCode = "la_local_city";
                }

                if (jurisTag) {
                    const cueJuris = document.createElement("span");
                    cueJuris.className = `jurisdiction-badge ${jurisCode ? "jurisdiction-" + jurisCode : ""}`;
                    cueJuris.textContent = jurisTag;
                    cueMeta.appendChild(cueJuris);
                }

                cueCard.appendChild(cueMeta);
                cueCell.appendChild(cueCard);
                pairRow.appendChild(cueCell);

                // --- Right Column: Quote Bullet ---
                const quoteCell = document.createElement("div");
                quoteCell.className = "cornell-quote-cell";

                const quoteBullet = document.createElement("div");
                quoteBullet.className = "cornell-quote-bullet";

                const bulletHeader = document.createElement("div");
                bulletHeader.className = "quote-bullet-header";

                const titleWrap = document.createElement("div");
                titleWrap.className = "quote-bullet-title-wrap";

                const quoteBadge = document.createElement("span");
                quoteBadge.className = "quote-index-badge";
                quoteBadge.textContent = `[${bulletIndex}]`;
                titleWrap.appendChild(quoteBadge);

                const inlineDomain = document.createElement("span");
                inlineDomain.className = "quote-source-domain-inline";
                inlineDomain.textContent = domainDisplay;
                titleWrap.appendChild(inlineDomain);

                bulletHeader.appendChild(titleWrap);

                // "☑ Include in Report" Checkbox
                const includeLabel = document.createElement("label");
                includeLabel.className = "quote-include-label";

                const quoteCheckbox = document.createElement("input");
                quoteCheckbox.type = "checkbox";
                quoteCheckbox.className = "quote-select-checkbox";
                const isChecked = selectedQuotes[quoteKey] ? selectedQuotes[quoteKey].checked : true;
                quoteCheckbox.checked = isChecked;

                if (!selectedQuotes[quoteKey]) {
                    selectedQuotes[quoteKey] = {
                        checked: true,
                        passage: p,
                        claimId: claim.id,
                    };
                }

                quoteCheckbox.addEventListener("change", () => {
                    toggleQuoteSelection(quoteKey, quoteCheckbox.checked);
                });

                includeLabel.appendChild(quoteCheckbox);
                includeLabel.appendChild(document.createTextNode("Include in Report"));
                bulletHeader.appendChild(includeLabel);

                quoteBullet.appendChild(bulletHeader);

                // Deep fragment URL
                const deepUrl = buildTextFragmentUrl(p.source_url, p.exact_passage);

                // Verbatim quote element (clickable deep link)
                const quoteText = document.createElement("a");
                quoteText.className = "focused-quote-text";
                quoteText.textContent = `"${p.exact_passage}"`;
                if (isSafeHttpUrl(deepUrl)) {
                    quoteText.href = deepUrl;
                    quoteText.target = "_blank";
                    quoteText.rel = "noopener noreferrer";
                    quoteText.title = "Click to open source page and scroll to highlighted text";
                }
                quoteBullet.appendChild(quoteText);

                // Actions row (More button + Find exact line link)
                const actionsRow = document.createElement("div");
                actionsRow.className = "quote-actions-row";

                let moreBtn = null;
                let contextContainer = null;
                const hasExtraContext = p.context_surrounding && p.context_surrounding.trim() !== p.exact_passage.trim();

                if (hasExtraContext) {
                    moreBtn = document.createElement("button");
                    moreBtn.type = "button";
                    moreBtn.className = "btn-more-toggle";
                    moreBtn.textContent = "More ▾";

                    contextContainer = document.createElement("div");
                    contextContainer.className = "full-context-container hidden";
                    contextContainer.textContent = p.context_surrounding;

                    moreBtn.addEventListener("click", () => {
                        const isHidden = contextContainer.classList.contains("hidden");
                        contextContainer.classList.toggle("hidden", !isHidden);
                        moreBtn.textContent = isHidden ? "Less ▴" : "More ▾";
                    });

                    actionsRow.appendChild(moreBtn);
                } else {
                    const spacer = document.createElement("span");
                    actionsRow.appendChild(spacer);
                }

                const findExactLink = document.createElement("a");
                findExactLink.className = "link-find-exact";
                findExactLink.href = isSafeHttpUrl(deepUrl) ? deepUrl : (isSafeHttpUrl(p.source_url) ? p.source_url : "#");
                findExactLink.target = "_blank";
                findExactLink.rel = "noopener noreferrer";
                findExactLink.innerHTML = `Find exact line on website <span aria-hidden="true">&nearr;</span>`;
                actionsRow.appendChild(findExactLink);

                quoteBullet.appendChild(actionsRow);

                if (contextContainer) {
                    quoteBullet.appendChild(contextContainer);
                }

                quoteCell.appendChild(quoteBullet);
                pairRow.appendChild(quoteCell);

                cornellGrid.appendChild(pairRow);
            });

            panel.appendChild(cornellGrid);
        }

        // Report & Evidence Bank Studio Panel (only fallback inline if #custom-report-section is not in the page)
        if (!document.getElementById("custom-report-section")) {
            const reportBuilderPanel = renderReportBuilderPanel(claim, data);
            panel.appendChild(reportBuilderPanel);
        }


        // 3. Actionable Explore Further
        const nextQueries = data.suggested_next_queries || [];
        if (nextQueries.length > 0) {
            const exploreCard = document.createElement("div");
            exploreCard.className = "explore-further-card";

            const exploreTitle = document.createElement("div");
            exploreTitle.className = "explore-title";
            exploreTitle.innerHTML = `<span aria-hidden="true">🔍</span> Explore Further`;
            exploreCard.appendChild(exploreTitle);

            const queriesList = document.createElement("div");
            queriesList.className = "explore-queries-list";

            nextQueries.forEach((q) => {
                const itemRow = document.createElement("div");
                itemRow.className = "explore-item-row";

                const chipBtn = document.createElement("button");
                chipBtn.type = "button";
                chipBtn.className = "explore-query-chip btn-explore-query";
                chipBtn.title = "Click to immediately research this query in-place";

                const qSpan = document.createElement("span");
                qSpan.textContent = q;
                chipBtn.appendChild(qSpan);

                const iconSpan = document.createElement("span");
                iconSpan.className = "explore-query-icon";
                iconSpan.innerHTML = "&rarr;";
                chipBtn.appendChild(iconSpan);

                chipBtn.addEventListener("click", () => {
                    if (scopeQuestionInput) {
                        scopeQuestionInput.value = q;
                    }
                    currentConfirmedScopeQuestion = q;
                    scopeQuestionManuallyEdited = true;
                    updateStickyInquiryBar(q);
                    if (card) {
                        card.scrollIntoView({ behavior: "smooth", block: "start" });
                    }
                    if (claim && button && card) {
                        executeResearch(claim, button, card, q);
                    }
                });
                itemRow.appendChild(chipBtn);

                const newInqBtn = document.createElement("button");
                newInqBtn.type = "button";
                newInqBtn.className = "btn-new-inquiry";
                newInqBtn.title = "Load this query into statement input to start fresh inquiry";
                newInqBtn.innerHTML = `New Inquiry <span aria-hidden="true">&nearr;</span>`;

                newInqBtn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    if (inputText) {
                        inputText.value = q;
                        inputText.dispatchEvent(new Event("input", { bubbles: true }));
                        inputText.scrollIntoView({ behavior: "smooth", block: "center" });
                        inputText.focus();
                    }
                });
                itemRow.appendChild(newInqBtn);

                queriesList.appendChild(itemRow);
            });

            exploreCard.appendChild(queriesList);
            panel.appendChild(exploreCard);
        }

        // 4. Collapsed Technical Audit Drawer
        const auditDrawer = document.createElement("details");
        auditDrawer.className = "technical-audit-drawer";

        const retrievedCount = (data.retrieved_sources || []).filter(s => s.status === "retrieved").length;
        const totalSources = (data.retrieved_sources || []).length;
        const hitsCount = (data.search_hits || []).length;

        const auditSummary = document.createElement("summary");
        auditSummary.className = "audit-summary-header";
        auditSummary.innerHTML = `<span>Technical Audit & Raw Search Data (${hitsCount} search hits, ${retrievedCount}/${totalSources} pages fetched, ${data.completed_in_seconds}s)</span> <span>▾</span>`;
        auditDrawer.appendChild(auditSummary);

        const auditContent = document.createElement("div");
        auditContent.className = "audit-drawer-content";

        // Summary Bar & Queries
        const auditStatus = document.createElement("div");
        auditStatus.style.fontWeight = "600";
        auditStatus.textContent = data.status_message;
        auditContent.appendChild(auditStatus);

        if (data.search_failure_message) {
            const failBanner = document.createElement("div");
            failBanner.className = "notice-banner";
            failBanner.style.borderColor = "var(--error-border)";
            failBanner.style.background = "var(--error-bg)";
            failBanner.style.color = "var(--error-text)";
            failBanner.textContent = `Search provider notice: ${data.search_failure_message}`;
            auditContent.appendChild(failBanner);
        }

        if (data.queries_used && data.queries_used.length > 0) {
            const queryRow = document.createElement("div");
            queryRow.style.display = "flex";
            queryRow.style.flexWrap = "wrap";
            queryRow.style.gap = "0.4rem";
            queryRow.style.alignItems = "center";

            const qLabel = document.createElement("span");
            qLabel.textContent = "Executed Search Queries:";
            queryRow.appendChild(qLabel);

            data.queries_used.forEach((q) => {
                const chip = document.createElement("span");
                chip.className = "query-chip";
                chip.textContent = `"${q.query_text}" (${q.query_intent})`;
                queryRow.appendChild(chip);
            });
            auditContent.appendChild(queryRow);
        }

        // Search Hits (Unexamined Snippets)
        const hitsSection = document.createElement("div");
        hitsSection.className = "search-hits-group";
        const hitsLabel = document.createElement("div");
        hitsLabel.className = "section-label";
        hitsLabel.textContent = "Search Engine Results (Unexamined Previews — Not Full Evidence)";
        hitsSection.appendChild(hitsLabel);

        const snippetNotice = document.createElement("div");
        snippetNotice.className = "notice-banner notice-snippet-only";
        snippetNotice.textContent = "Search snippets are unexamined candidate previews and NEVER count as verified evidence.";
        hitsSection.appendChild(snippetNotice);

        const hitsList = document.createElement("div");
        hitsList.className = "hits-list";
        hitsList.style.marginTop = "0.5rem";

        if (!data.search_hits || data.search_hits.length === 0) {
            const noHits = document.createElement("p");
            noHits.className = "hit-snippet";
            noHits.textContent = data.search_failure_message ? `Search unavailable: ${data.search_failure_message}` : "No search hits returned by search provider.";
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
        auditContent.appendChild(hitsSection);

        // Sources Technical Details (IPs, Bytes, Raw Decoded Inspector)
        const sourcesSection = document.createElement("div");
        sourcesSection.className = "retrieved-sources-group";
        const sourcesLabel = document.createElement("div");
        sourcesLabel.className = "section-label";
        sourcesLabel.textContent = "Source Retrieval & Network Audit";
        sourcesSection.appendChild(sourcesLabel);

        const sourcesList = document.createElement("div");
        sourcesList.className = "sources-list";
        sourcesList.style.marginTop = "0.5rem";

        (data.retrieved_sources || []).forEach((src) => {
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
            header.appendChild(link);

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
            header.appendChild(badge);
            card.appendChild(header);

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

            if (src.error_message) {
                const errP = document.createElement("div");
                errP.className = "source-error-msg";
                errP.textContent = src.error_message;
                card.appendChild(errP);
            }

            // Raw page text inspector
            if (src.extracted_text) {
                const rawDetails = document.createElement("details");
                rawDetails.style.marginTop = "0.5rem";
                const rawSummary = document.createElement("summary");
                rawSummary.className = "text-viewer-toggle";
                rawSummary.textContent = "Inspect full extracted page text";
                rawSummary.style.cursor = "pointer";
                rawDetails.appendChild(rawSummary);

                const rawBox = document.createElement("div");
                rawBox.className = "raw-page-text-box";
                rawBox.style.marginTop = "0.5rem";
                rawBox.textContent = src.extracted_text;
                rawDetails.appendChild(rawBox);

                card.appendChild(rawDetails);
            }

            sourcesList.appendChild(card);
        });

        sourcesSection.appendChild(sourcesList);
        auditContent.appendChild(sourcesSection);

        auditDrawer.appendChild(auditContent);
        panel.appendChild(auditDrawer);

        container.appendChild(panel);
    }

    // --- Milestone 3B Multi-Tab Workspace for Claim Research Runs ---
    function renderClaimResearchTabsWorkspace(container, claim, button, card) {
        container.innerHTML = "";
        const runs = claimResearchTabs[claim.id] || [];
        if (runs.length === 0) return;

        let activeTabId = activeClaimTabId[claim.id];
        if (!activeTabId || !runs.some(r => r.id === activeTabId)) {
            activeTabId = runs[runs.length - 1].id;
            activeClaimTabId[claim.id] = activeTabId;
        }

        const activeRun = runs.find(r => r.id === activeTabId) || runs[runs.length - 1];

        // Research tabs bar
        const tabsBar = document.createElement("div");
        tabsBar.className = "research-tabs-bar";

        runs.forEach((run, rIdx) => {
            const tabBtn = document.createElement("button");
            tabBtn.type = "button";
            tabBtn.className = `research-tab-btn ${run.id === activeRun.id ? "active" : ""}`;
            tabBtn.textContent = run.title || `Tab ${rIdx + 1}`;
            tabBtn.addEventListener("click", () => {
                activeClaimTabId[claim.id] = run.id;
                renderClaimResearchTabsWorkspace(container, claim, button, card);
            });
            tabsBar.appendChild(tabBtn);
        });

        container.appendChild(tabsBar);

        // Content area for the active run
        const contentContainer = document.createElement("div");
        contentContainer.className = "research-tab-content";
        container.appendChild(contentContainer);

        renderResearchResults(contentContainer, activeRun.data, claim, button, card);
        updateAllEvidenceCounters();
    }

    // --- Milestone 3B & 4E Top-Level Session & Workspace Persistence Management ---
    function updateActiveSessionState() {
        if (!activeSessionId) return;
        const sess = sessionInquiries.find(s => s.id === activeSessionId);
        if (!sess) return;
        const claimInput = document.getElementById("claim-input");
        const effectiveText = (inputText && inputText.value !== undefined) ? inputText.value : ((claimInput && claimInput.value !== undefined) ? claimInput.value : "");
        sess.inputText = effectiveText;
        if (inputText) inputText.value = effectiveText;
        if (claimInput) claimInput.value = effectiveText;
        sess.sourceUrl = sourceUrl ? sourceUrl.value : null;
        sess.scopeQuestion = currentConfirmedScopeQuestion;
        sess.scopeEdited = scopeQuestionManuallyEdited;
        sess.claims = currentClaims;
        sess.claimResearchTabs = claimResearchTabs;
        sess.activeClaimTabId = activeClaimTabId;
        sess.selectedQuotes = selectedQuotes;
        sess.clarificationExchanges = clarificationExchanges;
        sess.isClarifying = false;
        sess.isResearching = false;
    }

    function saveCurrentSessionSnapshot() {
        updateActiveSessionState();
    }

    function restoreSessionSnapshot(target) {
        if (!target) return;
        const claimInput = document.getElementById("claim-input");
        const effectiveText = target.inputText || "";
        if (inputText) inputText.value = effectiveText;
        if (claimInput) claimInput.value = effectiveText;
        if (charCount) charCount.textContent = effectiveText.length.toLocaleString();
        if (sourceUrl) sourceUrl.value = target.sourceUrl || "";
        currentSourceUrl = target.sourceUrl || null;
        currentConfirmedScopeQuestion = target.scopeQuestion || "";
        scopeQuestionManuallyEdited = Boolean(target.scopeEdited);
        currentClaims = target.claims || [];
        claimResearchTabs = target.claimResearchTabs || {};
        activeClaimTabId = target.activeClaimTabId || {};
        selectedQuotes = target.selectedQuotes || {};
        clarificationExchanges = target.clarificationExchanges || [];
    }

    function createEmptySession(title) {
        const sessCount = sessionInquiries.length + 1;
        const sessId = "sess_" + Date.now() + "_" + Math.random().toString(36).slice(2, 6);
        return {
            id: sessId,
            title: title || `Session ${sessCount}`,
            inputText: "",
            sourceUrl: null,
            scopeQuestion: "",
            scopeEdited: false,
            claims: [],
            claimResearchTabs: {},
            activeClaimTabId: {},
            selectedQuotes: {},
            data: null,
            isClarification: false,
            clarificationExchanges: [],
            isClarifying: false,
            isResearching: false,
        };
    }

    function saveWorkspaceToStorage() {
        updateActiveSessionState();
        const payload = {
            version: 1,
            activeSessionId: activeSessionId,
            citationStyle: activeCitationStyle || "standard",
            sessions: sessionInquiries.map((s) => {
                let quotesArray;
                if (Array.isArray(s.selectedQuotes)) {
                    quotesArray = s.selectedQuotes;
                } else if (s.selectedQuotes instanceof Map) {
                    quotesArray = Array.from(s.selectedQuotes.entries());
                } else if (s.selectedQuotes && typeof s.selectedQuotes === "object") {
                    quotesArray = Object.entries(s.selectedQuotes);
                } else {
                    quotesArray = [];
                }
                return {
                    id: s.id,
                    title: s.title,
                    inputText: s.inputText || "",
                    sourceUrl: s.sourceUrl || null,
                    scopeQuestion: s.scopeQuestion || "",
                    scopeEdited: Boolean(s.scopeEdited),
                    claims: s.claims || [],
                    claimResearchTabs: s.claimResearchTabs || {},
                    activeClaimTabId: s.activeClaimTabId || {},
                    selectedQuotes: quotesArray, // Decision 015: Map <-> JSON array
                    data: s.data || null,
                    isClarification: Boolean(s.isClarification),
                    clarificationExchanges: s.clarificationExchanges || [],
                    isClarifying: false,
                    isResearching: false,
                };
            }),
        };
        try {
            localStorage.setItem(WORKSPACE_STORAGE_KEY, JSON.stringify(payload));
        } catch (err) {
            console.warn("Could not save workspace to localStorage:", err);
        }
    }

    function loadWorkspaceFromStorage() {
        let raw = null;
        try {
            raw = localStorage.getItem(WORKSPACE_STORAGE_KEY);
        } catch (err) {
            console.warn("localStorage read failed:", err);
        }

        if (!raw) {
            if (sessionInquiries.length === 0) {
                const initial = createEmptySession("Session 1");
                sessionInquiries = [initial];
                activeSessionId = initial.id;
                renderSessionTabs();
            }
            return false;
        }

        let parsed = null;
        try {
            parsed = JSON.parse(raw);
        } catch (err) {
            console.warn("Corrupt workspace state in localStorage, resetting to default Session 1:", err);
            const fresh = createEmptySession("Session 1");
            sessionInquiries = [fresh];
            activeSessionId = fresh.id;
            activeCitationStyle = "standard";
            renderSessionTabs();
            saveWorkspaceToStorage();
            return false;
        }

        if (!parsed || typeof parsed !== "object" || !Array.isArray(parsed.sessions) || parsed.sessions.length === 0) {
            const fresh = createEmptySession("Session 1");
            sessionInquiries = [fresh];
            activeSessionId = fresh.id;
            activeCitationStyle = "standard";
            renderSessionTabs();
            saveWorkspaceToStorage();
            return false;
        }

        activeCitationStyle = parsed.citationStyle || "standard";
        sessionInquiries = parsed.sessions.map((rawSess, idx) => {
            const sessId = rawSess.id || ("sess_" + Date.now() + "_" + idx);
            let quotes = {};
            if (Array.isArray(rawSess.selectedQuotes)) {
                quotes = Object.fromEntries(rawSess.selectedQuotes);
            } else if (rawSess.selectedQuotes && typeof rawSess.selectedQuotes === "object") {
                quotes = rawSess.selectedQuotes;
            }
            return {
                id: sessId,
                title: rawSess.title || ("Session " + (idx + 1)),
                inputText: rawSess.inputText || "",
                sourceUrl: rawSess.sourceUrl || null,
                scopeQuestion: rawSess.scopeQuestion || "",
                scopeEdited: Boolean(rawSess.scopeEdited),
                claims: Array.isArray(rawSess.claims) ? rawSess.claims : [],
                claimResearchTabs: rawSess.claimResearchTabs || {},
                activeClaimTabId: rawSess.activeClaimTabId || {},
                selectedQuotes: quotes,
                data: rawSess.data || null,
                isClarification: Boolean(rawSess.isClarification),
                clarificationExchanges: Array.isArray(rawSess.clarificationExchanges) ? rawSess.clarificationExchanges : [],
                // Decision 015: Force transient loading spinner reset
                isClarifying: false,
                isResearching: false,
            };
        });

        const targetId = parsed.activeSessionId && sessionInquiries.some((s) => s.id === parsed.activeSessionId)
            ? parsed.activeSessionId
            : sessionInquiries[0].id;

        activeSessionId = targetId;
        switchSession(activeSessionId);
        renderSessionTabs();

        setLoading(false);
        setClarificationLoading(false);
        hideLoadingProgress();

        document.querySelectorAll("#citation-style-select, .citation-style-select").forEach(sel => {
            sel.value = activeCitationStyle;
        });

        const activeSess = sessionInquiries.find(s => s.id === activeSessionId) || sessionInquiries[0];
        if (!activeSess || !activeSess.data) {
            if (confirmedScopeCard) confirmedScopeCard.classList.add("hidden");
            const scopeBanner = document.getElementById("confirmed-scope-banner");
            if (scopeBanner) scopeBanner.classList.add("hidden");
            const claimsSec = document.getElementById("claims-section");
            if (claimsSec) claimsSec.classList.add("hidden");
            const customReportSec = document.getElementById("custom-report-section");
            if (customReportSec) customReportSec.classList.add("hidden");
            const reportStudio = document.getElementById("report-studio-section");
            if (reportStudio) reportStudio.classList.add("hidden");
        } else {
            const hasCheckedQuotes = Object.values(selectedQuotes).some(q => q && q.checked);
            if (hasCheckedQuotes) {
                renderCustomReport();
            } else {
                const customReportSec = document.getElementById("custom-report-section");
                if (customReportSec) customReportSec.classList.add("hidden");
                const reportStudio = document.getElementById("report-studio-section");
                if (reportStudio) reportStudio.classList.add("hidden");
            }
        }

        return true;
    }

    function clearWorkspace() {
        try {
            localStorage.removeItem(WORKSPACE_STORAGE_KEY);
        } catch (err) {
            console.warn("Could not remove item from localStorage:", err);
        }

        activeCitationStyle = "standard";
        const fresh = createEmptySession("Session 1");
        sessionInquiries = [fresh];
        activeSessionId = fresh.id;

        inputText.value = "";
        charCount.textContent = "0";
        if (sourceUrl) sourceUrl.value = "";
        const claimInput = document.getElementById("claim-input");
        if (claimInput) claimInput.value = "";
        currentSubmissionId = null;
        currentSourceUrl = null;
        currentClarificationData = null;
        clarificationExchanges = [];
        currentConfirmedScopeQuestion = "";
        scopeQuestionManuallyEdited = false;
        currentClaims = [];
        claimResearchTabs = {};
        activeClaimTabId = {};
        selectedQuotes = {};
        activeResearchClaimId = null;

        setLoading(false);
        setClarificationLoading(false);
        hideLoadingProgress();
        hideError();

        resultsSection.classList.add("hidden");
        if (clarificationSection) clarificationSection.classList.add("hidden");
        if (stickyInquiryBar) stickyInquiryBar.classList.add("hidden");
        if (confirmedScopeCard) confirmedScopeCard.classList.add("hidden");
        const scopeBanner = document.getElementById("confirmed-scope-banner");
        if (scopeBanner) scopeBanner.classList.add("hidden");
        const claimsSec = document.getElementById("claims-section");
        if (claimsSec) claimsSec.classList.add("hidden");
        if (claimsList) claimsList.innerHTML = "";
        if (submittedText) submittedText.textContent = "";
        if (submittedUrlRow) submittedUrlRow.classList.add("hidden");
        const formEl = document.getElementById("extraction-form") || document.getElementById("input-section");
        if (formEl) formEl.classList.remove("compact-collapsed");

        const customReportSec = document.getElementById("custom-report-section");
        if (customReportSec) customReportSec.classList.add("hidden");
        const reportStudio = document.getElementById("report-studio-section");
        if (reportStudio) reportStudio.classList.add("hidden");
        document.querySelectorAll(".report-output-card, .report-builder-panel").forEach(el => el.classList.add("hidden"));
        primaryGeneratedMarkdown = "";
        primaryReportSources = [];
        const staleBanner = document.getElementById("claims-outdated-banner");
        if (staleBanner) staleBanner.remove();

        document.querySelectorAll("#citation-style-select, .citation-style-select").forEach(sel => {
            sel.value = "standard";
        });

        renderSessionTabs();
        saveWorkspaceToStorage();
        inputText.focus();
    }

    function closeSessionTab(sessionId) {
        const idx = sessionInquiries.findIndex((s) => s.id === sessionId);
        if (idx === -1) return;

        sessionInquiries.splice(idx, 1);
        if (sessionInquiries.length === 0) {
            const fresh = createEmptySession("Session 1");
            sessionInquiries.push(fresh);
            activeSessionId = fresh.id;
            switchSession(fresh.id);
        } else if (activeSessionId === sessionId) {
            const newIdx = Math.min(idx, sessionInquiries.length - 1);
            activeSessionId = sessionInquiries[newIdx].id;
            switchSession(activeSessionId);
        }
        renderSessionTabs();
        saveWorkspaceToStorage();
    }

    function toggleQuoteSelection(quoteKey, explicitValue) {
        if (!selectedQuotes[quoteKey]) return;
        selectedQuotes[quoteKey].checked = explicitValue !== undefined ? Boolean(explicitValue) : !selectedQuotes[quoteKey].checked;
        updateAllEvidenceCounters();
        updateActiveSessionState();
        saveWorkspaceToStorage();
    }

    function renderSessionTabs() {
        if (!sessionTabsBar || !sessionTabsList) return;
        if (sessionInquiries.length === 0) {
            sessionTabsBar.classList.add("hidden");
            return;
        }
        sessionTabsBar.classList.remove("hidden");
        sessionTabsList.innerHTML = "";

        sessionInquiries.forEach((sess) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = `session-tab-btn ${sess.id === activeSessionId ? "active" : ""}`;
            btn.title = sess.inputText || sess.title;

            const titleSpan = document.createElement("span");
            titleSpan.className = "session-tab-title";
            titleSpan.textContent = sess.title;
            btn.appendChild(titleSpan);

            const closeSpan = document.createElement("span");
            closeSpan.className = "btn-close-tab";
            closeSpan.innerHTML = "&times;";
            closeSpan.title = "Close tab";
            closeSpan.setAttribute("role", "button");
            closeSpan.setAttribute("aria-label", "Close tab");
            closeSpan.addEventListener("click", (e) => {
                e.stopPropagation();
                closeSessionTab(sess.id);
            });
            btn.appendChild(closeSpan);

            btn.addEventListener("click", () => {
                switchSession(sess.id);
            });
            sessionTabsList.appendChild(btn);
        });
    }

    function switchSession(sessId) {
        updateActiveSessionState();
        const target = sessionInquiries.find(s => s.id === sessId);
        if (!target) return;

        activeSessionId = sessId;
        restoreSessionSnapshot(target);

        renderSessionTabs();
        updateStickyInquiryBar(currentConfirmedScopeQuestion || target.inputText);

        const staleBanner = document.getElementById("claims-outdated-banner");
        if (staleBanner) staleBanner.remove();

        const formEl = document.getElementById("extraction-form") || document.getElementById("input-section");
        const confirmedScope = document.getElementById("confirmed-scope-card");
        const scopeBanner = document.getElementById("confirmed-scope-banner");
        const claimsSec = document.getElementById("claims-section");

        if (target.isClarification && target.data) {
            resultsSection.classList.add("hidden");
            if (confirmedScope) confirmedScope.classList.add("hidden");
            if (scopeBanner) scopeBanner.classList.add("hidden");
            if (claimsSec) claimsSec.classList.add("hidden");
            if (formEl) formEl.classList.remove("compact-collapsed");
            renderClarification(target.data, currentSubmissionSeq);
        } else if (target.data) {
            if (clarificationSection) clarificationSection.classList.add("hidden");
            renderResults(target.data, currentSubmissionSeq);
            let hasResearch = false;
            (target.claims || []).forEach(claim => {
                if (claimResearchTabs[claim.id] && claimResearchTabs[claim.id].length > 0) {
                    hasResearch = true;
                    const card = document.getElementById(`claim-card-${claim.id}`);
                    if (card) {
                        const container = card.querySelector(`#research-container-${claim.id}`) || card.querySelector(`.claim-research-container`);
                        const researchBtn = card.querySelector(`#btn-research-${claim.id}`) || card.querySelector(`.btn-research`);
                        if (container && researchBtn) {
                            container.classList.remove("hidden");
                            renderClaimResearchTabsWorkspace(container, claim, researchBtn, card);
                        }
                    }
                }
            });
            if (formEl) {
                if (hasResearch) formEl.classList.add("compact-collapsed");
                else formEl.classList.remove("compact-collapsed");
            }
        } else {
            resultsSection.classList.add("hidden");
            if (clarificationSection) clarificationSection.classList.add("hidden");
            if (confirmedScope) confirmedScope.classList.add("hidden");
            if (scopeBanner) scopeBanner.classList.add("hidden");
            if (claimsSec) claimsSec.classList.add("hidden");
            if (claimsList) claimsList.innerHTML = "";
            if (submittedText) submittedText.textContent = "";
            if (submittedUrlRow) submittedUrlRow.classList.add("hidden");
            if (stickyInquiryBar) stickyInquiryBar.classList.add("hidden");
            if (formEl) formEl.classList.remove("compact-collapsed");
        }

        document.querySelectorAll("#citation-style-select, .citation-style-select").forEach(sel => {
            sel.value = activeCitationStyle;
        });

        updateAllEvidenceCounters();
    }

    function startNewSession() {
        updateActiveSessionState();
        const nextNum = sessionInquiries.length + 1;
        const newSess = createEmptySession(`Session ${nextNum}`);
        sessionInquiries.push(newSess);
        activeSessionId = newSess.id;
        inputText.value = "";
        charCount.textContent = "0";
        if (sourceUrl) sourceUrl.value = "";
        const claimInput = document.getElementById("claim-input");
        if (claimInput) claimInput.value = "";
        currentSourceUrl = null;
        currentConfirmedScopeQuestion = "";
        scopeQuestionManuallyEdited = false;
        currentClaims = [];
        claimResearchTabs = {};
        activeClaimTabId = {};
        selectedQuotes = {};
        clarificationExchanges = [];
        hideError();
        resultsSection.classList.add("hidden");
        if (clarificationSection) clarificationSection.classList.add("hidden");
        if (stickyInquiryBar) stickyInquiryBar.classList.add("hidden");
        const confirmedScope = document.getElementById("confirmed-scope-card");
        if (confirmedScope) confirmedScope.classList.add("hidden");
        const scopeBanner = document.getElementById("confirmed-scope-banner");
        if (scopeBanner) scopeBanner.classList.add("hidden");
        const claimsSec = document.getElementById("claims-section");
        if (claimsSec) claimsSec.classList.add("hidden");
        if (claimsList) claimsList.innerHTML = "";
        if (submittedText) submittedText.textContent = "";
        if (submittedUrlRow) submittedUrlRow.classList.add("hidden");
        const formEl = document.getElementById("extraction-form") || document.getElementById("input-section");
        if (formEl) formEl.classList.remove("compact-collapsed");
        const customReportSec = document.getElementById("custom-report-section");
        if (customReportSec) customReportSec.classList.add("hidden");
        const reportStudio = document.getElementById("report-studio-section");
        if (reportStudio) reportStudio.classList.add("hidden");
        document.querySelectorAll(".report-output-card, .report-builder-panel").forEach(el => el.classList.add("hidden"));
        const staleBanner = document.getElementById("claims-outdated-banner");
        if (staleBanner) staleBanner.remove();
        renderSessionTabs();
        saveWorkspaceToStorage();
        inputText.focus();
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
        showLoadingProgress("Analyzing your statement and checking scope…");

        // Maintain top-level session list
        let originSession = sessionInquiries.find(s => s.id === activeSessionId);
        if (!originSession) {
            const sessId = "sess_" + Date.now() + "_" + Math.random().toString(36).slice(2, 6);
            activeSessionId = sessId;
            let shortTitle = text.length > 28 ? text.slice(0, 26) + "…" : text;
            originSession = {
                id: sessId,
                title: `Inquiry ${sessionInquiries.length + 1}: ${shortTitle}`,
                inputText: text,
                sourceUrl: sourceUrl ? (sourceUrl.value.trim() || null) : null,
                scopeQuestion: "",
                scopeEdited: false,
                claims: [],
                claimResearchTabs: {},
                activeClaimTabId: {},
                selectedQuotes: {},
                data: null,
                isClarification: false,
                clarificationExchanges: [],
                isClarifying: false,
                isResearching: false,
            };
            sessionInquiries.push(originSession);
            renderSessionTabs();
        } else {
            originSession.inputText = text;
            originSession.sourceUrl = sourceUrl ? (sourceUrl.value.trim() || null) : null;
            if (!originSession.data && (originSession.title.startsWith("Session ") || originSession.title === "Session 1")) {
                let shortTitle = text.length > 28 ? text.slice(0, 26) + "…" : text;
                const idx = sessionInquiries.indexOf(originSession) + 1;
                originSession.title = `Inquiry ${idx}: ${shortTitle}`;
                renderSessionTabs();
            }
        }
        const originSessionId = originSession.id;
        saveWorkspaceToStorage();

        // Clear previous results while new request is in flight to guarantee clean state ownership
        resultsSection.classList.add("hidden");
        if (clarificationSection) {
            clarificationSection.classList.add("hidden");
        }

        const body = {
            text: text,
            source_url: sourceUrl ? (sourceUrl.value.trim() || null) : null,
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
                if (activeSessionId === originSessionId) {
                    showError("Response error", "Server returned an unparseable response.");
                }
                return;
            }

            if (seq !== currentSubmissionSeq) {
                return;
            }

            if (!res.ok) {
                if (activeSessionId === originSessionId) {
                    showError(
                        data.error || `Error ${res.status}`,
                        data.detail || "Something went wrong."
                    );
                }
                return;
            }

            if (data.clarification_needed) {
                originSession.data = data;
                originSession.isClarification = true;
                originSession.clarificationExchanges = clarificationExchanges;
            } else {
                originSession.data = data;
                originSession.isClarification = false;
                originSession.scopeQuestion = data.confirmed_scope_question || data.interpreted_question || (data.claims && data.claims[0] && data.claims[0].normalized_assertion) || text;
                originSession.claims = data.claims || [];
            }
            originSession.isClarifying = false;

            if (activeSessionId === originSessionId) {
                renderSessionTabs();
                if (data.clarification_needed) {
                    renderClarification(data, seq);
                } else {
                    renderResults(data, seq);
                }
                saveWorkspaceToStorage();
            } else {
                // Tab switched in-flight! Do NOT touch active tab's screen
                renderSessionTabs();
                saveWorkspaceToStorage();
            }
        } catch (err) {
            if (seq !== currentSubmissionSeq) return;
            if (activeSessionId === originSessionId) {
                showError("Network error", "Could not reach the server. Is it running?");
            }
        } finally {
            if (activeSessionId === originSessionId && seq === currentSubmissionSeq) {
                setLoading(false);
                hideLoadingProgress();
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

    if (btnNewSession) {
        btnNewSession.addEventListener("click", () => {
            startNewSession();
        });
    }

    if (btnClearWorkspace) {
        btnClearWorkspace.addEventListener("click", () => {
            clearWorkspace();
        });
    }

    // Milestone 4F: Wire controls in #custom-report-section
    const btnToggleReportStudio = document.getElementById("btn-toggle-report-studio");
    const reportStudioBody = document.getElementById("report-studio-collapsible-body");
    if (btnToggleReportStudio && reportStudioBody) {
        btnToggleReportStudio.addEventListener("click", () => {
            const isHidden = reportStudioBody.classList.contains("hidden");
            if (isHidden) {
                reportStudioBody.classList.remove("hidden");
                btnToggleReportStudio.innerHTML = "Hide Options ▴";
                btnToggleReportStudio.setAttribute("aria-expanded", "true");
            } else {
                reportStudioBody.classList.add("hidden");
                btnToggleReportStudio.innerHTML = "Customize &amp; Generate Report ▾";
                btnToggleReportStudio.setAttribute("aria-expanded", "false");
            }
        });
    }

    const customCitationSelect = document.getElementById("citation-style-select");
    if (customCitationSelect) {
        customCitationSelect.addEventListener("change", (e) => {
            activeCitationStyle = e.target.value;
            saveWorkspaceToStorage();
            renderCustomReport();
        });
    }

    const btnCustomSelectAll = document.querySelector("#custom-report-section .btn-select-all-quotes");
    if (btnCustomSelectAll) {
        btnCustomSelectAll.addEventListener("click", () => {
            Object.keys(selectedQuotes).forEach(k => {
                if (selectedQuotes[k]) selectedQuotes[k].checked = true;
            });
            document.querySelectorAll(".quote-select-checkbox").forEach(cb => { cb.checked = true; });
            updateAllEvidenceCounters();
            updateActiveSessionState();
            saveWorkspaceToStorage();
        });
    }

    const btnCustomClearAll = document.querySelector("#custom-report-section .btn-clear-quotes");
    if (btnCustomClearAll) {
        btnCustomClearAll.addEventListener("click", () => {
            Object.keys(selectedQuotes).forEach(k => {
                if (selectedQuotes[k]) selectedQuotes[k].checked = false;
            });
            document.querySelectorAll(".quote-select-checkbox").forEach(cb => { cb.checked = false; });
            updateAllEvidenceCounters();
            updateActiveSessionState();
            saveWorkspaceToStorage();
        });
    }

    const btnCustomGen = document.getElementById("btn-generate-custom-report");
    if (btnCustomGen) {
        btnCustomGen.addEventListener("click", async () => {
            const checkedItems = Object.values(selectedQuotes).filter(item => item && item.checked);
            if (checkedItems.length === 0) {
                alert("Please select at least one quote to include in the report.");
                return;
            }
            const originSessionId = activeSessionId;
            btnCustomGen.disabled = true;
            btnCustomGen.textContent = "Synthesizing Report…";
            try {
                const reqBody = {
                    inquiry_title: currentConfirmedScopeQuestion || "Investigation Findings",
                    report_vibe: (document.getElementById("report-vibe-select") || {}).value || "objective_brief",
                    citation_style: activeCitationStyle || "standard",
                    include_summary: true,
                    include_evidence_bank: true,
                    include_works_cited: true,
                    include_open_questions: true,
                    selected_passages: checkedItems.map(item => ({
                        passage_id: item.passage.passage_id,
                        exact_passage: item.passage.exact_passage,
                        context_surrounding: item.passage.context_surrounding,
                        source_url: item.passage.source_url,
                        relevance_explanation: item.passage.relevance_explanation || item.passage.relevance_note,
                        publication_date: item.passage.publication_date,
                    })),
                    sources: primaryReportSources,
                };
                const res = await fetch("/api/report", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(reqBody),
                });
                if (res.ok) {
                    const repData = await res.json();
                    primaryGeneratedMarkdown = repData.markdown_content;
                }
            } catch (_) {
                // Keep local draft synthesis
            } finally {
                btnCustomGen.disabled = false;
                btnCustomGen.innerHTML = `<span>Synthesize Custom Report &amp; Evidence Bank</span> <span aria-hidden="true">&rarr;</span>`;
                if (activeSessionId === originSessionId) {
                    const outputCard = document.getElementById("custom-report-output-card");
                    const outputBody = outputCard ? outputCard.querySelector(".report-content-body") : null;
                    if (outputCard && outputBody && primaryGeneratedMarkdown) {
                        outputBody.innerHTML = renderMarkdown(primaryGeneratedMarkdown);
                        outputCard.classList.remove("hidden");
                    }
                }
            }
        });
    }

    const customCopyMdBtn = document.querySelector("#custom-report-section .btn-copy-report");
    if (customCopyMdBtn) {
        customCopyMdBtn.addEventListener("click", async () => {
            if (!primaryGeneratedMarkdown) return;
            try { await navigator.clipboard.writeText(primaryGeneratedMarkdown); } catch (_) {}
            customCopyMdBtn.textContent = "Copied Markdown!";
            setTimeout(() => { customCopyMdBtn.textContent = "Copy Markdown"; }, 1500);
        });
    }

    const customCopyPlainBtn = document.querySelector("#custom-report-section .btn-copy-plaintext-report");
    if (customCopyPlainBtn) {
        customCopyPlainBtn.addEventListener("click", async () => {
            if (!primaryGeneratedMarkdown) return;
            const plain = stripMarkdownToPlainText(primaryGeneratedMarkdown);
            try { await navigator.clipboard.writeText(plain); } catch (_) {}
            customCopyPlainBtn.textContent = "Copied Plain Text!";
            setTimeout(() => { customCopyPlainBtn.textContent = "Copy Plain Text"; }, 1500);
        });
    }

    const customDownloadBtn = document.querySelector("#custom-report-section .btn-download-report");
    if (customDownloadBtn) {
        customDownloadBtn.addEventListener("click", () => {
            if (!primaryGeneratedMarkdown) return;
            const filename = `scoopscope-report-${Date.now()}.md`;
            downloadFile(filename, primaryGeneratedMarkdown, "text/markdown");
            customDownloadBtn.textContent = "Downloaded!";
            setTimeout(() => { customDownloadBtn.textContent = "Download .md Report"; }, 1500);
        });
    }

    const customPrintBtn = document.querySelector("#custom-report-section .btn-print-report");
    if (customPrintBtn) {
        customPrintBtn.addEventListener("click", () => { window.print(); });
    }

    // Expose for testing if running in test environment
    if (typeof window !== "undefined") {
        window.__ScoopScope = {
            WORKSPACE_STORAGE_KEY,
            get workspaceState() {
                return {
                    version: 1,
                    activeSessionId,
                    citationStyle: activeCitationStyle,
                    sessions: sessionInquiries,
                };
            },
            get currentSeq() { return currentSubmissionSeq; },
            get activeResearchSeq() { return activeResearchSeq; },
            get activeResearchClaimId() { return activeResearchClaimId; },
            get clarificationExchanges() { return clarificationExchanges; },
            get currentConfirmedScopeQuestion() { return currentConfirmedScopeQuestion; },
            get scopeQuestionManuallyEdited() { return scopeQuestionManuallyEdited; },
            get currentClaims() { return currentClaims; },
            get sessionInquiries() { return sessionInquiries; },
            get activeSessionId() { return activeSessionId; },
            get claimResearchTabs() { return claimResearchTabs; },
            get activeClaimTabId() { return activeClaimTabId; },
            get selectedQuotes() { return selectedQuotes; },
            get activeCitationStyle() { return activeCitationStyle; },
            set activeCitationStyle(val) { activeCitationStyle = val; },
            saveCurrentSessionSnapshot,
            restoreSessionSnapshot,
            renderCustomReport,
            saveWorkspaceToStorage,
            loadWorkspaceFromStorage,
            clearWorkspace,
            createEmptySession,
            switchSessionTab: switchSession,
            closeSessionTab,
            toggleQuoteSelection,
            handleScopeQuestionEdit,
            executeSubmission,
            renderResults,
            renderClarification,
            executeClarificationChoice,
            executeResearch,
            renderResearchResults,
            renderClaimResearchTabsWorkspace,
            renderSessionTabs,
            switchSession,
            startNewSession,
            renderReportBuilderPanel,
            updateAllEvidenceCounters,
            renderMarkdown,
            showError,
            hideError,
            setLoading,
            setClarificationLoading,
            updateStickyInquiryBar,
            buildTextFragmentUrl,
            showLoadingProgress,
            hideLoadingProgress,
            handleInputEdit,
            markSnapshotOutdated,
        };

        window.renderMarkdown = renderMarkdown;
        window.saveWorkspaceToStorage = saveWorkspaceToStorage;
        window.loadWorkspaceFromStorage = loadWorkspaceFromStorage;
        window.clearWorkspace = clearWorkspace;
        window.WORKSPACE_STORAGE_KEY = WORKSPACE_STORAGE_KEY;
    }

    // Initialize workspace from localStorage (Milestone 4E)
    loadWorkspaceFromStorage();
})();
