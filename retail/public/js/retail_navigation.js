(function() {
    const DIRECT_MAPPING = {
        'Items List': ['List', 'Item'],
        'Item Groups': ['List', 'Item Group'],
        'Price Lists': ['List', 'Price List'],
        'Brands': ['List', 'Brand'],

        'Customers': ['List', 'Customer'],
        'Sales Orders': ['List', 'Sales Order'],
        'Sales Invoices': ['List', 'Sales Invoice'],
        'Sales Returns': ['List', 'Sales Invoice', {"is_return": 1}],
        'Delivery Notes': ['List', 'Delivery Note'],

        'Suppliers': ['List', 'Supplier'],
        'Purchase Orders': ['List', 'Purchase Order'],
        'Purchase Receipts': ['List', 'Purchase Receipt'],
        'Purchase Bills': ['List', 'Purchase Invoice'],
        'Purchase Returns': ['List', 'Purchase Invoice', {"is_return": 1}],

        'Warehouses': ['List', 'Warehouse'],
        'Stock Adjustments': ['List', 'Stock Entry'],
        'Stock Take': ['List', 'Stock Reconciliation'],
        'Serials & Batches': ['List', 'Serial and Batch Bundle'],

        'Bank Accounts': ['List', 'Bank Account'],
        'Payments': ['List', 'Payment Entry'],
        'Taxes': ['List', 'Sales Taxes and Charges Template'],
        'Journal Entries': ['List', 'Journal Entry'],

        'Staff & Users': ['List', 'User'],
        'Branding': ['List', 'Letter Head'],
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

        'Bank Account': 'Accounts',
        'Payment Entry': 'Accounts',
        'Sales Taxes and Charges Template': 'Accounts',
        'Journal Entry': 'Accounts',

        'User': 'Settings',
        'Letter Head': 'Settings',
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

        'Bank Account': 'Bank Accounts',
        'Payment Entry': 'Payments',
        'Sales Taxes and Charges Template': 'Taxes',
        'Journal Entry': 'Journal Entries',

        'User': 'Staff & Users',
        'Letter Head': 'Branding',
        'Counter': 'Counters'
    };

    const CHILD_TO_PARENT = {
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

        'Bank Accounts': 'Accounts',
        'Payments': 'Accounts',
        'Taxes': 'Accounts',
        'Journal Entries': 'Accounts',

        'Staff & Users': 'Settings',
        'Branding': 'Settings',
        'Counters': 'Settings'
    };

    const get_direct_child = (container) => {
        return Array.from(container.children).find(child =>
            child.classList.contains('desk-sidebar-item')
        );
    };

    const get_workspace_url = (workspace) => {
        return `/app/${frappe.router.slug(workspace)}`;
    };

    const get_query_filters = () => {
        const filters = {};

        new URLSearchParams(window.location.search).forEach((value, field) => {
            filters[field] = value;
        });

        return filters;
    };

    const get_route_filters = (route) => {
        return Object.assign(
            {},
            route.find(part => $.isPlainObject(part)) || {},
            get_query_filters(),
            frappe.route_options || {}
        );
    };

    const is_truthy_filter = (value) => {
        return value === true || value === 1 || value === '1' || value === 'true';
    };

    const append_query = (url, filters) => {
        if (!filters || !Object.keys(filters).length) return url;

        const params = new URLSearchParams();
        Object.entries(filters).forEach(([field, value]) => {
            params.set(field, value);
        });

        return `${url}?${params.toString()}`;
    };

    const get_target_url = (target) => {
        const route = target.filter(part => !$.isPlainObject(part));
        const filters = target.find(part => $.isPlainObject(part));
        const url = frappe.router.make_url(
            frappe.router.convert_from_standard_route(route)
        );

        return append_query(url, filters);
    };

    const get_anchor_app_url = (anchor) => {
        const href = anchor.getAttribute('href');
        if (!href || href === '#') return '';

        const url = new URL(href, window.location.origin);
        if (url.origin !== window.location.origin || !frappe.router.is_app_route(url.pathname)) {
            return '';
        }

        return `${url.pathname}${url.search}${url.hash}`;
    };

    const wait_for_route = () => {
        return new Promise(resolve => {
            setTimeout(() => {
                if (frappe.after_ajax) {
                    frappe.after_ajax(resolve);
                } else {
                    resolve();
                }
            }, 100);
        });
    };

    const route_to_url = (url, replace = false) => {
        frappe.route_options = null;
        frappe.route_hash = null;

        const current_url = `${window.location.pathname}${window.location.search}${window.location.hash}`;

        if (current_url !== url) {
            if (replace) {
                window.history.replaceState(null, null, url);
            } else {
                window.history.pushState(null, null, url);
            }
            frappe.router.route();
        }

        return wait_for_route();
    };

    const get_route_state = (route) => {
        if (!route) return {};

        const view = route[0]?.toLowerCase();

        if (view === 'workspaces' || view === 'workspace') {
            const ws_name = decodeURIComponent(route[route[1] === 'private' ? 2 : 1] || '');

            return {
                main: ws_name,
                child: ''
            };
        }

        if (view === 'list' || view === 'form') {
            const doctype = route[1];
            const filters = get_route_filters(route);
            let child = DOCTYPE_TO_CHILD[doctype];

            if (doctype === 'Sales Invoice' && is_truthy_filter(filters.is_return)) {
                child = 'Sales Returns';
            } else if (doctype === 'Purchase Invoice' && is_truthy_filter(filters.is_return)) {
                child = 'Purchase Returns';
            }

            return {
                main: DOCTYPE_TO_WORKSPACE[doctype],
                child
            };
        }

        return {};
    };

    const RetailSidebar = {
        sync: function(route) {
            const state = get_route_state(route || frappe.get_route());
            this.apply_dom_state(state.main, state.child);
        },

        sync_from_url: function() {
            const route = frappe.get_route();

            if (route?.length) {
                this.sync(route);
                return;
            }

            frappe.router.parse().then(parsed_route => this.sync(parsed_route));
        },

        schedule_sync: function() {
            [50, 150, 350, 700, 1200].forEach(delay => {
                setTimeout(() => this.sync_from_url(), delay);
            });
        },

        apply_dom_state: function(main, child) {
            document
                .querySelectorAll('.sidebar-item-container, .desk-sidebar-item')
                .forEach(el => {
                    el.classList.remove(
                        'selected',
                        'active',
                        'retail-secondary-active',
                        'retail-visited-active'
                    );
                });

            if (!main) return;

            document.querySelectorAll('.sidebar-item-container').forEach(container => {
                const label = container.querySelector('.sidebar-item-label')?.innerText.trim();
                const inner = get_direct_child(container);

                if (label === main) {
                    container.classList.add('selected', 'active');
                    if (inner) inner.classList.add('selected', 'active');
                }

                if (child && label === child) {
                    container.classList.add('retail-secondary-active');
                    this.open_parent_menu(container);
                }
            });
        },

        open_parent_menu: function(child_container) {
            const child_section = child_container.closest('.sidebar-child-item');
            if (!child_section) return;

            child_section.classList.remove('hidden');

            const parent_container = child_section.closest('.sidebar-item-container');
            const drop_icon = get_direct_child(parent_container)?.querySelector('.drop-icon');
            const icon = drop_icon?.querySelector('use');

            if (icon) icon.setAttribute('href', '#es-line-up');
        }
    };

    document.addEventListener('click', function(e) {
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
        if (e.target.closest('.drop-icon, .sidebar-item-control')) return;

        const anchor = e.target.closest('.item-anchor');
        if (!anchor) return;
        if (anchor.getAttribute('target') === '_blank') return;

        const item = e.target.closest('.sidebar-item-container');
        const label = item?.querySelector('.sidebar-item-label')?.innerText.trim();

        const parent = CHILD_TO_PARENT[label];
        const target = DIRECT_MAPPING[label];

        if (!parent) return;

        const target_url = target ? get_target_url(target) : get_anchor_app_url(anchor);
        if (!target_url) return;

        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();

        RetailSidebar.apply_dom_state(parent, '');

        const workspace_url = get_workspace_url(parent);

        route_to_url(workspace_url, true)
            .then(() => route_to_url(target_url))
            .then(() => {
                RetailSidebar.apply_dom_state(parent, label);
                RetailSidebar.schedule_sync();
            });
    }, true);

    frappe.router.on('change', () => {
        RetailSidebar.schedule_sync();
    });

    window.addEventListener('popstate', () => {
        setTimeout(() => {
            RetailSidebar.schedule_sync();
        }, 100);
    });

    const observe_sidebar = () => {
        const target = document.querySelector('.layout-side-section');

        if (!target) {
            setTimeout(observe_sidebar, 500);
            return;
        }

        const observer = new MutationObserver(() => {
            observer.disconnect();
            RetailSidebar.sync_from_url();

            start();
        });

        const start = () => {
            observer.observe(target, {
                childList: true,
                subtree: true
            });
        };

        start();
    };

    const style = document.createElement('style');
    style.innerHTML = `
        .sidebar-item-container.selected > .desk-sidebar-item,
        .sidebar-item-container.active > .desk-sidebar-item {
            background-color: var(--fg-color, #f0f4f7) !important;
        }

        .sidebar-item-container.selected > .desk-sidebar-item > .item-anchor > .sidebar-item-label,
        .sidebar-item-container.active > .desk-sidebar-item > .item-anchor > .sidebar-item-label {
            font-weight: 700 !important;
            color: #000 !important;
        }

        .sidebar-item-container.retail-secondary-active > .desk-sidebar-item {
            border-left: 4px solid var(--primary-color) !important;
            background-color: var(--control-bg) !important;
        }

        .sidebar-item-container.retail-secondary-active > .desk-sidebar-item > .item-anchor > .sidebar-item-label {
            font-weight: 700 !important;
            color: #000 !important;
        }
    `;

    document.head.appendChild(style);

    $(document).ready(() => {
        observe_sidebar();
        RetailSidebar.sync_from_url();
    });

})();
