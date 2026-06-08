(function() {
    console.log('retail_navigation: script loaded', {host: window.location.host, readyState: document.readyState});
    const ICON_MAP = {
        'home': { icon: 'fa fa-home', cls: 'color-settings' },
        'items': { icon: 'fa fa-cubes', cls: 'color-items' },
        'sales': { icon: 'fa fa-shopping-cart', cls: 'color-sales' },
        'purchases': { icon: 'fa fa-cart-arrow-down', cls: 'color-purchase' },
        'stocks': { icon: 'fa fa-archive', cls: 'color-stock' },
        'accounts': { icon: 'fa fa-university', cls: 'color-accounts' },
        'reports': { icon: 'fa fa-bar-chart', cls: 'color-accounts' },
        'settings': { icon: 'fa fa-cog', cls: 'color-settings' },
        'purchase orders': { icon: 'fa fa-file-text', cls: 'color-purchase' },
        'purchase receipts': { icon: 'fa fa-file-text', cls: 'color-purchase' },
        'purchase bills': { icon: 'fa fa-money', cls: 'color-purchase' },
        'purchase returns': { icon: 'fa fa-undo', cls: 'color-purchase' },
        'suppliers': { icon: 'fa fa-building', cls: 'color-purchase' },
        'items list': { icon: 'fa fa-cubes', cls: 'color-items' },
        'item groups': { icon: 'fa fa-th-large', cls: 'color-items' },
        'price lists': { icon: 'fa fa-tags', cls: 'color-items' },
        'brands': { icon: 'fa fa-bookmark', cls: 'color-items' },
        'customers': { icon: 'fa fa-users', cls: 'color-sales' },
        'sales orders': { icon: 'fa fa-shopping-cart', cls: 'color-sales' },
        'sales invoices': { icon: 'fa fa-file-text', cls: 'color-sales' },
        'sales returns': { icon: 'fa fa-undo', cls: 'color-sales' },
        'delivery notes': { icon: 'fa fa-truck', cls: 'color-sales' },
        'warehouses': { icon: 'fa fa-archive', cls: 'color-stock' },
        'stock adjustments': { icon: 'fa fa-wrench', cls: 'color-stock' },
        'stock take': { icon: 'fa fa-clipboard', cls: 'color-stock' },
        'serials & batches': { icon: 'fa fa-barcode', cls: 'color-stock' },
        'stock status': { icon: 'fa fa-bar-chart', cls: 'color-stock' },
        'bank accounts': { icon: 'fa fa-university', cls: 'color-accounts' },
        'payments': { icon: 'fa fa-money', cls: 'color-accounts' },
        'taxes': { icon: 'fa fa-percent', cls: 'color-accounts' },
        'journal entries': { icon: 'fa fa-book', cls: 'color-accounts' },
        'accounts receivable': { icon: 'fa fa-arrow-circle-down', cls: 'color-accounts' },
        'accounts payable': { icon: 'fa fa-arrow-circle-up', cls: 'color-accounts' },
        'business profile': { icon: 'fa fa-building', cls: 'color-settings' },
        'staff & users': { icon: 'fa fa-user', cls: 'color-settings' },
        'branding': { icon: 'fa fa-paint-brush', cls: 'color-settings' },
        'system rules': { icon: 'fa fa-gavel', cls: 'color-settings' },
        'counters': { icon: 'fa fa-arrow-up', cls: 'color-settings' }
    };
    const DESKTOP_MEDIA = '(min-width: 992px)';
    const DIRECT_MAPPING = {
        'Items List': ['List', 'Item'],
        'Item Groups': ['List', 'Item Group'],
        'Price Lists': ['List', 'Item Price'],
        'Brands': ['List', 'Brand'],
        'Customers': ['List', 'Customer'],
        'Sales Orders': ['List', 'Sales Order'],
        'Sales Invoices': ['List', 'Sales Invoice'],
        'Sales Returns': ['List', 'Sales Invoice', { is_return: 1 }],
        'Delivery Notes': ['List', 'Delivery Note'],
        'Suppliers': ['List', 'Supplier'],
        'Purchase Orders': ['List', 'Purchase Order'],
        'Purchase Receipts': ['List', 'Purchase Receipt'],
        'Purchase Bills': ['List', 'Purchase Invoice'],
        'Purchase Returns': ['List', 'Purchase Invoice', { is_return: 1 }],
        'Warehouses': ['List', 'Warehouse'],
        'Stock Adjustments': ['List', 'Stock Entry'],
        'Stock Take': ['List', 'Stock Reconciliation'],
        'Serials & Batches': ['List', 'Serial and Batch Bundle'],
        'Stock Status': ['List', 'Bin'],
        'Bank Accounts': ['List', 'Bank Account'],
        'Payments': ['List', 'Payment Entry'],
        'Taxes': ['List', 'Sales Taxes and Charges Template'],
        'Journal Entries': ['List', 'Journal Entry'],
        'Accounts Receivable': ['query-report', 'Accounts Receivable'],
        'Accounts Payable': ['query-report', 'Accounts Payable'],
        'Business Profile': ['List', 'Company'],
        'Staff & Users': ['List', 'User'],
        'Branding': ['List', 'Letter Head'],
        'System Rules': ['List', 'Document Naming Rule'],
        'Counters': ['List', 'Counter']
    };
    const DOCTYPE_TO_WORKSPACE = {
        'Item': 'Items',
        'Item Group': 'Items',
        'Price List': 'Items',
        'Brand': 'Items',
        'Customer': 'Sales',
        'Sales Order': 'Sales',
        'Sales Invoice': 'Sales',
        'Delivery Note': 'Sales',
        'Supplier': 'Purchases',
        'Purchase Order': 'Purchases',
        'Purchase Receipt': 'Purchases',
        'Purchase Invoice': 'Purchases',
        'Warehouse': 'Stocks',
        'Stock Entry': 'Stocks',
        'Stock Reconciliation': 'Stocks',
        'Serial and Batch Bundle': 'Stocks',
        'Bin': 'Stocks',
        'Bank Account': 'Accounts',
        'Payment Entry': 'Accounts',
        'Sales Taxes and Charges Template': 'Accounts',
        'Journal Entry': 'Accounts',
        'Company': 'Settings',
        'User': 'Settings',
        'Letter Head': 'Settings',
        'Document Naming Rule': 'Settings',
        'Counter': 'Settings'
    };
    const DOCTYPE_TO_CHILD = {
        'Item': 'Items List',
        'Item Group': 'Item Groups',
        'Price List': 'Price Lists',
        'Brand': 'Brands',
        'Customer': 'Customers',
        'Sales Order': 'Sales Orders',
        'Sales Invoice': 'Sales Invoices',
        'Delivery Note': 'Delivery Notes',
        'Supplier': 'Suppliers',
        'Purchase Order': 'Purchase Orders',
        'Purchase Receipt': 'Purchase Receipts',
        'Purchase Invoice': 'Purchase Bills',
        'Warehouse': 'Warehouses',
        'Stock Entry': 'Stock Adjustments',
        'Stock Reconciliation': 'Stock Take',
        'Serial and Batch Bundle': 'Serials & Batches',
        'Bin': 'Stock Status',
        'Bank Account': 'Bank Accounts',
        'Payment Entry': 'Payments',
        'Sales Taxes and Charges Template': 'Taxes',
        'Journal Entry': 'Journal Entries',
        'Company': 'Business Profile',
        'User': 'Staff & Users',
        'Letter Head': 'Branding',
        'Document Naming Rule': 'System Rules',
        'Counter': 'Counters'
    };
    const CHILD_TO_PARENT = Object.freeze({
        'Items List': 'Items',
        'Item Groups': 'Items',
        'Price Lists': 'Items',
        'Brands': 'Items',
        'Customers': 'Sales',
        'Sales Orders': 'Sales',
        'Sales Invoices': 'Sales',
        'Sales Returns': 'Sales',
        'Delivery Notes': 'Sales',
        'Suppliers': 'Purchases',
        'Purchase Orders': 'Purchases',
        'Purchase Receipts': 'Purchases',
        'Purchase Bills': 'Purchases',
        'Purchase Returns': 'Purchases',
        'Warehouses': 'Stocks',
        'Stock Adjustments': 'Stocks',
        'Stock Take': 'Stocks',
        'Serials & Batches': 'Stocks',
        'Stock Status': 'Stocks',
        'Bank Accounts': 'Accounts',
        'Payments': 'Accounts',
        'Taxes': 'Accounts',
        'Journal Entries': 'Accounts',
        'Accounts Receivable': 'Accounts',
        'Accounts Payable': 'Accounts',
        'Business Profile': 'Settings',
        'Staff & Users': 'Settings',
        'Branding': 'Settings',
        'System Rules': 'Settings',
        'Counters': 'Settings'
    });
    const TOP_LEVEL_WORKSPACES = new Set([
        'Home',
        'Items',
        'Sales',
        'Purchases',
        'Stocks',
        'Accounts',
        'Reports',
        'Settings'
    ]);

    function normalizeText(text) {
        return (text || '')
            .toString()
            .trim()
            .toLowerCase()
            .replace(/\s+/g, ' ');
    }

    function findIconConfig(labelText) {
        const name = normalizeText(labelText);
        if (!name) return null;
        if (ICON_MAP[name]) return ICON_MAP[name];
        if (ICON_MAP[name + 's']) return ICON_MAP[name + 's'];
        return null;
    }

    function createIconElement(config) {
        const iconEl = document.createElement('i');
        // Normalize Font Awesome class names for environments using FA4 (which
        // uses the base `fa` class and icon names like `fa-shopping-cart`). Replace
        // FA6 prefixes (fa-solid, fas, far, fal) with the FA4 base `fa` so the
        // local font CSS picks up the pseudo-element glyphs.
        let iconClasses = (config.icon || '')
            .replace(/\bfa-(?:solid|regular|brands|light|duotone)\b/g, 'fa')
            .replace(/\bfas\b|\bfar\b|\bfal\b/g, 'fa');
        if (!/\bfa\b/.test(iconClasses)) {
            iconClasses = `fa ${iconClasses}`.trim();
        }

        iconEl.className = `${iconClasses} ${config.cls} retail-icon`;
        iconEl.setAttribute('aria-hidden', 'true');
        return iconEl;
    }

    function isDesktop() {
        return window.matchMedia(DESKTOP_MEDIA).matches;
    }

    function isWorkspaceRoute(route) {
        const currentPage = getCurrentPage();
        return (
            (route && (route[0] === 'Workspaces' || route[0] === 'workspace')) ||
            currentPage?.dataset?.pageRoute === 'Workspaces' ||
            !!currentPage?.querySelector('.desk-sidebar:not(.retail-persistent-sidebar)')
        );
    }

    function isReturnFilter(value) {
        return value === true || value === 1 || value === '1' || value === 'true';
    }

    function getRouteFilters(route) {
        const queryFilters = {};
        new URLSearchParams(window.location.search).forEach((value, field) => {
            queryFilters[field] = value;
        });

        return Object.assign(
            {},
            route?.find(part => $.isPlainObject(part)) || {},
            queryFilters,
            frappe.route_options || {}
        );
    }

    function getTargetUrl(target) {
        const route = target.filter(part => !$.isPlainObject(part));
        const filters = target.find(part => $.isPlainObject(part));
        let url = frappe.router.make_url(frappe.router.convert_from_standard_route(route));

        if (filters && Object.keys(filters).length) {
            const params = new URLSearchParams(filters);
            url = `${url}?${params.toString()}`;
        }

        return url;
    }

    function routeToTarget(target) {
        const route = target.filter(part => !$.isPlainObject(part));
        const filters = target.find(part => $.isPlainObject(part));
        frappe.route_options = filters || null;
        frappe.set_route(...route);
    }

    function getAnchorAppUrl(anchor) {
        const href = anchor?.getAttribute('href');
        if (!href || href === '#') return '';

        const url = new URL(href, window.location.origin);
        if (url.origin !== window.location.origin || !frappe.router.is_app_route(url.pathname)) {
            return '';
        }

        return `${url.pathname}${url.search}${url.hash}`;
    }

    function waitForRoute() {
        return new Promise(resolve => {
            setTimeout(() => {
                if (frappe.after_ajax) {
                    frappe.after_ajax(resolve);
                } else {
                    resolve();
                }
            }, 100);
        });
    }

    function routeToUrl(url, replace = false) {
        frappe.route_options = null;
        frappe.route_hash = null;

        const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;

        if (currentUrl !== url) {
            if (replace) {
                window.history.replaceState(null, null, url);
            } else {
                window.history.pushState(null, null, url);
            }
            frappe.router.route();
        }

        return waitForRoute();
    }

    function getWorkspaceUrl(title, isPublic = true) {
        const slug = frappe.router.slug(title);
        return `/app/${isPublic ? slug : `private/${slug}`}`;
    }

    function getCurrentPage() {
        return frappe.container?.page || document.querySelector('.page-container[style*="display: block"]');
    }

    function getCurrentSideSection() {
        return getCurrentPage()?.querySelector('.layout-side-section');
    }

    function getItemLabel(container) {
        return container
            ?.querySelector(':scope > .desk-sidebar-item > .item-anchor .sidebar-item-label')
            ?.innerText
            ?.trim();
    }

    function escapeHtml(value) {
        if (frappe.utils?.escape_html) return frappe.utils.escape_html(value);
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function getRouteState() {
        const route = frappe.get_route();
        const view = route?.[0]?.toLowerCase();

        if (view === 'workspaces' || view === 'workspace') {
            const title = decodeURIComponent(route[route[1] === 'private' ? 2 : 1] || '');
            return { main: title, child: '' };
        }

        if (view === 'list' || view === 'form') {
            const doctype = route[1];
            const filters = getRouteFilters(route);
            let child = DOCTYPE_TO_CHILD[doctype];

            if (doctype === 'Sales Invoice' && isReturnFilter(filters.is_return)) {
                child = 'Sales Returns';
            } else if (doctype === 'Purchase Invoice' && isReturnFilter(filters.is_return)) {
                child = 'Purchase Returns';
            }

            return { main: DOCTYPE_TO_WORKSPACE[doctype], child };
        }

        return {};
    }

    // Ensure our CSS is loaded at runtime in case app_include_css wasn't picked up
    function ensureRetailCss() {
        const href = '/assets/retail/css/retail_icons.css';
        if (document.querySelector(`link[href="${href}"]`)) return;
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = href;
        link.type = 'text/css';
        link.onload = () => console.log('retail_navigation: retail_icons.css loaded');
        link.onerror = () => console.error('retail_navigation: failed to load retail_icons.css');
        document.head.appendChild(link);
    }

    // As a fallback, inject critical CSS inline to guarantee overrides
    function injectRetailInlineCss() {
        if (document.getElementById('retail-icons-inline-css')) return;
        const css = `
        @media (min-width: 992px) {
            .sidebar-item-container .sidebar-item-icon > svg,
            .sidebar-item-container .sidebar-item-icon > .icon-sm,
            .sidebar-item-container .sidebar-item-icon > .es-icon { display: none !important; }

            .retail-icon {
                font-family: "FontAwesome" !important;
                font-weight: normal !important;
                width: 24px !important;
                text-align: center !important;
                margin-right: 10px !important;
                font-size: 15px !important;
                display: inline-block !important;
                vertical-align: middle !important;
            }

            .color-items    { color: #06b6d4 !important; }
            .color-sales    { color: #3b82f6 !important; }
            .color-purchase { color: #8b5cf6 !important; }
            .color-stock    { color: #f97316 !important; }
            .color-accounts { color: #10b981 !important; }
            .color-settings { color: #64748b !important; }

            .sidebar-item-label { display: inline-block !important; vertical-align: middle !important; }
        }
        `;
        const style = document.createElement('style');
        style.id = 'retail-icons-inline-css';
        style.appendChild(document.createTextNode(css));
        document.head.appendChild(style);
    }

    function applyIcons() {
        const containers = document.querySelectorAll('.sidebar-item-container');
        if (!containers.length) {
            console.log('retail_navigation: no sidebar containers found');
            return;
        }

        console.log('retail_navigation: sidebar containers found', containers.length);

        containers.forEach(container => {
            const labelEl = container.querySelector(':scope > .desk-sidebar-item > .item-anchor .sidebar-item-label');
            const iconContainer = container.querySelector(':scope > .desk-sidebar-item > .item-anchor .sidebar-item-icon');
            const labelText = normalizeText(labelEl?.innerText);
            const config = findIconConfig(labelText);
            if (!config) return;

            console.log('retail_navigation: matched item', labelText, config.icon, config.cls);

            if (iconContainer) {
                if (iconContainer.querySelector('.retail-icon')) return;
                iconContainer.innerHTML = '';
                iconContainer.appendChild(createIconElement(config));
            } else if (labelEl) {
                if (container.querySelector('.retail-icon')) return;
                labelEl.prepend(createIconElement(config));
            }
        });
    }

    function setDropIcon(container, open) {
        const use = container
            ?.querySelector(':scope > .desk-sidebar-item .drop-icon use');
        if (use) use.setAttribute('href', open ? '#es-line-up' : '#es-line-down');
    }

    function syncSidebarState() {
        const state = getRouteState();

        document.querySelectorAll('.sidebar-item-container').forEach(container => {
            const label = getItemLabel(container);
            const directItem = container.querySelector(':scope > .desk-sidebar-item');
            const childSection = container.querySelector(':scope > .sidebar-child-item');
            const isMain = label && state.main === label;
            const isChild = label && state.child === label;
            const shouldOpen = isMain || (label && state.child && CHILD_TO_PARENT[state.child] === label);

            container.classList.toggle('retail-primary-active', !!isMain);
            container.classList.toggle('retail-secondary-active', !!isChild);
            directItem?.classList.toggle('selected', !!(isMain || isChild));

            if (childSection && shouldOpen) {
                childSection.classList.remove('hidden');
                setDropIcon(container, true);
            }
        });
    }

    function syncDesktopSidebarClass() {
        const hasSidebar = isDesktop() && !!getCurrentSideSection()?.querySelector('.retail-persistent-sidebar');
        document.body.classList.toggle('retail-has-persistent-sidebar', hasSidebar);
    }

    function removePersistentSidebar() {
        document.querySelectorAll('.retail-sidebar-overlay').forEach(sidebar => sidebar.remove());
        document.querySelectorAll('.retail-persistent-sidebar').forEach(sidebar => sidebar.remove());
        syncDesktopSidebarClass();
    }

    function getRetailSidebarHost(sideSection) {
        const existingOverlay = sideSection.querySelector('.overlay-sidebar:not(.retail-sidebar-overlay)');
        if (existingOverlay) return existingOverlay;

        let host = sideSection.querySelector('.retail-sidebar-overlay');
        if (!host) {
            host = document.createElement('div');
            host.className = 'retail-sidebar-overlay overlay-sidebar hidden-xs hidden-sm';
            sideSection.prepend(host);
        }
        return host;
    }

    function bindSubmenuRouting() {
        document.addEventListener('click', event => {
            if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            if (event.target.closest('.drop-icon, .sidebar-item-control')) return;

            const anchor = event.target.closest('.item-anchor');
            const container = anchor?.closest('.sidebar-item-container');
            const label = getItemLabel(container);
            const parent = CHILD_TO_PARENT[label];
            const target = DIRECT_MAPPING[label];

            if (parent) {
                const targetUrl = target ? getTargetUrl(target) : getAnchorAppUrl(anchor);
                if (!targetUrl) return;

                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();

                syncSidebarState();

                routeToUrl(getWorkspaceUrl(parent), true)
                    .then(() => routeToUrl(targetUrl))
                    .then(() => {
                        syncSidebarState();
                        scheduleRetry();
                    });
                return;
            }

            if (!target && !TOP_LEVEL_WORKSPACES.has(label)) return;

            event.preventDefault();
            if (target) {
                routeToTarget(target);
            } else {
                frappe.route_options = null;
                frappe.set_route(getWorkspaceUrl(label, true).replace(/^\/app\//, ''));
            }
        }, true);
    }

    function applyDirectLinks() {
        document.querySelectorAll('.sidebar-item-container').forEach(container => {
            const label = getItemLabel(container);
            const anchor = container.querySelector(':scope > .desk-sidebar-item > .item-anchor');
            const target = DIRECT_MAPPING[label];

            if (target) {
                anchor?.setAttribute('href', getTargetUrl(target));
                anchor?.setAttribute('data-retail-direct-link', '1');
            } else if (TOP_LEVEL_WORKSPACES.has(label)) {
                anchor?.setAttribute('href', getWorkspaceUrl(label, true));
                anchor?.setAttribute('data-retail-direct-link', '1');
            }
        });
    }

    function buildSidebarItem(item, pages) {
        const title = item.title;
        const children = pages.filter(page => page.parent_page === title);
        const target = DIRECT_MAPPING[title];
        const href = target ? getTargetUrl(target) : getWorkspaceUrl(title, item.public);
        const container = document.createElement('div');
        container.className = 'sidebar-item-container retail-sidebar-item';
        container.setAttribute('item-name', title);
        container.setAttribute('item-parent', item.parent_page || '');
        container.setAttribute('item-public', item.public || 0);
        container.setAttribute('item-is-hidden', item.is_hidden || 0);
        container.innerHTML = `
            <div class="desk-sidebar-item standard-sidebar-item">
                <a href="${href}" class="item-anchor block-click" title="${escapeHtml(__(title))}">
                    <span class="sidebar-item-icon"></span>
                    <span class="sidebar-item-label">${escapeHtml(__(title))}</span>
                </a>
                <div class="sidebar-item-control"></div>
            </div>
            <div class="sidebar-child-item nested-container hidden"></div>
        `;

        if (children.length) {
            const control = container.querySelector('.sidebar-item-control');
            const childSection = container.querySelector('.sidebar-child-item');
            const button = document.createElement('button');
            button.className = 'btn-reset drop-icon';
            button.innerHTML = frappe.utils.icon('es-line-down', 'sm');
            button.addEventListener('click', event => {
                event.preventDefault();
                event.stopPropagation();
                const open = childSection.classList.toggle('hidden');
                setDropIcon(container, !open);
            });
            control.appendChild(button);
            children.forEach(child => childSection.appendChild(buildSidebarItem(child, pages)));
        }

        return container;
    }

    function renderPersistentSidebar() {
        if (isWorkspaceRoute(frappe.get_route())) {
            removePersistentSidebar();
            syncDesktopSidebarClass();
            return;
        }

        const sideSection = getCurrentSideSection();
        if (!sideSection) {
            syncDesktopSidebarClass();
            return;
        }
        const host = getRetailSidebarHost(sideSection);
        if (host.querySelector('.retail-persistent-sidebar')) {
            syncDesktopSidebarClass();
            return;
        }

        frappe.xcall('frappe.desk.desktop.get_workspace_sidebar_items').then(result => {
            if (isWorkspaceRoute(frappe.get_route())) {
                removePersistentSidebar();
                return;
            }
            if (host.querySelector('.retail-persistent-sidebar')) return;

            const items = Array.isArray(result) ? result : result?.pages || [];
            const visibleItems = items.filter(item => !item.is_hidden);
            const publicItems = visibleItems.filter(item => item.public);
            const roots = publicItems.filter(item => !item.parent_page);
            const wrapper = document.createElement('div');
            wrapper.className = 'retail-persistent-sidebar standard-sidebar-section nested-container';
            wrapper.dataset.title = 'Retail';

            roots.forEach(item => wrapper.appendChild(buildSidebarItem(item, publicItems)));
            host.prepend(wrapper);
            applyIcons();
            syncSidebarState();
            syncDesktopSidebarClass();
        });
    }

    function observeSidebarChanges() {
        const observer = new MutationObserver(mutations => {
            if (mutations.some(m => m.addedNodes.length || m.removedNodes.length)) {
                console.log('retail_navigation: sidebar DOM mutated, reapplying icons');
                applyDirectLinks();
                applyIcons();
                syncSidebarState();
                renderPersistentSidebar();
                syncDesktopSidebarClass();
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    function scheduleRetry() {
        [250, 750, 1500, 3000].forEach(delay => {
            setTimeout(() => {
                console.log('retail_navigation: retry applyIcons after delay', delay);
                applyDirectLinks();
                applyIcons();
                syncSidebarState();
                renderPersistentSidebar();
            }, delay);
        });
    }

    function init() {
        ensureRetailCss();
        injectRetailInlineCss();
        applyDirectLinks();
        applyIcons();
        syncSidebarState();
        renderPersistentSidebar();
        observeSidebarChanges();
        scheduleRetry();
        bindSubmenuRouting();

        if (window.frappe?.router?.on) {
            frappe.router.on('change', () => setTimeout(() => {
                applyDirectLinks();
                applyIcons();
                syncSidebarState();
                renderPersistentSidebar();
            }, 250));
        }

        window.matchMedia(DESKTOP_MEDIA).addEventListener('change', () => {
            applyDirectLinks();
            applyIcons();
            syncSidebarState();
            renderPersistentSidebar();
        });
    }

    if (window.frappe?.ready) {
        frappe.ready(init);
    } else if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
