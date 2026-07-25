/* Job Board Scraper dashboard i18n & theme switcher.
 *
 * Responsibilities:
 *   1. Apply the persisted language + theme on every page load.
 *   2. Swap in-text translations when the user changes the language.
 *   3. Swap the Bootstrap theme (``data-bs-theme``) when the user
 *      changes the theme (light/dark/auto).
 *   4. Persist the choices in localStorage so they survive reloads.
 *
 * The initial application of theme + lang is done by an inline
 * script in base.html BEFORE this file loads, so the user never sees
 * a flash of light content. This file handles runtime switching.
 */

(function () {
    "use strict";

    var STORAGE_LANG = "jbs:lang";
    var STORAGE_THEME = "jbs:theme";
    var DEFAULT_LANG = "en";
    var DEFAULT_THEME = "auto";
    var SUPPORTED_LANGS = ["en", "vi"];
    var SUPPORTED_THEMES = ["light", "dark", "auto"];

    function readChoice(key, fallback, allowed) {
        try {
            var value = localStorage.getItem(key);
            if (allowed && allowed.indexOf(value) === -1) {
                return fallback;
            }
            return value || fallback;
        } catch (e) {
            return fallback;
        }
    }

    function writeChoice(key, value) {
        try {
            localStorage.setItem(key, value);
        } catch (e) {
            // Storage may be unavailable (e.g. private mode); ignore.
        }
    }

    function resolveTheme(theme) {
        if (theme === "auto") {
            return window.matchMedia &&
                window.matchMedia("(prefers-color-scheme: dark)").matches
                ? "dark"
                : "light";
        }
        return theme;
    }

    function applyTheme(theme) {
        var resolved = resolveTheme(theme);
        document.documentElement.setAttribute("data-bs-theme", resolved);
        document.documentElement.setAttribute("data-jbs-theme", theme);
    }

    function setLang(lang) {
        if (SUPPORTED_LANGS.indexOf(lang) === -1) {
            lang = DEFAULT_LANG;
        }
        writeChoice(STORAGE_LANG, lang);
        document.documentElement.setAttribute("lang", lang);
        loadAndApplyLocale(lang);
        updateActiveLabels(".locale-switcher", lang);
    }

    function setTheme(theme) {
        if (SUPPORTED_THEMES.indexOf(theme) === -1) {
            theme = DEFAULT_THEME;
        }
        writeChoice(STORAGE_THEME, theme);
        applyTheme(theme);
        updateActiveLabels(".theme-switcher", theme);
    }

    function resolveKey(dict, key) {
        var parts = key.split(".");
        var node = dict;
        for (var i = 0; i < parts.length; i++) {
            if (node && typeof node === "object" && parts[i] in node) {
                node = node[parts[i]];
            } else {
                return null;
            }
        }
        return typeof node === "string" ? node : null;
    }

    function applyTranslations(dict) {
        // 1. Replace elements with [data-i18n="key"] (textNode children).
        var nodes = document.querySelectorAll("[data-i18n]");
        nodes.forEach(function (el) {
            var key = el.getAttribute("data-i18n");
            var value = resolveKey(dict, key);
            if (value !== null) {
                el.textContent = value;
            }
        });

        // 2. Replace placeholders / aria / title attributes.
        var attrNodes = document.querySelectorAll("[data-i18n-attr]");
        attrNodes.forEach(function (el) {
            var raw = el.getAttribute("data-i18n-attr");
            // Format: "attr1:key1;attr2:key2"
            raw.split(";").forEach(function (pair) {
                var parts = pair.split(":");
                if (parts.length !== 2) return;
                var attr = parts[0].trim();
                var key = parts[1].trim();
                var value = resolveKey(dict, key);
                if (attr && value !== null) {
                    el.setAttribute(attr, value);
                }
            });
        });
    }

    var activeLocale = DEFAULT_LANG;

    function loadAndApplyLocale(lang) {
        activeLocale = lang;
        fetch("/api/i18n/" + encodeURIComponent(lang), {
            credentials: "same-origin",
        })
            .then(function (r) {
                if (!r.ok) {
                    throw new Error("Locale fetch failed: " + r.status);
                }
                return r.json();
            })
            .then(function (dict) {
                applyTranslations(dict);
                window.dispatchEvent(
                    new CustomEvent("jbs:locale", { detail: { lang: lang } })
                );
            })
            .catch(function (err) {
                console.warn("i18n: failed to load locale", lang, err);
            });
    }

    function updateActiveLabels(scope, value) {
        var items = document.querySelectorAll(scope + " [data-value]");
        items.forEach(function (el) {
            if (el.getAttribute("data-value") === value) {
                el.classList.add("active");
            } else {
                el.classList.remove("active");
            }
        });
    }

    function bindClickHandlers() {
        document.querySelectorAll(".locale-switcher [data-value]").forEach(function (el) {
            el.addEventListener("click", function (ev) {
                ev.preventDefault();
                setLang(el.getAttribute("data-value"));
            });
        });

        document.querySelectorAll(".theme-switcher [data-value]").forEach(function (el) {
            el.addEventListener("click", function (ev) {
                ev.preventDefault();
                setTheme(el.getAttribute("data-value"));
            });
        });
    }

    function watchSystemTheme() {
        if (!window.matchMedia) return;
        var mql = window.matchMedia("(prefers-color-scheme: dark)");
        var handler = function () {
            var stored = readChoice(STORAGE_THEME, DEFAULT_THEME, SUPPORTED_THEMES);
            if (stored === "auto") {
                applyTheme("auto");
            }
        };
        if (mql.addEventListener) {
            mql.addEventListener("change", handler);
        } else if (mql.addListener) {
            mql.addListener(handler);
        }
    }

    function bootstrap() {
        var lang = readChoice(STORAGE_LANG, DEFAULT_LANG, SUPPORTED_LANGS);
        var theme = readChoice(STORAGE_THEME, DEFAULT_THEME, SUPPORTED_THEMES);

        // re-apply the persisted choices (the inline script in
        // base.html already applied defaults — this overlays the
        // user's stored preference if it differs).
        applyTheme(theme);
        document.documentElement.setAttribute("lang", lang);

        updateActiveLabels(".locale-switcher", lang);
        updateActiveLabels(".theme-switcher", theme);

        bindClickHandlers();
        watchSystemTheme();
        loadAndApplyLocale(lang);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bootstrap);
    } else {
        bootstrap();
    }

    // Expose a tiny API for testing in DevTools.
    window.JBS_I18N = {
        setLang: setLang,
        setTheme: setTheme,
        getLang: function () {
            return readChoice(STORAGE_LANG, DEFAULT_LANG, SUPPORTED_LANGS);
        },
        getTheme: function () {
            return readChoice(STORAGE_THEME, DEFAULT_THEME, SUPPORTED_THEMES);
        },
        getActiveLocale: function () {
            return activeLocale;
        },
    };
})();
