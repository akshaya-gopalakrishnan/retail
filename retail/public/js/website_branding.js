(function () {
    const STORAGE_KEY = "retail.brand_theme";
    const ATTRIBUTE = "data-retail-brand-theme";
    const DEFAULT_THEME = "executive-navy";
    const BRAND_NAME = "CELESTA ERP";
    const APP_ICON = "/assets/retail/images/celesta-app-icon.svg?v=1";

    function getTheme() {
        try {
            return localStorage.getItem(STORAGE_KEY) || DEFAULT_THEME;
        } catch (error) {
            return DEFAULT_THEME;
        }
    }

    function applyTheme() {
        const theme = getTheme();
        if (theme === "classic") {
            document.documentElement.removeAttribute(ATTRIBUTE);
        } else {
            document.documentElement.setAttribute(ATTRIBUTE, theme);
        }
    }

    function applyLoginBranding() {
        if (!/\/login(?:\?|#|$)/.test(window.location.pathname + window.location.search + window.location.hash)) {
            return;
        }

        document.querySelectorAll(".page-card-head").forEach((head) => {
            const logo = head.querySelector(".app-logo");
            if (logo) {
                logo.src = APP_ICON;
                logo.alt = "Celesta";
            }

            const title = head.querySelector("h4");
            if (title && /Frappe|Login to/i.test(title.textContent || "")) {
                title.textContent = `Login to ${BRAND_NAME}`;
            }
        });
    }

    applyTheme();
    applyLoginBranding();

    document.addEventListener("DOMContentLoaded", applyLoginBranding);
    document.addEventListener("login_rendered", applyLoginBranding);
    window.addEventListener("hashchange", applyLoginBranding);
})();
