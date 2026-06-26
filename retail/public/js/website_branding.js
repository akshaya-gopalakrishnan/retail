(function () {
    const STORAGE_KEY = "retail.brand_theme";
    const ATTRIBUTE = "data-retail-brand-theme";
    const DEFAULT_THEME = "executive-navy";

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

    applyTheme();
})();
