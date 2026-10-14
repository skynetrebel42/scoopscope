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
    // Monotonically increasing counter to prevent stale responses from
    // overwriting newer submissions.
    let currentSubmissionSeq = 0;

    // --- Character counter ---
    inputText.addEventListener("input", () => {
        charCount.textContent = inputText.value.length.toLocaleString();
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

    // --- Render claims ---
    function renderResults(data, seq) {
        // Guard against stale responses.
        if (seq !== currentSubmissionSeq) {
            return;
        }

        // Show the submitted context.
        submittedText.textContent = data.submitted_text;

        if (data.source_url) {
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
        }

        data.claims.forEach((claim, idx) => {
            const card = document.createElement("article");
            card.className = "claim-card";
            card.style.animationDelay = `${idx * 0.06}s`;

            let detailsHtml = "";
            const details = [
                { label: "Date", value: claim.explicit_date },
                { label: "Location", value: claim.explicit_location },
                { label: "Quantity", value: claim.explicit_quantity },
                { label: "Qualifications", value: claim.qualifications },
            ];
            details.forEach((d) => {
                if (d.value) {
                    detailsHtml += `
                        <span class="claim-detail">
                            <span class="detail-label">${d.label}:</span>
                            ${escapeHtml(d.value)}
                        </span>`;
                }
            });

            card.innerHTML = `
                <div class="claim-top-row">
                    <span class="claim-number">#${idx + 1}</span>
                    <span class="claim-type-tag ${claim.claim_type}">${claim.claim_type}</span>
                </div>
                <div class="claim-assertion">${escapeHtml(claim.normalized_assertion)}</div>
                <div class="claim-original">"${escapeHtml(claim.original_wording)}"</div>
                ${detailsHtml ? `<div class="claim-details">${detailsHtml}</div>` : ""}
            `;
            claimsList.appendChild(card);
        });

        resultsSection.classList.remove("hidden");
        resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
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

            // If a newer submission happened while awaiting network, discard
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

            // Check again after parsing
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
            executeSubmission,
            renderResults,
            showError,
            hideError,
            setLoading,
        };
    }

    // --- Utilities ---
    function escapeHtml(str) {
        const div = document.createElement("div");
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }
})();
