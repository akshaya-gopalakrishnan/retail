/**
 * RETAIL ICONS INITIALIZATION
 * 
 * Initializes Lucide Icons and maps sidebar items to appropriate icons
 * This script runs after the sidebar is loaded
 * 
 * Last Updated: 2026-06-05
 */

(function() {
    // Icon mapping: sidebar label -> lucide icon name
    const ICON_MAP = {
        // Sales Module
        'Customers': { icon: 'users', class: 'sales-icon' },
        'Sales Orders': { icon: 'shopping-cart', class: 'sales-icon' },
        'Sales Invoices': { icon: 'receipt', class: 'sales-icon' },
        'Sales Returns': { icon: 'undo-2', class: 'sales-icon' },
        'Delivery Notes': { icon: 'truck', class: 'sales-icon' },

        // Purchases Module
        'Suppliers': { icon: 'building-2', class: 'purchase-icon' },
        'Purchase Orders': { icon: 'clipboard-list', class: 'purchase-icon' },
        'Purchase Receipts': { icon: 'package', class: 'purchase-icon' },
        'Purchase Bills': { icon: 'file-text', class: 'purchase-icon' },
        'Purchase Returns': { icon: 'undo-2', class: 'purchase-icon' },

        // Stocks Module
        'Warehouses': { icon: 'home', class: 'stock-icon' },
        'Stock Adjustments': { icon: 'align-justify', class: 'stock-icon' },
        'Stock Take': { icon: 'check-square', class: 'stock-icon' },
        'Serials & Batches': { icon: 'tag', class: 'stock-icon' },

        // Items Module
        'Items List': { icon: 'box', class: 'items-icon' },
        'Item Groups': { icon: 'grid', class: 'items-icon' },
        'Price Lists': { icon: 'tag', class: 'items-icon' },
        'Brands': { icon: 'flag', class: 'items-icon' },

        // Accounts Module
        'Bank Accounts': { icon: 'credit-card', class: 'accounts-icon' },
        'Payments': { icon: 'dollar-sign', class: 'accounts-icon' },
        'Taxes': { icon: 'percent', class: 'accounts-icon' },
        'Journal Entries': { icon: 'book-open', class: 'accounts-icon' },

        // Settings Module
        'Staff & Users': { icon: 'users-cog', class: 'settings-icon' },
        'Branding': { icon: 'palette', class: 'settings-icon' },
        'Counters': { icon: 'layout', class: 'settings-icon' }
    };

    /**
     * Apply icons to sidebar items
     */
    const apply_icons_to_sidebar = () => {
        document.querySelectorAll('.sidebar-child-item').forEach(item => {
            const label = item.querySelector('.sidebar-item-label')?.innerText.trim();
            if (!label) return;

            const iconConfig = ICON_MAP[label];
            if (!iconConfig) return;

            // Get or create the icon element
            let iconElement = item.querySelector('[data-lucide]');
            if (!iconElement) {
                iconElement = document.createElement('i');
                iconElement.setAttribute('data-lucide', iconConfig.icon);
                iconElement.classList.add(iconConfig.class);
                
                const labelElement = item.querySelector('.sidebar-item-label');
                if (labelElement) {
                    item.insertBefore(iconElement, labelElement);
                }
            } else {
                iconElement.setAttribute('data-lucide', iconConfig.icon);
                iconElement.className = iconConfig.class;
            }
        });

        // Initialize Lucide icons
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }
    };

    /**
     * Wait for sidebar to be ready, then apply icons
     */
    const init_icons = () => {
        const sidebar = document.querySelector('.layout-side-section');
        
        if (!sidebar) {
            setTimeout(init_icons, 500);
            return;
        }

        // Initial application
        apply_icons_to_sidebar();

        // Watch for sidebar mutations and reapply icons
        const observer = new MutationObserver(() => {
            apply_icons_to_sidebar();
        });

        observer.observe(sidebar, {
            childList: true,
            subtree: true,
            characterData: false
        });
    };

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init_icons);
    } else {
        init_icons();
    }
})();
