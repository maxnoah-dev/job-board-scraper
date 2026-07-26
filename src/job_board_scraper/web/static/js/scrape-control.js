/* Manual scrape trigger controller.
 *
 * Wires up every element with [data-scrape-trigger] to POST /api/runs.
 * After starting a scrape it polls GET /api/runs/status until the run
 * finishes, then surfaces success/failure via a Bootstrap toast.
 *
 * Two scopes are supported, selected by data-scrape-scope:
 *   - "all":     run every active company (no company_slug)
 *   - "company": run only the company whose slug is in
 *                data-company-slug on the button
 *
 * The current state of the trigger is also reflected on every page so
 * that two buttons on different tabs do not fire at the same time.
 */

(function () {
    "use strict";

    var POLL_INTERVAL_MS = 2000;
    var POLL_TIMEOUT_MS = 15 * 60 * 1000; // 15 minutes

    function getLocale() {
        try {
            var lang = localStorage.getItem("jbs:lang");
            return lang === "vi" ? "vi" : "en";
        } catch (e) {
            return "en";
        }
    }

    function t(key) {
        var translations = window.JBS_I18N || {};
        var locale = getLocale();
        var bucket = translations[locale] || translations.en || {};
        var parts = key.split(".");
        var cursor = bucket;
        for (var i = 0; i < parts.length; i++) {
            if (cursor == null) return key;
            cursor = cursor[parts[i]];
        }
        return cursor || key;
    }

    function ensureTranslationsLoaded() {
        if (window.JBS_I18N) {
            return Promise.resolve();
        }
        var locale = getLocale();
        return fetch("/api/i18n/" + locale, { credentials: "same-origin" })
            .then(function (resp) {
                if (!resp.ok) throw new Error("i18n load failed");
                return resp.json();
            })
            .then(function (data) {
                window.JBS_I18N = {};
                window.JBS_I18N[locale] = data;
            })
            .catch(function () {
                window.JBS_I18N = { en: {}, vi: {} };
            });
    }

    function ensureToastContainer() {
        var existing = document.getElementById("scrape-toast-container");
        if (existing) return existing;
        var container = document.createElement("div");
        container.id = "scrape-toast-container";
        container.className =
            "toast-container position-fixed top-0 end-0 p-3";
        container.style.zIndex = "1080";
        document.body.appendChild(container);
        return container;
    }

    function showToast(kind, title, body) {
        var container = ensureToastContainer();
        var colorMap = {
            success: "bg-success text-white",
            error: "bg-danger text-white",
            info: "bg-info text-white",
            warning: "bg-warning text-dark"
        };
        var iconMap = {
            success: "\u2713",
            error: "\u2715",
            info: "\u2139",
            warning: "!"
        };
        var el = document.createElement("div");
        el.className =
            "toast align-items-center " +
            (colorMap[kind] || colorMap.info) +
            " border-0 mb-2";
        el.setAttribute("role", "alert");
        el.setAttribute("aria-live", "polite");
        el.innerHTML =
            '<div class="d-flex">' +
            '<div class="toast-body">' +
            "<strong>" +
            (iconMap[kind] || "") +
            " " +
            escapeHtml(title) +
            "</strong>" +
            (body ? "<div class=\"small mt-1\">" + escapeHtml(body) + "</div>" : "") +
            "</div>" +
            '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>' +
            "</div>";
        container.appendChild(el);
        var toast = new bootstrap.Toast(el, { delay: 6000 });
        toast.show();
        el.addEventListener("hidden.bs.toast", function () {
            el.remove();
        });
    }

    function escapeHtml(value) {
        if (value == null) return "";
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    /* Tracks which buttons have already had their original HTML captured so a
     * second busy call (e.g. "starting" -> "running") does not overwrite the
     * genuine original markup with the spinner markup we just inserted. */
    var capturedOriginalHtml = new WeakSet();

    function setButtonsBusy(busy, runningText) {
        var buttons = document.querySelectorAll("[data-scrape-trigger]");
        for (var i = 0; i < buttons.length; i++) {
            var btn = buttons[i];
            btn.disabled = busy;
            if (busy) {
                if (!capturedOriginalHtml.has(btn)) {
                    btn.dataset.originalHtml = btn.innerHTML;
                    capturedOriginalHtml.add(btn);
                }
                btn.innerHTML =
                    '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>' +
                    escapeHtml(runningText || t("scrape.running"));
            } else if (btn.dataset.originalHtml) {
                btn.innerHTML = btn.dataset.originalHtml;
                delete btn.dataset.originalHtml;
                capturedOriginalHtml.delete(btn);
            }
        }
    }

    function postRun(payload) {
        return fetch("/api/runs", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload || {})
        });
    }

    function fetchStatus() {
        return fetch("/api/runs/status", { credentials: "same-origin" }).then(
            function (r) {
                if (!r.ok) throw new Error("status fetch failed");
                return r.json();
            }
        );
    }

    function pollUntilDone() {
        var start = Date.now();
        return new Promise(function (resolve, reject) {
            function tick() {
                fetchStatus()
                    .then(function (snap) {
                        if (snap.state === "finished") {
                            resolve(snap);
                            return;
                        }
                        if (Date.now() - start > POLL_TIMEOUT_MS) {
                            reject(new Error("timeout"));
                            return;
                        }
                        setTimeout(tick, POLL_INTERVAL_MS);
                    })
                    .catch(function () {
                        setTimeout(tick, POLL_INTERVAL_MS);
                    });
            }
            tick();
        });
    }

    function runScrape(button) {
        var scope = button.getAttribute("data-scrape-scope") || "all";
        var payload = {};
        if (scope === "company") {
            payload.company_slug = button.getAttribute("data-company-slug");
        }

        ensureTranslationsLoaded().then(function () {
            setButtonsBusy(true, t("scrape.starting"));
            var conflictMessage = "";
            postRun(payload)
                .then(function (resp) {
                    if (resp.status === 409) {
                        return resp.json().then(function (body) {
                            conflictMessage =
                                (body && body.detail) ||
                                t("scrape.conflict_message");
                            var err = new Error(conflictMessage);
                            err.isConflict = true;
                            throw err;
                        });
                    }
                    if (!resp.ok) {
                        throw new Error("HTTP " + resp.status);
                    }
                    return resp.json();
                })
                .then(function (data) {
                    setButtonsBusy(true, t("scrape.running"));
                    return pollUntilDone().then(function () {
                        return data;
                    });
                })
                .then(function (data) {
                    showToast(
                        "success",
                        t("scrape.success"),
                        "#" + data.run_id
                    );
                })
                .catch(function (err) {
                    if (err && err.isConflict) {
                        showToast(
                            "warning",
                            t("scrape.conflict_title"),
                            t("scrape.conflict_message")
                        );
                        return;
                    }
                    var message =
                        err && err.message ? err.message : String(err);
                    showToast("error", t("scrape.error_title"), message);
                })
                .finally(function () {
                    setButtonsBusy(false);
                });
        });
    }

    function init() {
        var buttons = document.querySelectorAll("[data-scrape-trigger]");
        if (!buttons.length) return;

        // Reflect server-side state on page load so the buttons are
        // already disabled if a scrape is mid-flight.
        fetchStatus()
            .then(function (snap) {
                if (snap.state === "running") {
                    setButtonsBusy(true, t("scrape.running"));
                    // Continue polling in case the user just landed here.
                    pollUntilDone().finally(function () {
                        setButtonsBusy(false);
                    });
                }
            })
            .catch(function () {
                /* status probe failed; UI stays interactive */
            });

        for (var i = 0; i < buttons.length; i++) {
            buttons[i].addEventListener("click", function (event) {
                event.preventDefault();
                runScrape(event.currentTarget);
            });
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
