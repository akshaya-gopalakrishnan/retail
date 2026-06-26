(function () {
    const STORAGE_KEY = "retail.brand_theme";
    const ATTRIBUTE = "data-retail-brand-theme";
    const DEFAULT_THEME = "executive-navy";

    const THEMES = [
        {
            name: "classic",
            label: "Classic ERPNext",
            description: "Original ERPNext look. Safest fallback.",
            preview: {
                primary: "#64748b",
                accent: "#94a3b8",
                bg: "#f8fafc",
                surface: "#ffffff",
                muted: "#cbd5e1",
            },
        },
        {
            name: "executive-navy",
            label: "Executive Navy",
            description: "Premium corporate navy with muted gold.",
            preview: {
                primary: "#0b1f3a",
                accent: "#c9a227",
                bg: "#f5f7fa",
                surface: "#ffffff",
                muted: "#94a3b8",
            },
        },
        {
            name: "modern-blue",
            label: "Modern Blue",
            description: "Clean, bright, and technology-focused.",
            preview: {
                primary: "#1d4ed8",
                accent: "#0ea5e9",
                bg: "#f8fafc",
                surface: "#ffffff",
                muted: "#bfdbfe",
            },
        },
        {
            name: "graphite-pro",
            label: "Graphite Pro",
            description: "Minimal, operational, and neutral.",
            preview: {
                primary: "#2f3437",
                accent: "#3b82f6",
                bg: "#f6f7f8",
                surface: "#ffffff",
                muted: "#d1d5db",
            },
        },
        {
            name: "emerald-business",
            label: "Emerald Business",
            description: "Calm, fresh, and reliable.",
            preview: {
                primary: "#047857",
                accent: "#14b8a6",
                bg: "#f7faf8",
                surface: "#ffffff",
                muted: "#a7f3d0",
            },
        },
        {
            name: "burgundy-formal",
            label: "Burgundy Formal",
            description: "Established, warm, and formal.",
            preview: {
                primary: "#7f1d1d",
                accent: "#c8a45d",
                bg: "#fbfaf7",
                surface: "#ffffff",
                muted: "#eadfd3",
            },
        },
    ];

    function getSavedTheme() {
        return localStorage.getItem(STORAGE_KEY) || DEFAULT_THEME;
    }

    function setDocumentTheme(themeName) {
        if (themeName === "classic") {
            document.documentElement.removeAttribute(ATTRIBUTE);
            return;
        }

        document.documentElement.setAttribute(ATTRIBUTE, themeName);
    }

    function saveTheme(themeName) {
        localStorage.setItem(STORAGE_KEY, themeName);
        setDocumentTheme(themeName);
    }

    function getTheme(themeName) {
        return THEMES.find((theme) => theme.name === themeName) || THEMES[0];
    }

    function buildPreview(theme, selectedTheme) {
        const isSelected = theme.name === selectedTheme;
        const preview = theme.preview;
        const card = $(`
            <button type="button" class="retail-brand-theme-card ${isSelected ? "selected" : ""}">
                <div class="retail-brand-preview">
                    <div class="retail-brand-preview-header">
                        <span class="retail-brand-preview-dot"></span>
                        <span class="retail-brand-preview-line"></span>
                    </div>
                    <div class="retail-brand-preview-body">
                        <div class="retail-brand-preview-nav"></div>
                        <div class="retail-brand-preview-panel"></div>
                    </div>
                    <span class="retail-brand-check">${frappe.utils.icon("tick", "xs")}</span>
                </div>
                <div class="retail-brand-theme-title"></div>
                <p class="retail-brand-theme-description"></p>
            </button>
        `);

        card.css({
            "--retail-preview-primary": preview.primary,
            "--retail-preview-accent": preview.accent,
            "--retail-preview-bg": preview.bg,
            "--retail-preview-surface": preview.surface,
            "--retail-preview-muted": preview.muted,
        });
        card.find(".retail-brand-theme-title").text(theme.label);
        card.find(".retail-brand-theme-description").text(theme.description);
        card.attr("aria-pressed", isSelected ? "true" : "false");
        card.attr("title", theme.description);
        return card;
    }

    function showBrandThemeDialog() {
        const selectedTheme = getSavedTheme();
        const dialog = new frappe.ui.Dialog({
            title: __("Switch Brand Theme"),
            size: "large",
        });

        dialog.$wrapper.addClass("retail-brand-theme-dialog");
        const grid = $('<div class="retail-brand-theme-grid"></div>').appendTo(dialog.$body);

        THEMES.forEach((theme) => {
            const card = buildPreview(theme, selectedTheme);
            card.on("click", () => {
                grid.find(".retail-brand-theme-card")
                    .removeClass("selected")
                    .attr("aria-pressed", "false");
                card.addClass("selected").attr("aria-pressed", "true");
                saveTheme(theme.name);
                frappe.show_alert(__("Brand theme changed to {0}", [theme.label]), 3);
                dialog.hide();
            });
            grid.append(card);
        });

        dialog.show();
    }

    function addMenuItem() {
        const menu = $("#toolbar-user");
        if (!menu.length || menu.find('[data-retail-action="switch-brand-theme"]').length) {
            return Boolean(menu.length);
        }

        const item = $(`
            <button class="btn-reset dropdown-item" data-retail-action="switch-brand-theme">
                ${__("Switch Brand Theme")}
            </button>
        `);
        item.on("click", (event) => {
            event.preventDefault();
            showBrandThemeDialog();
        });

        const firstDivider = menu.find(".dropdown-divider").first();
        if (firstDivider.length) {
            item.insertBefore(firstDivider);
        } else {
            menu.append(item);
        }

        return true;
    }

    function addMenuItemWhenReady(attemptsLeft) {
        if (addMenuItem() || attemptsLeft <= 0) {
            return;
        }

        setTimeout(() => addMenuItemWhenReady(attemptsLeft - 1), 500);
    }

    setDocumentTheme(getSavedTheme());

    $(document).on("app_ready", () => {
        addMenuItemWhenReady(10);
        setDocumentTheme(getSavedTheme());
    });

    $(document).ready(() => {
        addMenuItemWhenReady(10);
    });

    window.retailBrandTheme = {
        themes: THEMES,
        get current() {
            return getTheme(getSavedTheme());
        },
        switchTo: saveTheme,
        show: showBrandThemeDialog,
    };
})();
