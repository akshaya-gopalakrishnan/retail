(() => {
  // ../retail/retail/public/js/website_branding.js
  (function() {
    const STORAGE_KEY = "retail.brand_theme";
    const ATTRIBUTE = "data-retail-brand-theme";
    const DEFAULT_THEME = "executive-navy";
    const BRAND_NAME = "CELESTA ERP";
    const APP_ICON = "/assets/retail/images/business-suite-app-icon.svg?v=3";
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
          logo.alt = "CELESTA ERP";
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

  // ../retail/retail/public/js/utils/prevent_history_swipe.js
  (() => {
    if (window.retail_history_swipe_guard)
      return;
    window.retail_history_swipe_guard = true;
    document.addEventListener("wheel", (event) => {
      if (!event.cancelable || event.ctrlKey || event.defaultPrevented)
        return;
      if (Math.abs(event.deltaX) <= Math.abs(event.deltaY))
        return;
      for (const element of event.composedPath()) {
        if (!(element instanceof Element))
          continue;
        const style = getComputedStyle(element);
        if (!/^(auto|scroll|overlay)$/.test(style.overflowX))
          continue;
        const extent = element.scrollWidth - element.clientWidth;
        if (extent <= 1)
          continue;
        const minimum = style.direction === "rtl" ? -extent : 0;
        const maximum = style.direction === "rtl" ? 0 : extent;
        if (event.deltaX < 0 && element.scrollLeft > minimum + 1)
          return;
        if (event.deltaX > 0 && element.scrollLeft < maximum - 1)
          return;
      }
      event.preventDefault();
    }, { passive: false, capture: true });
  })();
})();
//# sourceMappingURL=retail_website.bundle.RD42KV7O.js.map
