(function() {
    if (window.retailNavigationLoaded) return;
    window.retailNavigationLoaded = true;
    if (window.location.pathname === '/app/business-home-desk') {
        window.location.replace('/app/business-home');
        return;
    }
    const DEBUG = false;
    const debugLog = (...args) => DEBUG && console.log(...args);
    debugLog('retail_navigation: script loaded', {host: window.location.host, readyState: document.readyState});
    const OPEN_WORK_STORAGE_KEY = 'retail_open_work_tabs_v3';
    const OPEN_SIDEBAR_STORAGE_KEY = 'retail_open_sidebar_groups_v1';
    const OPEN_WORK_TTL_MS = 12 * 60 * 60 * 1000;
    const ICON_MAP = {
        'loyalty program list': { icon: 'fa fa-list', cls: 'color-sales' },
        'loyalty program': { icon: 'fa fa-star', cls: 'color-sales' },
        'loyalty program report': { icon: 'fa fa-bar-chart', cls: 'color-sales' },
        'loyalty point entry': { icon: 'fa fa-book', cls: 'color-sales' },
        'loyalty point entry report': { icon: 'fa fa-line-chart', cls: 'color-sales' },

        'promotions': { icon: 'fa fa-gift', cls: 'color-sales' },
        'promo price': { icon: 'fa fa-tag', cls: 'color-purchase' },
        'buy x get y promotion': { icon: 'fa fa-gift', cls: 'color-purchase' },
        'gift voucher promotion': { icon: 'fa fa-gift', cls: 'color-purchase' },
        'gift voucher ledger': { icon: 'fa fa-book', cls: 'color-purchase' },
        'pricing rule': { icon: 'fa fa-percent', cls: 'color-purchase' },
        'promotional scheme': { icon: 'fa fa-tags', cls: 'color-purchase' },
        'home': { icon: 'fa fa-home', cls: 'color-settings' },
        'business home': { icon: 'fa fa-home', cls: 'color-settings' },
        'items': { icon: 'fa fa-cubes', cls: 'color-items' },
        'sales': { icon: 'fa fa-shopping-cart', cls: 'color-sales' },
        'pos': { icon: 'fa fa-desktop', cls: 'color-sales' },
        'hr': { icon: 'fa fa-users', cls: 'color-hr' },
        'recruitment': { icon: 'fa fa-user-plus', cls: 'color-hr-recruitment' },
        'employee lifecycle': { icon: 'fa fa-random', cls: 'color-hr-lifecycle' },
        'performance': { icon: 'fa fa-star', cls: 'color-hr-performance' },
        'shift & attendance': { icon: 'fa fa-calendar-check-o', cls: 'color-hr-attendance' },
        'expense claims': { icon: 'fa fa-money', cls: 'color-hr-expenses' },
        'leaves': { icon: 'fa fa-calendar', cls: 'color-hr-leaves' },
        'purchases': { icon: 'fa fa-cart-arrow-down', cls: 'color-purchase' },
        'stocks': { icon: 'fa fa-archive', cls: 'color-stock' },
        'manufacturing': { icon: 'fa fa-industry', cls: 'color-manufacturing' },
        'van sales': { icon: 'fa fa-truck', cls: 'color-sales' },
        'fleet': { icon: 'fa fa-truck', cls: 'color-sales' },
        'van fleet': { icon: 'fa fa-truck', cls: 'color-sales' },
        'van sales fleet link': { icon: 'fa fa-truck', cls: 'color-sales' },
        'driver': { icon: 'fa fa-id-card-o', cls: 'color-sales' },
        'van driver': { icon: 'fa fa-id-card-o', cls: 'color-sales' },
        'van sales driver link': { icon: 'fa fa-id-card-o', cls: 'color-sales' },
        'van session': { icon: 'fa fa-clock-o', cls: 'color-sales' },
        'van sessions': { icon: 'fa fa-clock-o', cls: 'color-sales' },
        'van sales sessions link': { icon: 'fa fa-clock-o', cls: 'color-sales' },
        'stock request': { icon: 'fa fa-list-alt', cls: 'color-stock' },
        'van stock request': { icon: 'fa fa-list-alt', cls: 'color-stock' },
        'van sales stock request link': { icon: 'fa fa-list-alt', cls: 'color-stock' },
        'van stock entries': { icon: 'fa fa-exchange', cls: 'color-stock' },
        'van sales stock entries link': { icon: 'fa fa-exchange', cls: 'color-stock' },
        'van stock view': { icon: 'fa fa-cubes', cls: 'color-stock' },
        'van sales stock view link': { icon: 'fa fa-cubes', cls: 'color-stock' },
        'van sales invoice': { icon: 'fa fa-file-text', cls: 'color-sales' },
        'van sales invoice link': { icon: 'fa fa-file-text', cls: 'color-sales' },
        'van payments': { icon: 'fa fa-money', cls: 'color-accounts' },
        'van sales payments link': { icon: 'fa fa-money', cls: 'color-accounts' },
        'van customers': { icon: 'fa fa-users', cls: 'color-sales' },
        'van sales customers link': { icon: 'fa fa-users', cls: 'color-sales' },
        'van items': { icon: 'fa fa-cubes', cls: 'color-items' },
        'van sales items link': { icon: 'fa fa-cubes', cls: 'color-items' },
        'van warehouses': { icon: 'fa fa-archive', cls: 'color-stock' },
        'van sales warehouses link': { icon: 'fa fa-archive', cls: 'color-stock' },
        'van sales reports': { icon: 'fa fa-bar-chart', cls: 'color-sales' },
        'van sales reports link': { icon: 'fa fa-bar-chart', cls: 'color-sales' },
        'van daily sales summary': { icon: 'fa fa-bar-chart', cls: 'color-sales' },
        'van daily stock summary': { icon: 'fa fa-bar-chart', cls: 'color-stock' },
        'van detailed sales summary': { icon: 'fa fa-list-alt', cls: 'color-sales' },
        'van profit report': { icon: 'fa fa-line-chart', cls: 'color-accounts' },
        'van wastage report': { icon: 'fa fa-exclamation-triangle', cls: 'color-stock' },
        'van outstanding collection summary': { icon: 'fa fa-money', cls: 'color-accounts' },
        'daily stock summary': { icon: 'fa fa-bar-chart', cls: 'color-stock' },
        'detailed sales summary': { icon: 'fa fa-list-alt', cls: 'color-sales' },
        'profit report': { icon: 'fa fa-line-chart', cls: 'color-accounts' },
        'wastage report': { icon: 'fa fa-exclamation-triangle', cls: 'color-stock' },
        'outstanding / collection summary': { icon: 'fa fa-money', cls: 'color-accounts' },
        'bom': { icon: 'fa fa-sitemap', cls: 'color-manufacturing' },
        'production plan': { icon: 'fa fa-calendar-check-o', cls: 'color-manufacturing' },
        'work orders': { icon: 'fa fa-tasks', cls: 'color-manufacturing' },
        'job cards': { icon: 'fa fa-id-card-o', cls: 'color-manufacturing' },
        'stock entries': { icon: 'fa fa-exchange', cls: 'color-manufacturing' },
        'quality inspection': { icon: 'fa fa-check-square-o', cls: 'color-manufacturing' },
        'manufacturing reports': { icon: 'fa fa-line-chart', cls: 'color-manufacturing' },
        'manufacturing setup': { icon: 'fa fa-cogs', cls: 'color-manufacturing' },
        'setup': { icon: 'fa fa-cogs', cls: 'color-manufacturing' },
        'manufacturing child reports': { icon: 'fa fa-line-chart', cls: 'color-manufacturing' },
        'manufacturing child setup': { icon: 'fa fa-cogs', cls: 'color-manufacturing' },
        'operations': { icon: 'fa fa-cogs', cls: 'color-manufacturing' },
        'workstations': { icon: 'fa fa-building-o', cls: 'color-manufacturing' },
        'routing': { icon: 'fa fa-code-fork', cls: 'color-manufacturing' },
        'bom creator': { icon: 'fa fa-plus-square-o', cls: 'color-manufacturing' },
        'manufacturing settings': { icon: 'fa fa-sliders', cls: 'color-manufacturing' },
        'bom stock report': { icon: 'fa fa-bar-chart', cls: 'color-manufacturing' },
        'work order stock report': { icon: 'fa fa-bar-chart', cls: 'color-manufacturing' },
        'open work orders': { icon: 'fa fa-folder-open-o', cls: 'color-manufacturing' },
        'work orders in progress': { icon: 'fa fa-spinner', cls: 'color-manufacturing' },
        'completed work orders': { icon: 'fa fa-check-circle-o', cls: 'color-manufacturing' },
        'work order summary': { icon: 'fa fa-list-alt', cls: 'color-manufacturing' },
        'job card summary': { icon: 'fa fa-list-alt', cls: 'color-manufacturing' },
        'production analytics': { icon: 'fa fa-area-chart', cls: 'color-manufacturing' },
        'accounts': { icon: 'fa fa-university', cls: 'color-accounts' },
        'reports': { icon: 'fa fa-bar-chart', cls: 'color-accounts' },
        'settings': { icon: 'fa fa-cog', cls: 'color-settings' },
        'material request': { icon: 'fa fa-clipboard', cls: 'color-purchase' },
        'material requests': { icon: 'fa fa-clipboard', cls: 'color-purchase' },
        'request for quotation': { icon: 'fa fa-question-circle', cls: 'color-purchase' },
        'request for quotations': { icon: 'fa fa-question-circle', cls: 'color-purchase' },
        'supplier quotation': { icon: 'fa fa-comments-o', cls: 'color-purchase' },
        'supplier quotations': { icon: 'fa fa-comments-o', cls: 'color-purchase' },
        'purchase orders': { icon: 'fa fa-file-text', cls: 'color-purchase' },
        'purchase receipts': { icon: 'fa fa-file-text', cls: 'color-purchase' },
        'purchase invoice': { icon: 'fa fa-money', cls: 'color-purchase' },
        'purchase invoices': { icon: 'fa fa-money', cls: 'color-purchase' },
        'purchase bills': { icon: 'fa fa-money', cls: 'color-purchase' },
        'purchase returns': { icon: 'fa fa-undo', cls: 'color-purchase' },
        'suppliers': { icon: 'fa fa-building', cls: 'color-purchase' },
        'items list': { icon: 'fa fa-cubes', cls: 'color-items' },
        'item family list': { icon: 'fa fa-sitemap', cls: 'color-items' },
        'item groups': { icon: 'fa fa-th-large', cls: 'color-items' },
        'price lists': { icon: 'fa fa-tags', cls: 'color-items' },
        'brands': { icon: 'fa fa-bookmark', cls: 'color-items' },
        'customers': { icon: 'fa fa-users', cls: 'color-sales' },
        'quotation': { icon: 'fa fa-file-text-o', cls: 'color-sales' },
        'quotations': { icon: 'fa fa-file-text-o', cls: 'color-sales' },
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
        'user list': { icon: 'fa fa-users', cls: 'color-settings' },
        'employee list': { icon: 'fa fa-id-badge', cls: 'color-hr' },
        'branding': { icon: 'fa fa-paint-brush', cls: 'color-settings' },
        'system rules': { icon: 'fa fa-gavel', cls: 'color-settings' },
        'counters': { icon: 'fa fa-arrow-up', cls: 'color-settings' },
        'pos counters': { icon: 'fa fa-desktop', cls: 'color-pos-counters' }
        , 'pos invoices': { icon: 'fa fa-file-text', cls: 'color-pos-invoices' }
        , 'pos profiles': { icon: 'fa fa-id-card', cls: 'color-pos-profiles' }
        , 'pos profile': { icon: 'fa fa-id-card', cls: 'color-settings' }
        , 'pos cashier shifts': { icon: 'fa fa-user', cls: 'color-pos-cashier-shifts' }
        , 'pos cashier shift': { icon: 'fa fa-user', cls: 'color-pos-cashier-shifts' }
        , 'pos counter sessions': { icon: 'fa fa-desktop', cls: 'color-pos-counter-sessions' }
        , 'pos counter session': { icon: 'fa fa-desktop', cls: 'color-pos-counter-sessions' }
        , 'pos opening entries': { icon: 'fa fa-sign-in', cls: 'color-pos-opening' }
        , 'pos opening entry': { icon: 'fa fa-sign-in', cls: 'color-accounts' }
        , 'pos closing entries': { icon: 'fa fa-sign-out', cls: 'color-pos-closing' }
        , 'pos closing entry': { icon: 'fa fa-sign-out', cls: 'color-accounts' }
        , 'pos branch day closings': { icon: 'fa fa-calendar-check-o', cls: 'color-pos-day-closing' }
        , 'pos branch day closing': { icon: 'fa fa-calendar-check-o', cls: 'color-pos-day-closing' }
        , 'pos sync logs': { icon: 'fa fa-exchange', cls: 'color-pos-sync' }
        , 'pos sync log': { icon: 'fa fa-exchange', cls: 'color-settings' }
        , 'pos reports': { icon: 'fa fa-bar-chart', cls: 'color-pos-reports' }
        , 'mode of payment': { icon: 'fa fa-credit-card', cls: 'color-accounts' }
        , 'pos invoice profit': { icon: 'fa fa-file-text', cls: 'color-pos-reports' }
        , 'pos invoice report': { icon: 'fa fa-file-text', cls: 'color-pos-reports' }
        , 'pos sales summary': { icon: 'fa fa-bar-chart', cls: 'color-accounts' }
        , 'pos transaction log': { icon: 'fa fa-list', cls: 'color-accounts' }
        , 'pos item-wise sales': { icon: 'fa fa-cubes', cls: 'color-sales' }
        , 'pos category/item group sales': { icon: 'fa fa-sitemap', cls: 'color-sales' }
        , 'pos category item group sales': { icon: 'fa fa-sitemap', cls: 'color-sales' }
        , 'pos hourly sales': { icon: 'fa fa-clock-o', cls: 'color-sales' }
        , 'pos return report': { icon: 'fa fa-undo', cls: 'color-sales' }
        , 'cashier wise sales': { icon: 'fa fa-user', cls: 'color-pos-cashier-shifts' }
        , 'counter wise sales': { icon: 'fa fa-desktop', cls: 'color-pos-counters' }
        , 'shift closing variance': { icon: 'fa fa-balance-scale', cls: 'color-pos-closing' }
        , 'payment mode summary': { icon: 'fa fa-credit-card', cls: 'color-accounts' }
        , 'pos payment mode summary': { icon: 'fa fa-credit-card', cls: 'color-accounts' }
        , 'pos discount report': { icon: 'fa fa-tags', cls: 'color-sales' }
        , 'pos price override report': { icon: 'fa fa-pencil-square-o', cls: 'color-sales' }
        , 'pos daily closing summary': { icon: 'fa fa-calendar-check-o', cls: 'color-pos-day-closing' }
        , 'pos cash movement report': { icon: 'fa fa-money', cls: 'color-accounts' }
        , 'sales reports': { icon: 'fa fa-line-chart', cls: 'color-sales' }
        , 'purchase reports': { icon: 'fa fa-area-chart', cls: 'color-purchase' }
        , 'stock reports': { icon: 'fa fa-bar-chart', cls: 'color-stock' }
        , 'accounts reports': { icon: 'fa fa-pie-chart', cls: 'color-accounts' }
        , 'pos sales reports': { icon: 'fa fa-bar-chart', cls: 'color-pos-reports' }
        , 'manufacturing module reports': { icon: 'fa fa-industry', cls: 'color-manufacturing' }
        , 'item group sales analysis': { icon: 'fa fa-sitemap', cls: 'color-sales' }
        , 'daily sales summary': { icon: 'fa fa-line-chart', cls: 'color-sales' }
        , 'counter performance': { icon: 'fa fa-desktop', cls: 'color-pos-counters' }
        , 'daily transaction log': { icon: 'fa fa-list', cls: 'color-sales' }
        , 'sales payment mode summary': { icon: 'fa fa-credit-card', cls: 'color-sales' }
        , 'daily profit report': { icon: 'fa fa-money', cls: 'color-sales' }
        , 'gross profit': { icon: 'fa fa-area-chart', cls: 'color-sales' }
        , 'sales tax report': { icon: 'fa fa-percent', cls: 'color-accounts' }
        , 'sales day wise tax report': { icon: 'fa fa-calendar', cls: 'color-accounts' }
        , 'purchase register': { icon: 'fa fa-book', cls: 'color-purchase' }
        , 'purchase tax report': { icon: 'fa fa-percent', cls: 'color-purchase' }
        , 'purchase day wise tax report': { icon: 'fa fa-calendar', cls: 'color-purchase' }
        , 'supplier wise returns': { icon: 'fa fa-undo', cls: 'color-purchase' }
        , 'stock balance': { icon: 'fa fa-archive', cls: 'color-stock' }
        , 'stock ledger': { icon: 'fa fa-list-alt', cls: 'color-stock' }
        , 'packing stock balance': { icon: 'fa fa-cubes', cls: 'color-stock' }
        , 'packing stock ledger': { icon: 'fa fa-list', cls: 'color-stock' }
        , 'stock movement summary': { icon: 'fa fa-exchange', cls: 'color-stock' }
        , 'stock adjustment history': { icon: 'fa fa-history', cls: 'color-stock' }
        , 'low stock reorder report': { icon: 'fa fa-warning', cls: 'color-stock' }
        , 'fast moving items': { icon: 'fa fa-forward', cls: 'color-items' }
        , 'slow moving items': { icon: 'fa fa-hourglass-half', cls: 'color-items' }
        , 'negative stock report': { icon: 'fa fa-minus-circle', cls: 'color-stock' }
        , 'near expiry report': { icon: 'fa fa-clock-o', cls: 'color-stock' }
        , 'expiry loss': { icon: 'fa fa-trash-o', cls: 'color-stock' }
        , 'general ledger': { icon: 'fa fa-book', cls: 'color-accounts' }
        , 'trial balance': { icon: 'fa fa-balance-scale', cls: 'color-accounts' }
        , 'balance sheet': { icon: 'fa fa-table', cls: 'color-accounts' }
        , 'profit and loss statement': { icon: 'fa fa-line-chart', cls: 'color-accounts' }
        , 'tax report': { icon: 'fa fa-percent', cls: 'color-accounts' }
        , 'tax reports': { icon: 'fa fa-percent', cls: 'color-accounts' }
        , 'tax payable report summary': { icon: 'fa fa-calculator', cls: 'color-accounts' }
    };
    const DESKTOP_MEDIA = '(min-width: 992px)';
    const DIRECT_MAPPING = frappe.boot?.retail_sidebar_routes || {};
    const DOCTYPE_TO_WORKSPACE = {
        'Loyalty Program': 'Promotions',
        'Loyalty Point Entry': 'Promotions',
        'Item': 'Items',
        'Item Group': 'Items',
        'Price List': 'Items',
        'Item Price': 'Items',
        'Brand': 'Items',
        'Customer': 'Sales',
        'Quotation': 'Sales',
        'Sales Order': 'Sales',
        'Sales Invoice': 'Sales',
        'POS Invoice': 'POS',
        'POS Profile': 'POS',
        'POS Cashier Shift': 'POS',
        'POS Counter Session': 'POS',
        'POS Opening Entry': 'POS',
        'POS Closing Entry': 'POS',
        'POS Branch Day Closing': 'POS',
        'POS Sync Log': 'POS',
        'Delivery Note': 'Sales',
        'Supplier': 'Purchases',
        'Material Request': 'Purchases',
        'Request for Quotation': 'Purchases',
        'Supplier Quotation': 'Purchases',
        'Purchase Order': 'Purchases',
        'Purchase Receipt': 'Purchases',
        'Purchase Invoice': 'Purchases',
        'BOM': 'Manufacturing',
        'Production Plan': 'Manufacturing',
        'Work Order': 'Manufacturing',
        'Job Card': 'Manufacturing',
        'Quality Inspection': 'Manufacturing',
        'Operation': 'Manufacturing',
        'Workstation': 'Manufacturing',
        'Routing': 'Manufacturing',
        'BOM Creator': 'Manufacturing',
        'Manufacturing Settings': 'Manufacturing',
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
        'Employee': 'Settings',
        'POS Operator Privilege': 'Settings',
        'Letter Head': 'Settings',
        'Document Naming Rule': 'Settings',
        'POS Branch Counter': 'POS',
        'Van Fleet': 'Van Sales',
        'Driver': 'Van Sales',
        'Van Session': 'Van Sales'
    };
    const DOCTYPE_TO_CHILD = {
        'Loyalty Program': 'Promotions Loyalty Program Link',
        'Loyalty Point Entry': 'Promotions Loyalty Point Entry Link',
        'Item': 'Items List',
        'Item Group': 'Item Groups',
        'Price List': 'Price Lists',
        'Item Price': 'Price Lists',
        'Brand': 'Brands',
        'Customer': 'Customers',
        'Quotation': 'Quotations',
        'Sales Order': 'Sales Orders',
        'Sales Invoice': 'Sales Invoices',
        'POS Invoice': 'POS Invoices',
        'POS Profile': 'POS Profile',
        'POS Cashier Shift': 'POS Cashier Shifts',
        'POS Counter Session': 'POS Counter Sessions',
        'POS Opening Entry': 'POS Opening Entry',
        'POS Closing Entry': 'POS Closing Entry',
        'POS Branch Day Closing': 'POS Branch Day Closing',
        'POS Sync Log': 'POS Sync Log',
        'Delivery Note': 'Delivery Notes',
        'Supplier': 'Suppliers',
        'Material Request': 'Material Requests',
        'Request for Quotation': 'Request for Quotations',
        'Supplier Quotation': 'Supplier Quotations',
        'Purchase Order': 'Purchase Orders',
        'Purchase Receipt': 'Purchase Receipts',
        'Purchase Invoice': 'Purchase Invoices',
        'BOM': 'BOM',
        'Production Plan': 'Production Plan',
        'Work Order': 'Work Orders',
        'Job Card': 'Job Cards',
        'Quality Inspection': 'Quality Inspection',
        'Operation': 'Manufacturing Setup',
        'Workstation': 'Manufacturing Setup',
        'Routing': 'Manufacturing Setup',
        'BOM Creator': 'Manufacturing Setup',
        'Manufacturing Settings': 'Manufacturing Setup',
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
        'User': 'User List',
        'Employee': 'Employee List',
        'POS Operator Privilege': 'Employee List',
        'Letter Head': 'Branding',
        'Document Naming Rule': 'System Rules',
        'POS Branch Counter': 'POS Counters',
        'Van Fleet': 'Van Fleet',
        'Driver': 'Van Driver',
        'Van Session': 'Van Sessions'
    };
    const CHILD_TO_PARENT = Object.freeze({
        'Promotions Loyalty Program Link': 'Promotions',
        'Promotions Loyalty Program List Link': 'Promotions Loyalty Program Link',
        'Promotions Loyalty Program Report Link': 'Promotions Loyalty Program Link',
        'Promotions Loyalty Point Entry Link': 'Promotions Loyalty Program Link',
        'Promotions Loyalty Point Entry Report Link': 'Promotions Loyalty Program Link',
        'Promotions Promo Price Link': 'Promotions',
        'Promotions Buy X Get Y Promotion Link': 'Promotions',
        'Promotions Gift Voucher Promotion Link': 'Promotions',
        'Promotions Gift Voucher Ledger Link': 'Promotions',
        'Promo Price': 'Promotions',
        'Buy X Get Y Promotion': 'Promotions',
        'Gift Voucher Promotion': 'Promotions',
        'Gift Voucher Ledger': 'Promotions',
        'Items List': 'Items',
        'Item Groups': 'Items',
        'Price Lists': 'Items',
        'Brands': 'Items',
        'Customers': 'Sales',
        'Quotation': 'Sales',
        'Quotations': 'Sales',
        'Sales Orders': 'Sales',
        'Sales Invoices': 'Sales',
        'Sales Returns': 'Sales',
        'Trading Invoices': 'Sales',
        'All Sales Invoices': 'Sales',
        'POS Invoices': 'POS',
        'POS Profile': 'POS',
        'POS Profiles': 'POS',
        'POS Cashier Shifts': 'POS',
        'POS Counter Sessions': 'POS',
        'POS Opening Entry': 'POS',
        'POS Opening Entries': 'POS',
        'POS Closing Entry': 'POS',
        'POS Closing Entries': 'POS',
        'POS Branch Day Closing': 'POS',
        'POS Branch Day Closings': 'POS',
        'POS Counters': 'POS',
        'POS Sync Log': 'POS',
        'POS Sync Logs': 'POS',
        'Mode of Payment': 'POS',
        'POS Payments': 'POS',
        'POS Reports': 'POS',
        'POS Invoice Profit': 'POS Reports',
        'POS Sales Summary': 'POS Reports',
        'POS Transaction Log': 'POS Reports',
        'POS Item-wise Sales': 'POS Reports',
        'POS Category/Item Group Sales': 'POS Reports',
        'POS Category Item Group Sales': 'POS Reports',
        'POS Hourly Sales': 'POS Reports',
        'POS Return Report': 'POS Reports',
        'Cashier Wise Sales': 'POS Reports',
        'Counter Wise Sales': 'POS Reports',
        'Shift Closing Variance': 'POS Reports',
        'Payment Mode Summary': 'POS Reports',
        'POS Discount Report': 'POS Reports',
        'POS Price Override Report': 'POS Reports',
        'POS Daily Closing Summary': 'POS Reports',
        'POS Cash Movement Report': 'POS Reports',
        'Counter Performance': 'POS',
        'Delivery Notes': 'Sales',
        'Suppliers': 'Purchases',
        'Material Request': 'Purchases',
        'Material Requests': 'Purchases',
        'Request for Quotation': 'Purchases',
        'Request for Quotations': 'Purchases',
        'Supplier Quotation': 'Purchases',
        'Supplier Quotations': 'Purchases',
        'Purchase Orders': 'Purchases',
        'Purchase Receipts': 'Purchases',
        'Purchase Invoice': 'Purchases',
        'Purchase Invoices': 'Purchases',
        'Purchase Bills': 'Purchases',
        'Purchase Returns': 'Purchases',
        'BOM': 'Manufacturing',
        'Production Plan': 'Manufacturing',
        'Work Orders': 'Manufacturing',
        'Job Cards': 'Manufacturing',
        'Stock Entries': 'Manufacturing',
        'Quality Inspection': 'Manufacturing',
        'Manufacturing Reports': 'Manufacturing',
        'Manufacturing Setup': 'Manufacturing',
        'BOM Stock Report': 'Manufacturing',
        'Work Order Stock Report': 'Manufacturing',
        'Open Work Orders': 'Manufacturing',
        'Work Orders in Progress': 'Manufacturing',
        'Completed Work Orders': 'Manufacturing',
        'Work Order Summary': 'Manufacturing',
        'Job Card Summary': 'Manufacturing',
        'Production Analytics': 'Manufacturing',
        'Operations': 'Manufacturing',
        'Workstations': 'Manufacturing',
        'Routing': 'Manufacturing',
        'BOM Creator': 'Manufacturing',
        'Manufacturing Settings': 'Manufacturing',
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
        'User List': 'Settings',
        'Employee List': 'Settings',
        'Branding': 'Settings',
        'System Rules': 'Settings',
        'Van Fleet': 'Van Sales',
        'Fleet': 'Van Sales',
        'Van Driver': 'Van Sales',
        'Driver': 'Van Sales',
        'Van Sessions': 'Van Sales',
        'Stock Request': 'Van Sales',
        'Van Stock Request': 'Van Sales',
        'Van Stock Entries': 'Van Sales',
        'Van Stock View': 'Van Sales',
        'Van Sales Invoice': 'Van Sales',
        'Van Payments': 'Van Sales',
        'Van Customers': 'Van Sales',
        'Van Items': 'Van Sales',
        'Van Warehouses': 'Van Sales',
        'Van Sales Fleet Link': 'Van Sales',
        'Van Sales Driver Link': 'Van Sales',
        'Van Sales Sessions Link': 'Van Sales',
        'Van Sales Stock Entries Link': 'Van Sales',
        'Van Sales Stock View Link': 'Van Sales',
        'Van Sales Invoice Link': 'Van Sales',
        'Van Sales Payments Link': 'Van Sales',
        'Van Sales Customers Link': 'Van Sales',
        'Van Sales Items Link': 'Van Sales',
        'Van Sales Warehouses Link': 'Van Sales',
        'Van Sales Reports': 'Van Sales',
        'Van Sales Reports Link': 'Van Sales',
        'Van Daily Sales Summary': 'Van Sales Reports',
        'Van Daily Stock Summary': 'Van Sales Reports',
        'Van Detailed Sales Summary': 'Van Sales Reports',
        'Van Profit Report': 'Van Sales Reports',
        'Van Wastage Report': 'Van Sales Reports',
        'Van Outstanding Collection Summary': 'Van Sales Reports'
        , 'Daily Stock Summary': 'Van Sales'
        , 'Detailed Sales Summary': 'Van Sales'
        , 'Profit Report': 'Van Sales'
        , 'Wastage Report': 'Van Sales'
        , 'Outstanding / Collection Summary': 'Van Sales'
    });
    const ROUTE_ALIAS_TO_CHILD = Object.freeze({
        'Fleet': 'Van Sales Fleet Link',
        'Van Fleet': 'Van Sales Fleet Link',
        'Driver': 'Van Sales Driver Link',
        'Van Driver': 'Van Sales Driver Link',
        'Van Session': 'Van Sales Sessions Link',
        'Van Sessions': 'Van Sales Sessions Link',
        'Van Items': 'Van Sales Items Link',
        'Van Warehouses': 'Van Sales Warehouses Link',
        'Van Sales Reports': 'Van Sales Reports Link',
        'BOM Stock Report': 'Manufacturing Reports',
        'Work Order Stock Report': 'Manufacturing Reports',
        'Open Work Orders': 'Manufacturing Reports',
        'Work Orders in Progress': 'Manufacturing Reports',
        'Completed Work Orders': 'Manufacturing Reports',
        'Work Order Summary': 'Manufacturing Reports',
        'Job Card Summary': 'Manufacturing Reports',
        'Production Analytics': 'Manufacturing Reports',
        'Operations': 'Manufacturing Setup',
        'Workstations': 'Manufacturing Setup',
        'Routing': 'Manufacturing Setup',
        'BOM Creator': 'Manufacturing Setup',
        'Manufacturing Settings': 'Manufacturing Setup'
    });
    const WORKSPACE_ROUTE_NAMES = Object.freeze({
        'Home': 'Business Home',
        'Manufacturing Reports': 'Manufacturing Reports',
        'Manufacturing Setup': 'Manufacturing Setup'
    });
    const WORKSPACE_DISPLAY_LABELS = Object.freeze(frappe.boot?.retail_sidebar_labels || {});
    const ROLE_SIDEBAR_WORKSPACES = Object.freeze({
        'Van Sales User': ['Van Sales'],
        'Van Sales Manager': ['Van Sales'],
        'Sales User': ['Sales'],
        'Sales Manager': ['Sales'],
        'Sales Master Manager': ['Sales'],
        'Item Manager': ['Items'],
        'Retail Price Manager': ['Items'],
        'Stock User': ['Stocks'],
        'Stock Manager': ['Stocks'],
        'Purchase User': ['Purchases'],
        'Purchase Manager': ['Purchases'],
        'Purchase Master Manager': ['Purchases'],
        'Accounts User': ['Accounts'],
        'Accounts Manager': ['Accounts'],
        'POS User': ['POS'],
        'POS Manager': ['POS'],
        'POS Integration User': ['POS'],
        'Manufacturing User': ['Manufacturing'],
        'Manufacturing Manager': ['Manufacturing'],
        'Report Manager': ['Reports'],
        'Analytics': ['Reports'],
        'Fleet Manager': ['Van Sales']
    });
    const TOP_LEVEL_WORKSPACES = new Set([
        'Promotions',
        'Business Home',
        'Items',
        'Sales',
        'POS',
        'Purchases',
        'Stocks',
        'Manufacturing',
        'Van Sales',
        'Accounts',
        'Reports',
        'Settings'
    ]);
    const ALWAYS_VISIBLE_WORKSPACES = new Set(['Business Home']);
    const HIDDEN_SIDEBAR_LABELS = new Set([
        'Sales Stock View',
        'Stock View'
    ]);
    const WORKSPACE_TO_MODULE = Object.freeze({
        'Business Home': '',
        'Items': 'Stock',
        'Items List': 'Stock',
        'Item Family List': 'Stock',
        'Item Groups': 'Stock',
        'Price Lists': 'Stock',
        'Brands': 'Stock',
        'Stocks': 'Stock',
        'Warehouses': 'Stock',
        'Stock Adjustments': 'Stock',
        'Stock Take': 'Stock',
        'Serials & Batches': 'Stock',
        'Stock Status': 'Stock',
        'Delivery Notes': 'Stock',
        'Purchase Receipts': 'Stock',
        'Material Requests': 'Stock',
        'Sales': 'Selling',
        'Customers': 'Selling',
        'Quotations': 'Selling',
        'Sales Orders': 'Selling',
        'Sales Invoices': 'Selling',
        'Sales Returns': 'Selling',
        'POS': 'Accounts',
        'POS Invoices': 'Accounts',
        'POS Profile': 'Accounts',
        'POS Profiles': 'Accounts',
        'POS Counters': 'Accounts',
        'POS Opening Entry': 'Accounts',
        'POS Opening Entries': 'Accounts',
        'POS Closing Entry': 'Accounts',
        'POS Closing Entries': 'Accounts',
        'POS Cashier Shifts': 'Accounts',
        'POS Counter Sessions': 'Accounts',
        'POS Branch Day Closing': 'Accounts',
        'POS Branch Day Closings': 'Accounts',
        'POS Sync Log': 'Accounts',
        'POS Sync Logs': 'Accounts',
        'Mode of Payment': 'Accounts',
        'POS Reports': 'Accounts',
        'POS Sales Summary': 'Accounts',
        'POS Transaction Log': 'Accounts',
        'POS Item-wise Sales': 'Accounts',
        'POS Category/Item Group Sales': 'Accounts',
        'POS Category Item Group Sales': 'Accounts',
        'POS Hourly Sales': 'Accounts',
        'POS Return Report': 'Accounts',
        'Cashier Wise Sales': 'Accounts',
        'Counter Wise Sales': 'Accounts',
        'Shift Closing Variance': 'Accounts',
        'Payment Mode Summary': 'Accounts',
        'POS Discount Report': 'Accounts',
        'POS Price Override Report': 'Accounts',
        'POS Daily Closing Summary': 'Accounts',
        'POS Cash Movement Report': 'Accounts',
        'Purchases': 'Buying',
        'Suppliers': 'Buying',
        'Request for Quotations': 'Buying',
        'Supplier Quotations': 'Buying',
        'Purchase Orders': 'Buying',
        'Purchase Invoices': 'Accounts',
        'Purchase Returns': 'Accounts',
        'Manufacturing': 'Manufacturing',
        'BOM': 'Manufacturing',
        'Production Plan': 'Manufacturing',
        'Work Orders': 'Manufacturing',
        'Job Cards': 'Manufacturing',
        'Stock Entries': 'Manufacturing',
        'Quality Inspection': 'Manufacturing',
        'Manufacturing Reports': 'Manufacturing',
        'Manufacturing Setup': 'Manufacturing',
        'Accounts': 'Accounts',
        'Bank Accounts': 'Accounts',
        'Payments': 'Accounts',
        'Taxes': 'Accounts',
        'Journal Entries': 'Accounts',
        'Accounts Receivable': 'Accounts',
        'Accounts Payable': 'Accounts',
        'Reports': 'Accounts',
        'Settings': 'Setup',
        'Business Profile': 'Setup',
        'Branding': 'Setup',
        'System Rules': 'Setup',
        'User List': 'Setup',
        'Employee List': 'HR',
        'Van Sales': '',
        'Van Fleet': '',
        'Van Driver': '',
        'Van Sessions': '',
        'Stock Request': '',
        'Van Stock Request': '',
        'Van Stock Entries': '',
        'Van Stock View': '',
        'Van Sales Invoice': '',
        'Van Payments': '',
        'Van Customers': '',
        'Van Items': '',
        'Van Warehouses': '',
        'Van Sales Fleet Link': '',
        'Van Sales Driver Link': '',
        'Van Sales Sessions Link': '',
        'Van Sales Stock Entries Link': '',
        'Van Sales Stock View Link': '',
        'Van Sales Invoice Link': '',
        'Van Sales Payments Link': '',
        'Van Sales Customers Link': '',
        'Van Sales Items Link': '',
        'Van Sales Warehouses Link': '',
        'Van Sales Reports': '',
        'Van Sales Reports Link': ''
    });
    const REPORT_TO_WORKSPACE = Object.freeze({
        'Daily Sales Summary': 'Sales',
        'Counter Performance': 'Sales',
        'Daily Transaction Log': 'Sales',
        'Daily Profit Report': 'Sales',
        'Gross Profit': 'Sales',
        'Low Stock Reorder Report': 'Stocks',
        'Stock Movement Summary': 'Stocks',
        'Stock Adjustment History': 'Stocks',
        'Stock Balance': 'Stocks',
        'Stock Ledger': 'Stocks',
        'Packing Stock Balance': 'Stocks',
        'Packing Stock Ledger': 'Stocks',
        'Fast Moving Items': 'Items',
        'Slow Moving Items': 'Items',
        'Accounts Receivable': 'Accounts',
        'Accounts Payable': 'Accounts',
        'General Ledger': 'Accounts',
        'Trial Balance': 'Accounts',
        'Balance Sheet': 'Accounts',
        'Profit and Loss Statement': 'Accounts',
        'POS Sales Summary': 'POS Reports',
        'POS Transaction Log': 'POS Reports',
        'POS Item-wise Sales': 'POS Reports',
        'POS Category Item Group Sales': 'POS Reports',
        'POS Category/Item Group Sales': 'POS Reports',
        'POS Hourly Sales': 'POS Reports',
        'POS Return Report': 'POS Reports',
        'Cashier Wise Sales': 'POS Reports',
        'Counter Wise Sales': 'POS Reports',
        'Shift Closing Variance': 'POS Reports',
        'POS Payment Mode Summary': 'POS Reports',
        'Payment Mode Summary': 'POS Reports',
        'POS Discount Report': 'POS Reports',
        'POS Price Override Report': 'POS Reports',
        'POS Daily Closing Summary': 'POS Reports',
        'POS Cash Movement Report': 'POS Reports',
        'BOM Stock Report': 'Manufacturing',
        'Work Order Stock Report': 'Manufacturing',
        'Open Work Orders': 'Manufacturing',
        'Work Orders in Progress': 'Manufacturing',
        'Completed Work Orders': 'Manufacturing',
        'Work Order Summary': 'Manufacturing',
        'Job Card Summary': 'Manufacturing',
        'Production Analytics': 'Manufacturing'
        , 'Van Daily Sales Summary': 'Van Sales Reports'
        , 'Van Daily Stock Summary': 'Van Sales Reports'
        , 'Van Detailed Sales Summary': 'Van Sales Reports'
        , 'Van Profit Report': 'Van Sales Reports'
        , 'Van Wastage Report': 'Van Sales Reports'
        , 'Van Outstanding Collection Summary': 'Van Sales Reports'
    });
    const VAN_PAGE_TO_CHILD = Object.freeze({
        'retail-van-sales-invoice': 'Van Sales Invoice',
        'van-payments': 'Van Payments',
        'van-stock-request': 'Stock Request',
        'van-stock-entries': 'Van Stock Entries',
        'van-stock-view': 'Van Stock View',
        'van-customers': 'Van Customers'
    });
    const VAN_PAGE_ROUTES = new Set(Object.keys(VAN_PAGE_TO_CHILD));
    const REQUIRED_VAN_SALES_CHILDREN = Object.freeze([
        {
            name: 'Stock Request',
            title: 'Stock Request',
            parent_page: 'Van Sales',
            icon: 'list',
            public: 1,
            is_hidden: 0
        },
        {
            name: 'Van Sales Stock View Link',
            title: 'Van Stock View',
            parent_page: 'Van Sales',
            icon: 'stock',
            public: 1,
            is_hidden: 0,
            insert_after: ['Van Stock Entries', 'Stock Request', 'Van Sessions']
        }
    ]);
    let sidebarItemsPromise = null;
    let sidebarItemsCache = null;
    let observerRefreshTimer = null;
    let routeRefreshTimer = null;
    let sidebarRenderRetryCount = 0;
    let sidebarRenderRetryTimer = null;
    let useBootSidebarItems = true;
    let sidebarItemsGeneration = 0;
    let workspaceCustomCardsPatched = false;
    let workspaceSidebarRoutesPatched = false;
    const dynamicSidebarItems = new Map();
    const manuallyClosedSidebarGroups = new Set();
    let lastSidebarStateRouteKey = null;
    let openWorkClearedRouteKey = null;

    function redirectStandardHomeToBusinessHome() {
        if (Array.isArray(frappe.boot?.retail_sidebar_selection) && !workspaceIsAllowed('Business Home')) return false;
        const route = frappe.get_route?.() || [];
        const routeName = route[0] === 'private' ? route[1] : route[0];
        if (frappe.router.slug(routeName || '') !== 'home') return false;

        const target = getWorkspaceUrl('Business Home', true).replace(/^\/app\//, '');
        if (route.join('/') === target) return false;

        frappe.set_route(target);
        return true;
    }

    function bindNavbarHomeToBusinessHome() {
        if (Array.isArray(frappe.boot?.retail_sidebar_selection) && !workspaceIsAllowed('Business Home')) return;
        const businessHomeUrl = getWorkspaceUrl('Business Home', true);
        const businessHomeRoute = businessHomeUrl.replace(/^\/app\//, '');

        document.querySelectorAll('.navbar .navbar-home').forEach((link) => {
            if (link.tagName === 'A') {
                link.setAttribute('href', businessHomeUrl);
            }
        });

        if (!window.__retail_business_home_navbar_bound) {
            window.__retail_business_home_navbar_bound = true;
            document.addEventListener('click', (event) => {
                const homeLink = event.target?.closest?.('.navbar .navbar-home');
                if (!homeLink) return;

                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation?.();
                frappe.set_route(businessHomeRoute);
            }, true);
        }

        if (!window.jQuery) return;

        $(document)
            .off('click.retailBusinessHome', '.navbar .navbar-home')
            .on('click.retailBusinessHome', '.navbar .navbar-home', (event) => {
                event.preventDefault();
                event.stopPropagation();
                frappe.set_route(businessHomeRoute);
                return false;
            });
    }

    function normalizeText(text) {
        return (text || '')
            .toString()
            .trim()
            .toLowerCase()
            .replace(/\s+/g, ' ');
    }

    function getBlockedModules() {
        return new Set(frappe.boot?.retail_blocked_modules || []);
    }

    function moduleIsAllowed(moduleName) {
        if (frappe.boot?.retail_module_access?.[moduleName] === false) return false;
        return !moduleName || !getBlockedModules().has(moduleName);
    }

    function getWorkspaceModule(workspaceName) {
        if (!workspaceName) return '';
        return WORKSPACE_TO_MODULE[workspaceName] || frappe.boot?.retail_workspace_modules?.[workspaceName] || '';
    }

    function getCurrentUserRoles() {
        return frappe.user_roles || frappe.boot?.user?.roles || [];
    }

    function getRoleAllowedSidebarWorkspaces() {
        if (frappe.session?.user === 'Administrator') return null;
        const roles = getCurrentUserRoles();
        if (roles.includes('System Manager')) return null;

        const bootAllowed = frappe.boot?.retail_allowed_sidebar_workspaces;
        if (Array.isArray(bootAllowed)) return new Set(bootAllowed);

        const allowed = new Set();
        roles.forEach(role => {
            (ROLE_SIDEBAR_WORKSPACES[role] || []).forEach(workspace => allowed.add(workspace));
        });
        ALWAYS_VISIBLE_WORKSPACES.forEach(workspace => allowed.add(workspace));
        return allowed;
    }

    function getSidebarGroup(workspaceName) {
        if (!workspaceName) return '';
        if (dynamicSidebarItems.get(workspaceName)?.sidebar_group) {
            return dynamicSidebarItems.get(workspaceName).sidebar_group;
        }
        const bootGroups = frappe.boot?.retail_workspace_sidebar_groups || {};
        if (bootGroups[workspaceName]) return bootGroups[workspaceName];

        let current = workspaceName;
        const seen = new Set();
        while (current && !seen.has(current)) {
            seen.add(current);
            if (TOP_LEVEL_WORKSPACES.has(current)) return current;
            current = CHILD_TO_PARENT[current];
        }

        return workspaceName;
    }

    function sidebarWorkspaceIsAllowed(...names) {
        if (names.filter(Boolean).some(name => ALWAYS_VISIBLE_WORKSPACES.has(name))) return true;
        const allowed = getRoleAllowedSidebarWorkspaces();
        if (allowed === null) return true;
        return names.filter(Boolean).some(name => allowed.has(getSidebarGroup(name)));
    }

    function workspaceIsAllowed(workspaceName) {
        const selection = frappe.boot?.retail_sidebar_selection;
        if (Array.isArray(selection)) {
            const entries = (frappe.boot.retail_sidebar_registry || []).flatMap(group => [group, ...group.children]);
            const entry = entries.find(entry => entry.workspace === workspaceName || entry.workspace === WORKSPACE_DISPLAY_LABELS[workspaceName]);
            if (entry && !selection.includes(entry.id)) return false;

        }
        if (workspaceName && !sidebarWorkspaceIsAllowed(workspaceName)) return false;

        let current = workspaceName;
        const seen = new Set();

        while (current && !seen.has(current)) {
            seen.add(current);
            if (!moduleIsAllowed(getWorkspaceModule(current))) return false;
            current = CHILD_TO_PARENT[current];
        }

        return true;
    }

    function checklistTargetIsAllowed(kind, target) {
        const selection = frappe.boot?.retail_sidebar_selection;
        if (!Array.isArray(selection)) return true;
        const entries = (frappe.boot.retail_sidebar_registry || []).flatMap(group => [group, ...group.children]);
        const candidates = entries.filter(entry => (entry.targets || []).some(pair => pair[0] === kind && pair[1] === target));
        return !candidates.length || candidates.some(entry => selection.includes(entry.id));
    }

    function doctypeIsAllowed(doctype) {
        if (!doctype) return true;
        if (!checklistTargetIsAllowed('doctype', doctype)) return false;
        let canRead = true;
        const bootCanRead = frappe.boot?.user?.can_read;
        if (Array.isArray(bootCanRead)) {
            canRead = bootCanRead.includes(doctype);
        } else if (frappe.model?.can_read) {
            canRead = frappe.model.can_read(doctype);
        }
        if (!canRead) return false;
        if (Array.isArray(frappe.boot?.retail_sidebar_selection)) return true;

        // Driver is a standard ERPNext doctype. Its Van Sales mapping only
        // controls sidebar placement, never document routes or search access.
        if (doctype === 'Driver') return true;

        const workspace = DOCTYPE_TO_CHILD[doctype] || DOCTYPE_TO_WORKSPACE[doctype];
        return workspace ? workspaceIsAllowed(workspace) : true;
    }

    function pageIsAllowed(pageName) {
        if (!pageName) return true;
        if (!checklistTargetIsAllowed('page', pageName)) return false;
        if (['point-of-sale', 'pos'].includes(pageName) && !moduleIsAllowed('POS')) return false;
        if ((pageName.startsWith('van-') || pageName === 'retail-van-sales-invoice') && !moduleIsAllowed('Van Sales')) return false;
        const allowedPages = frappe.boot?.allowed_pages;
        return !Array.isArray(allowedPages) || !allowedPages.length || allowedPages.includes(pageName);
    }

    function reportIsAllowed(reportName, report) {
        if (!checklistTargetIsAllowed('report', reportName)) return false;
        if ((reportName?.startsWith('POS ') || ['Cashier Wise Sales', 'Counter Wise Sales', 'Shift Closing Variance', 'Item Group Sales Analysis'].includes(reportName)) && !moduleIsAllowed('POS')) return false;
        if (reportName?.startsWith('Van ') && !moduleIsAllowed('Van Sales')) return false;
        if (workspaceIsAllowed('Reports') &&
            frappe.boot?.retail_allowed_workspace_reports?.includes(reportName)) return true;
        if (!reportName) return true;
        const reports = frappe.boot?.user?.all_reports;
        if (reports && !reports[reportName]) return false;
        if (Array.isArray(frappe.boot?.retail_sidebar_selection)) return true;

        const workspace = REPORT_TO_WORKSPACE[reportName];
        if (workspace) return workspaceIsAllowed(workspace);
        return doctypeIsAllowed(report?.ref_doctype);
    }

    function routeIsAllowed(route) {
        if (!Array.isArray(route) || !route.length) return true;
        const view = route[0];
        if (VAN_PAGE_TO_CHILD[view]) {
            return workspaceIsAllowed('Van Sales') && (pageIsAllowed(view) || VAN_PAGE_ROUTES.has(view));
        }
        if (view === 'List' || view === 'Form' || view === 'Tree') {
            return doctypeIsAllowed(route[1]);
        }
        if (view === 'query-report') {
            return reportIsAllowed(route[1], frappe.boot?.user?.all_reports?.[route[1]]);
        }
        if (view === 'Workspaces' || view === 'workspace' || view === 'private') {
            const workspaceName = view === 'private' ? route[1] : route[1];
            return workspaceIsAllowed(routeNameToWorkspaceTitle(workspaceName));
        }
        if (typeof view === 'string') {
            return pageIsAllowed(view);
        }
        return true;
    }

    function getSidebarTarget(item) {
        const title = item?.title || item?.name || '';
        const displayTitle = WORKSPACE_DISPLAY_LABELS[item?.name] || title;
        return (
            item?.route ||
            dynamicSidebarItems.get(item?.name || title)?.route ||
            DIRECT_MAPPING[title] ||
            DIRECT_MAPPING[item?.name] ||
            DIRECT_MAPPING[displayTitle]
        );
    }

    function workspaceHasAllowedChildren(workspaceName) {
        if (!workspaceName) return false;
        if (Array.from(dynamicSidebarItems.values()).some(item => (
            item.parent_page === workspaceName && sidebarItemIsAllowed(item)
        ))) return true;
        return Object.entries(CHILD_TO_PARENT).some(([child, parent]) => {
            if (parent !== workspaceName) return false;
            if (!sidebarWorkspaceIsAllowed(child)) return false;
            if (!workspaceIsAllowed(child)) return false;

            const childTarget = getSidebarTarget({ name: child, title: child });
            if (childTarget) return routeIsAllowed(childTarget);
            return workspaceHasAllowedChildren(child);
        });
    }

    function sidebarItemIsAllowed(item) {
        const title = item?.title || item?.name || '';
        if (Array.isArray(frappe.boot?.retail_sidebar_selection)) {
            const entries = (frappe.boot.retail_sidebar_registry || []).flatMap(group => [group, ...group.children]);
            const entry = entries.find(entry => entry.workspace === item?.name || entry.workspace === title || entry.workspace === WORKSPACE_DISPLAY_LABELS[item?.name]);
            if (entry && !frappe.boot.retail_sidebar_selection.includes(entry.id)) return false;

        }
        const target = getSidebarTarget(item);
        const reportItem = dynamicSidebarItems.get(item?.name || title);
        if (reportItem) {
            if (reportItem.is_report_link) {
                const reportRoute = reportItem.route || target;
                const reportName = Array.isArray(reportRoute) && reportRoute[0] === 'query-report'
                    ? reportRoute[1]
                    : reportItem.link_to || title;
                return workspaceIsAllowed('Reports') && reportIsAllowed(reportName, reportItem);
            }

            return workspaceIsAllowed('Reports') && workspaceHasAllowedChildren(reportItem.name);
        }

        if (ALWAYS_VISIBLE_WORKSPACES.has(item?.name) || ALWAYS_VISIBLE_WORKSPACES.has(title)) return true;
        if (!sidebarWorkspaceIsAllowed(item?.name, title)) return false;
        if (!workspaceIsAllowed(title) || !workspaceIsAllowed(item?.name)) return false;
        if (item?.is_workspace_link || (item?.name || title) === 'Reports') return true;
        if (target) return routeIsAllowed(target);
        return workspaceHasAllowedChildren(item?.name || title);
    }

    function registerSidebarItems(items) {
        (items || []).forEach(item => {
            if (item.is_report_link || item.is_report_group) {
                dynamicSidebarItems.set(item.name || item.title, item);
            }
        });
        return items;
    }

    function optionIsAllowed(option) {
        if (!option) return true;
        if (option.match && typeof option.match === 'string') {
            if (DOCTYPE_TO_CHILD[option.match] || DOCTYPE_TO_WORKSPACE[option.match]) {
                return doctypeIsAllowed(option.match);
            }
            if (WORKSPACE_TO_MODULE[option.match]) {
                return workspaceIsAllowed(option.match);
            }
        }
        return routeIsAllowed(option.route);
    }

    function routeNameToWorkspaceTitle(routeName) {
        const decoded = decodeURIComponent(String(routeName || '')).replace(/-/g, ' ');
        const normalized = normalizeText(decoded);
        const known = Object.keys(WORKSPACE_TO_MODULE).find(name => normalizeText(name) === normalized);
        return known || decoded.replace(/\b\w/g, char => char.toUpperCase());
    }

    function filterSearchResults(results) {
        if (!Array.isArray(results)) return results;
        return results.filter(optionIsAllowed);
    }

    function filterGlobalResultSets(resultSets) {
        if (!Array.isArray(resultSets)) return resultSets;
        return resultSets
            .map(set => Object.assign({}, set, { results: filterSearchResults(set.results || []) }))
            .filter(set => doctypeIsAllowed(set.title) && set.results.length);
    }

    function installModuleAwareSearchFilters() {
        const utils = frappe.search?.utils;
        if (!utils || utils.__retail_module_filters_installed) return !!utils;

        [
            'get_recent_pages',
            'get_frequent_links',
            'get_search_in_list',
            'get_creatables',
            'get_doctypes',
            'get_reports',
            'get_pages',
            'get_workspaces',
            'get_dashboards',
            'get_executables'
        ].forEach(methodName => {
            const original = utils[methodName];
            if (typeof original !== 'function') return;
            utils[methodName] = function (...args) {
                return filterSearchResults(original.apply(this, args));
            };
        });

        const originalGetGlobalResults = utils.get_global_results;
        if (typeof originalGetGlobalResults === 'function') {
            utils.get_global_results = function (...args) {
                return originalGetGlobalResults.apply(this, args).then(filterGlobalResultSets);
            };
        }

        utils.__retail_module_filters_installed = true;
        return true;
    }

    function waitForSearchFilters() {
        if (installModuleAwareSearchFilters()) return;
        let attempts = 0;
        const timer = setInterval(() => {
            attempts += 1;
            if (installModuleAwareSearchFilters() || attempts >= 40) clearInterval(timer);
        }, 250);
    }

    function enforceAllowedRoute() {
        if (routeIsAllowed(frappe.get_route?.() || [])) return false;
        frappe.show_alert({
            message: __('You do not have permission to access this module.'),
            indicator: 'orange'
        });
        if (Array.isArray(frappe.boot?.retail_sidebar_selection)) {
            const permitted = (frappe.boot.allowed_workspaces || []).find(item => item.route || DIRECT_MAPPING[item.name]);
            const target = permitted && (permitted.route || DIRECT_MAPPING[permitted.name]);
            if (target) frappe.set_route(target);
            // With no permitted menus, retain the native permission screen.
        } else {
            frappe.set_route(getWorkspaceUrl('Business Home', true).replace(/^\/app\//, ''));
        }
        return true;
    }

    function findIconConfig(labelText) {
        const displayLabel = WORKSPACE_DISPLAY_LABELS[labelText] || labelText;
        const name = normalizeText(displayLabel);
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

    function isMobile() {
        return !isDesktop();
    }

    function isWorkspaceRoute(route) {
        const view = route?.[0]?.toLowerCase();
        const routeSlug = frappe.router.slug(
            route?.[0] === 'private' ? route?.[1] || '' : route?.[0] || ''
        );
        const currentPage = getCurrentPage();
        return (
            view === 'workspaces' ||
            view === 'workspace' ||
            !!(routeSlug && frappe.workspaces?.[routeSlug]) ||
            currentPage?.dataset?.pageRoute === 'Workspaces'
        );
    }

    function isItemFamilyPageRoute(route = frappe.get_route()) {
        return Array.isArray(route) && route[0] === 'retail-item-family-l';
    }

    function suppressCustomDocumentCards() {
        const workspacePrototype = frappe.views?.Workspace?.prototype;
        if (!workspacePrototype || workspaceCustomCardsPatched) return !!workspacePrototype;

        const addCustomCards = workspacePrototype.add_custom_cards_in_content;
        if (typeof addCustomCards !== "function") return false;

        workspacePrototype.add_custom_cards_in_content = function () {
            addCustomCards.call(this);
            this.content = (this.content || []).filter(
                (block) => !(block.type === "card" && block.data?.card_name === "Custom Documents")
            );
        };
        workspaceCustomCardsPatched = true;
        return true;
    }

    function patchWorkspaceSidebarRoutes() {
        const workspacePrototype = frappe.views?.Workspace?.prototype;
        if (!workspacePrototype) return false;
        if (workspaceSidebarRoutesPatched) return true;
        const renderItem = workspacePrototype.sidebar_item_container;
        const getPages = workspacePrototype.get_pages;
        if (typeof renderItem !== 'function' || typeof getPages !== 'function') return false;

        workspacePrototype.get_pages = function (...args) {
            return Promise.resolve(getPages.apply(this, args)).then(result => {
                registerSidebarItems(result?.pages || []);
                return result;
            });
        };
        workspacePrototype.sidebar_item_container = function (item) {
            registerSidebarItems([item]);
            const $container = renderItem.call(this, item);
            const container = $container.get(0);
            container.setAttribute('item-workspace-name', item.name || item.title);
            if (item.is_report_group) container.dataset.retailReportGroup = '1';
            if (item.is_report_link) container.dataset.retailReportLink = '1';
            const target = getSidebarTarget(item);
            const anchor = container.querySelector(':scope > .desk-sidebar-item > .item-anchor');
            if (item.is_report_group) {
                configureReportGroupAnchor(anchor);
            } else if (anchor && target) {
                anchor.setAttribute('href', getTargetUrl(target));
                setAnchorRouteTarget(anchor, target);
            }
            return $container;
        };
        workspaceSidebarRoutesPatched = true;
        return true;
    }

    function waitForWorkspaceModule() {
        if (suppressCustomDocumentCards() && patchWorkspaceSidebarRoutes()) return;

        let attempts = 0;
        const timer = setInterval(() => {
            attempts += 1;
            const ready = suppressCustomDocumentCards() && patchWorkspaceSidebarRoutes();
            if (ready || attempts >= 40) clearInterval(timer);
        }, 250);
    }

    function isReturnFilter(value) {
        return value === true || value === 1 || value === '1' || value === 'true';
    }

    function getRouteParts(route) {
        return (route || []).filter(part => !$.isPlainObject(part));
    }

    function getTargetRouteParts(target) {
        return getRouteParts(target);
    }

    function getTargetFilters(target) {
        return target?.find(part => $.isPlainObject(part)) || {};
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

    function normalizeFilterValue(value) {
        if (value === true) return '1';
        if (value === false) return '0';
        if (value === undefined || value === null) return '';
        return String(value);
    }

    function routePartsMatch(currentParts, targetParts) {
        if (!currentParts.length || currentParts.length < targetParts.length) return false;
        return targetParts.every((part, index) => currentParts[index] === part);
    }

    function targetFiltersMatch(currentFilters, targetFilters) {
        return Object.entries(targetFilters).every(([field, value]) => (
            normalizeFilterValue(currentFilters[field]) === normalizeFilterValue(value)
        ));
    }

    const SIDEBAR_CONTEXT_KEY = 'retail_sidebar_context_v1';

    function getStoredSidebarChild(matches, visibleLabels) {
        let stored = null;
        try {
            stored = JSON.parse(sessionStorage.getItem(SIDEBAR_CONTEXT_KEY) || 'null');
        } catch (e) {
            stored = null;
        }

        const child = stored?.child;
        if (!child || !visibleLabels.has(child)) return null;

        const matchLabels = new Set(matches.map(([label]) => label));
        const aliasMatches = matches.some(([label]) => ROUTE_ALIAS_TO_CHILD[label] === child);
        return matchLabels.has(child) || aliasMatches ? child : null;
    }

    function rememberSidebarContext(label) {
        const child = ROUTE_ALIAS_TO_CHILD[label] || (getParentLabel(label) ? label : null);
        const main = child ? getTopParentLabel(child) : (TOP_LEVEL_WORKSPACES.has(label) ? label : null);
        if (!main) return;

        try {
            sessionStorage.setItem(SIDEBAR_CONTEXT_KEY, JSON.stringify({ main, child, ts: Date.now() }));
        } catch (e) {
            // Ignore private-mode storage errors; normal route matching still works.
        }
    }

    function getMappedChildFromRoute(route, filters) {
        const currentParts = getRouteParts(route);
        const visibleLabels = getVisibleSidebarLabels();
        const matches = Object.entries(DIRECT_MAPPING)
            .sort((a, b) => Object.keys(getTargetFilters(b[1])).length - Object.keys(getTargetFilters(a[1])).length)
            .filter(([, target]) => (
                routePartsMatch(currentParts, getTargetRouteParts(target))
                && targetFiltersMatch(filters, getTargetFilters(target))
            ));

        const storedChild = getStoredSidebarChild(matches, visibleLabels);
        if (storedChild) return storedChild;

        const visibleMatch = matches.find(([label]) => visibleLabels.has(label))?.[0];
        if (visibleMatch) return visibleMatch;

        const aliasMatch = matches
            .map(([label]) => ROUTE_ALIAS_TO_CHILD[label])
            .find(child => child && visibleLabels.has(child));
        if (aliasMatch) return aliasMatch;

        return matches[0] ? ROUTE_ALIAS_TO_CHILD[matches[0][0]] || matches[0][0] : null;
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

    function clearListFilter(doctype, fieldname) {
        if (window.cur_list?.doctype !== doctype) return false;

        const filterArea = window.cur_list.filter_area;
        if (!filterArea?.get().some(filter => filter[1] === fieldname)) return false;

        // FilterArea owns standard controls and the nested FilterList.
        // get_filter/update_filters belong to FilterList, not FilterArea.
        filterArea.remove(fieldname);
        return true;
    }

    function resetSalesInvoiceListFilters() {
        return [
            window.cur_list?.retail_reset_invoice_source?.(),
            clearListFilter("Sales Invoice", "is_return"),
            clearListFilter("Sales Invoice", "custom_is_van_sale")
        ].some(Boolean);
    }

    function clearSalesInvoiceListState(keepFields = []) {
        const blockedFields = new Set(["is_return", "custom_is_van_sale"]);
        keepFields.forEach(field => blockedFields.delete(field));

        frappe.route_options = null;

        if (window.cur_list?.doctype === "Sales Invoice") {
            let changed = Boolean(window.cur_list.retail_reset_invoice_source?.());
            blockedFields.forEach(field => {
                changed = clearListFilter("Sales Invoice", field) || changed;
            });

            if (Array.isArray(window.cur_list.filters)) {
                const nextFilters = window.cur_list.filters.filter(filter => !blockedFields.has(filter?.[1]));
                changed = changed || nextFilters.length !== window.cur_list.filters.length;
                window.cur_list.filters = nextFilters;
            }

            return changed;
        }

        return false;
    }

    function normalizeSalesInvoiceListRoute(route, filters) {
        if (route[0] !== "List" || route[1] !== "Sales Invoice") return null;

        const hasFilters = filters && Object.keys(filters).length;
        if (hasFilters) {
            clearSalesInvoiceListState();
            return getTargetUrl(targetWithFilters(route, filters));
        }

        clearSalesInvoiceListState();
        return getTargetUrl(route);
    }

    function targetWithFilters(route, filters) {
        return filters && Object.keys(filters).length ? [...route, filters] : [...route];
    }

    function isVanSalesInvoiceWrapperRoute() {
        return Array.isArray(frappe.get_route()) && frappe.get_route()[0] === "retail-van-sales-invoice";
    }

    function routeToTarget(target) {
        const route = target.filter(part => !$.isPlainObject(part));
        const filters = target.find(part => $.isPlainObject(part));

        const salesInvoiceUrl = normalizeSalesInvoiceListRoute(route, filters);
        if (salesInvoiceUrl) {
            if (isVanSalesInvoiceWrapperRoute()) {
                window.location.href = salesInvoiceUrl;
                return Promise.resolve();
            }
            return routeToUrl(salesInvoiceUrl).then(() => {
                const changed = !filters || !Object.keys(filters).length
                    ? clearSalesInvoiceListState()
                    : clearSalesInvoiceListState(Object.keys(filters));
                if (changed && window.cur_list?.doctype === "Sales Invoice") {
                    return window.cur_list.refresh();
                }
            });
        }

        // A route option alone keeps the same URL as an unfiltered list. When
        // moving from Sales Invoices to Sales Returns, Frappe can therefore
        // reuse the already-rendered list and ignore the new filter. Put list
        // filters in the URL so this is always a distinct, reloadable route.
        if (filters && Object.keys(filters).length) {
            return routeToUrl(getTargetUrl(target));
        }

        if (route[0] === 'van-stock-view' || route[0] === 'van-stock-request') {
            return routeToUrl(`/app/${route[0]}`);
        }

        // Sales Invoices is the normal, non-return, non-van list. Remove
        // filters left by Sales Returns or Van Sales Invoice wrappers.
        const resetInvoiceFilters = route[0] === "List" && route[1] === "Sales Invoice"
            ? resetSalesInvoiceListFilters()
            : false;
        frappe.route_options = filters || null;
        return frappe.set_route(...route).then(() => {
            if (resetInvoiceFilters && window.cur_list?.doctype === "Sales Invoice") {
                return window.cur_list.refresh();
            }
        });
    }

    function bindViewWebsiteToRetailHome() {
        const websiteUrl = '/retail-home';

        if (window.frappe?.ui?.toolbar) {
            frappe.ui.toolbar.view_website = function () {
                const websiteTab = window.open();
                if (!websiteTab) {
                    window.location.href = websiteUrl;
                    return;
                }
                websiteTab.opener = null;
                websiteTab.location = websiteUrl;
            };
        }

        if (!window.__retail_view_website_bound) {
            window.__retail_view_website_bound = true;
            document.addEventListener('click', (event) => {
                const item = event.target?.closest?.('.dropdown-menu a, .dropdown-menu button');
                if (!item || normalizeText(item.textContent) !== 'view website') return;

                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation?.();
                const websiteTab = window.open(websiteUrl);
                if (websiteTab) {
                    websiteTab.opener = null;
                } else {
                    window.location.href = websiteUrl;
                }
            }, true);
        }

        document.querySelectorAll('.dropdown-menu a, .dropdown-menu button').forEach((item) => {
            if (normalizeText(item.textContent) !== 'view website') return;
            if (item.dataset.retailViewWebsiteBound === '1') return;
            item.dataset.retailViewWebsiteBound = '1';
            if (item.tagName === 'A') {
                item.setAttribute('href', websiteUrl);
            }
            item.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                const websiteTab = window.open(websiteUrl);
                if (websiteTab) {
                    websiteTab.opener = null;
                } else {
                    window.location.href = websiteUrl;
                }
            }, { capture: true });
        });
    }

    function getAnchorRouteTarget(anchor) {
        const routeTarget = anchor?.dataset?.retailRouteTarget;
        if (!routeTarget) return null;

        try {
            return JSON.parse(routeTarget);
        } catch (e) {
            return null;
        }
    }

    function setAnchorRouteTarget(anchor, target) {
        if (!anchor || !target) return;
        anchor.dataset.retailRouteTarget = JSON.stringify(target);
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

    function getTargetFromUrl(anchor) {
        const appUrl = getAnchorAppUrl(anchor);
        if (!appUrl) return null;

        const path = appUrl.split(/[?#]/)[0].replace(/\/+$/, '');
        const purchaseInvoiceWorkspaceUrls = new Set([
            '/app/purchase-invoice',
            '/app/purchase-invoices',
            '/app/purchase-bills'
        ]);

        if (purchaseInvoiceWorkspaceUrls.has(path)) {
            return DIRECT_MAPPING['Purchase Invoices'];
        }

        return null;
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

    function getWorkspaceUrl(workspaceName, isPublic = true) {
        const legacyName = workspaceName?.replace(/ Desk$/, '');
        if (TOP_LEVEL_WORKSPACES.has(legacyName)) workspaceName = legacyName;
        const slug = frappe.router.slug(workspaceName);
        return `/app/${isPublic ? slug : `private/${slug}`}`;
    }

    function isVisibleElement(element) {
        if (!element) return false;
        const style = window.getComputedStyle(element);
        return style.display !== 'none' && style.visibility !== 'hidden' && element.offsetParent !== null;
    }

    function unwrapElement(value) {
        if (!value) return null;
        if (value instanceof Element) return value;
        if (value.jquery) return value.get(0);
        if (value.wrapper instanceof Element) return value.wrapper;
        if (value.page instanceof Element) return value.page;
        return null;
    }

    function getVisiblePageContainers() {
        return Array.from(document.querySelectorAll('.page-container')).filter(isVisibleElement);
    }

    function getCurrentPage() {
        const frappePage = unwrapElement(frappe.container?.page);
        if (isVisibleElement(frappePage)) return frappePage;

        const visiblePages = getVisiblePageContainers();
        return visiblePages[visiblePages.length - 1] || document.querySelector('.page-container[style*="display: block"]');
    }

    function getCurrentSideSection() {
        const pageSideSection = getCurrentPage()?.querySelector('.layout-side-section');
        // New forms hide their document sidebar. Still mount navigation on the
        // active page, rather than borrowing a sidebar from a cached page.
        if (pageSideSection) return pageSideSection;

        const visibleSideSections = Array.from(document.querySelectorAll('.layout-side-section'))
            .filter(isVisibleElement);
        return visibleSideSections[visibleSideSections.length - 1] || pageSideSection;
    }

    function getRetailSidebarContainers() {
        return document.querySelectorAll('.retail-persistent-sidebar .sidebar-item-container');
    }

    function getSelectableSidebarContainers() {
        return document.querySelectorAll(
            '.retail-persistent-sidebar .sidebar-item-container, .desk-sidebar .sidebar-item-container'
        );
    }

    function getItemLabel(container) {
        return container
            ?.querySelector(':scope > .desk-sidebar-item > .item-anchor .sidebar-item-label')
            ?.innerText
            ?.trim();
    }

    function getSidebarRoutingLabel(container) {
        const label = getItemLabel(container);
        const workspaceName = container?.getAttribute('item-workspace-name');
        if (
            workspaceName
            && (dynamicSidebarItems.has(workspaceName) || CHILD_TO_PARENT[workspaceName] || DIRECT_MAPPING[workspaceName] || WORKSPACE_TO_MODULE[workspaceName])
        ) {
            return workspaceName;
        }
        return label;
    }

    function getParentLabel(label) {
        return dynamicSidebarItems.get(label)?.parent_page || CHILD_TO_PARENT[label] || '';
    }

    function getTopParentLabel(label) {
        let current = label;
        const seen = new Set();
        while (getParentLabel(current) && !seen.has(current)) {
            seen.add(current);
            current = getParentLabel(current);
        }
        return current;
    }

    function isDescendantOf(label, ancestor) {
        let current = label;
        const seen = new Set();
        while (getParentLabel(current) && !seen.has(current)) {
            seen.add(current);
            current = getParentLabel(current);
            if (current === ancestor) return true;
        }
        return false;
    }

    function getSidebarIconLabel(container) {
        const workspaceName = container?.getAttribute('item-workspace-name');
        if (workspaceName === 'Manufacturing Reports') return 'Manufacturing Child Reports';
        if (workspaceName === 'Manufacturing Setup') return 'Manufacturing Child Setup';
        return getItemLabel(container);
    }

    function getVisibleSidebarLabels() {
        const labels = new Set();
        Array.from(getSelectableSidebarContainers()).forEach(container => {
            const label = getItemLabel(container);
            const routingLabel = getSidebarRoutingLabel(container);
            if (label) labels.add(label);
            if (routingLabel) labels.add(routingLabel);
        });
        return labels;
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
        const filters = getRouteFilters(route);
        const workspaceRoute = (view === 'workspaces' || view === 'workspace')
            ? route[route[1] === 'private' ? 2 : 1]
            : route?.[0];
        const mainWorkspace = Array.from(TOP_LEVEL_WORKSPACES).find(name =>
            frappe.router.slug(name) === frappe.router.slug(workspaceRoute || '')
        );
        if (mainWorkspace) return { main: mainWorkspace, child: '' };

        if (VAN_PAGE_TO_CHILD[route?.[0]]) {
            return { main: 'Van Sales', child: VAN_PAGE_TO_CHILD[route[0]] };
        }

        const pageTitle = document.querySelector(".page-title .title-text, .title-text")?.innerText?.trim();
        if (pageTitle === "Van Sales Invoice") {
            return { main: "Van Sales", child: "Van Sales Invoice" };
        }

        const reportItems = view === 'query-report'
            ? Array.from(dynamicSidebarItems.values()).filter(item => item.is_report_link && item.route?.[1] === route[1])
            : [];
        let storedChild;
        try {
            storedChild = JSON.parse(sessionStorage.getItem(SIDEBAR_CONTEXT_KEY) || 'null')?.child;
        } catch (error) { /* Ignore unavailable sidebar history. */ }
        const selectedReport = reportItems.find(item => item.name === storedChild);
        if (selectedReport) return { main: 'Reports', child: selectedReport.name };

        const mappedChild = getMappedChildFromRoute(route, filters);

        if (isItemFamilyPageRoute(route)) {
            return { main: 'Items', child: 'Item Family List' };
        }

        if (mappedChild) {
            return { main: getTopParentLabel(mappedChild) || DOCTYPE_TO_WORKSPACE[route?.[1]], child: mappedChild };
        }

        if (reportItems.length) return { main: 'Reports', child: reportItems[0].name };

        if (view === 'workspaces' || view === 'workspace') {
            const title = decodeURIComponent(route[route[1] === 'private' ? 2 : 1] || '');
            if (CHILD_TO_PARENT[title]) {
                return { main: CHILD_TO_PARENT[title], child: title };
            }
            return { main: title, child: '' };
        }

        const workspaceSlug = frappe.router.slug(
            route?.[0] === 'private' ? route?.[1] || '' : route?.[0] || ''
        );
        const workspaceTitle = frappe.workspaces?.[workspaceSlug]?.title;
        if (workspaceTitle) {
            if (CHILD_TO_PARENT[workspaceTitle]) {
                return { main: CHILD_TO_PARENT[workspaceTitle], child: workspaceTitle };
            }
            return { main: workspaceTitle, child: '' };
        }

        if (view === 'list' || view === 'form') {
            const doctype = route[1];
            let child = DOCTYPE_TO_CHILD[doctype];

            if (doctype === 'Sales Invoice' && isReturnFilter(filters.is_return)) {
                child = 'Sales Returns';
            } else if (doctype === 'Purchase Receipt' && isReturnFilter(filters.is_return)) {
                child = 'Purchase Returns';
            }

            return { main: DOCTYPE_TO_WORKSPACE[doctype], child };
        }

        return {};
    }

    // Ensure our CSS is loaded at runtime in case app_include_css wasn't picked up
    function ensureRetailCss() {
        const fontHref = '/assets/frappe/css/fonts/fontawesome/font-awesome.min.css';
        if (!document.querySelector(`link[href="${fontHref}"]`)) {
            const fontLink = document.createElement('link');
            fontLink.rel = 'stylesheet';
            fontLink.href = fontHref;
            document.head.appendChild(fontLink);
        }
        const href = '/assets/retail/css/retail_icons.css?v=32';
        if (document.querySelector('link[href^="/assets/retail/css/retail_icons.css"]')) return;
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = href;
        link.type = 'text/css';
        link.onload = () => debugLog('retail_navigation: retail_icons.css loaded');
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
            .color-hr { color: #8b5cf6 !important; }
            .color-hr-recruitment { color: #ec4899 !important; }
            .color-hr-lifecycle { color: #06b6d4 !important; }
            .color-hr-performance { color: #f59e0b !important; }
            .color-hr-attendance { color: #3b82f6 !important; }
            .color-hr-expenses { color: #ef4444 !important; }
            .color-hr-leaves { color: #10b981 !important; }
            .color-pos-profiles { color: #8b5cf6 !important; }
            .color-pos-invoices { color: #0ea5e9 !important; }
            .color-pos-counters { color: #f97316 !important; }
            .color-pos-cashier-shifts { color: #14b8a6 !important; }
            .color-pos-counter-sessions { color: #2563eb !important; }
            .color-pos-opening { color: #10b981 !important; }
            .color-pos-closing { color: #ef4444 !important; }
            .color-pos-day-closing { color: #f59e0b !important; }
            .color-pos-sync { color: #64748b !important; }
            .color-pos-reports { color: #ec4899 !important; }

            .sidebar-item-label { display: inline-block !important; vertical-align: middle !important; }

            html[data-retail-brand-theme] .container,
            html[data-retail-brand-theme] .container-sm,
            html[data-retail-brand-theme] .container-md,
            html[data-retail-brand-theme] .container-lg,
            html[data-retail-brand-theme] .container-xl,
            body.retail-wide-desk .main-section,
            body.retail-wide-desk #body,
            body.retail-wide-desk .content,
            body.retail-wide-desk .navbar > .container,
            body.retail-wide-desk .page-head,
            body.retail-wide-desk .page-head .container,
            body.retail-wide-desk .page-container,
            body.retail-wide-desk .page-content,
            body.retail-wide-desk .page-wrapper,
            body.retail-wide-desk .layout-main,
            body.retail-wide-desk .page-body,
            body.retail-wide-desk .container,
            body.retail-wide-desk .layout-main-section-wrapper,
            body.retail-wide-desk .layout-main-section,
            body.retail-wide-desk .std-form-layout,
            body.retail-wide-desk .form-layout,
            body.retail-wide-desk .form-page {
                max-width: none !important;
                width: 100% !important;
            }

            body.retail-wide-desk .layout-main,
            body.retail-wide-desk .layout-main-section-wrapper {
                padding-left: 12px !important;
                padding-right: 12px !important;
            }

            body:has(.modal.show)[data-route^="Form/"] .form-grid,
            body:has(.modal.show)[data-route^="Form/"] .grid-body,
            body:has(.modal.show)[data-route^="Form/"] .rows,
            body:has(.modal.show)[data-route^="Form/"] .grid-row,
            body:has(.modal.show)[data-route^="Form/"] .data-row,
            body:has(.modal.show)[data-route^="Form/"] .grid-static-col,
            body:has(.modal.show)[data-route^="Form/"] .field-area {
                z-index: auto !important;
            }

            .retail-open-work {
                position: fixed;
                right: 10px;
                top: 112px;
                width: 48px;
                max-height: calc(100vh - 132px);
                background: rgba(255, 255, 255, 0.95);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
                display: flex;
                flex-direction: column;
                height: calc(100vh - 132px);
                overflow: hidden;
                pointer-events: auto;
                transition: width 160ms ease;
                z-index: 2000;
            }

            .retail-open-work:hover,
            .retail-open-work:focus-within {
                width: 248px;
            }

            .retail-open-work__head {
                align-items: center;
                display: grid;
                gap: 8px;
                grid-template-columns: 28px 1fr 28px;
                min-height: 42px;
                padding: 8px 10px;
                border-bottom: 1px solid var(--border-color);
                font-weight: 600;
                white-space: nowrap;
            }

            .retail-open-work__count {
                align-items: center;
                background: var(--blue-50);
                border-radius: 999px;
                color: var(--blue-700);
                display: inline-flex;
                font-size: 12px;
                height: 22px;
                justify-content: center;
                min-width: 22px;
            }

            .retail-open-work__title {
                opacity: 0;
                transition: opacity 120ms ease;
            }

            .retail-open-work:hover .retail-open-work__title,
            .retail-open-work:focus-within .retail-open-work__title {
                opacity: 1;
            }

            .retail-open-work__clear {
                align-items: center;
                background: transparent;
                border: 0;
                border-radius: 6px;
                color: var(--text-muted);
                cursor: pointer;
                display: inline-flex;
                font-size: 16px;
                height: 28px;
                justify-content: center;
                opacity: 0;
                width: 28px;
            }

            .retail-open-work:hover .retail-open-work__clear,
            .retail-open-work:focus-within .retail-open-work__clear {
                opacity: 1;
            }

            .retail-open-work__clear:hover,
            .retail-open-work__close:hover {
                background: var(--control-bg);
                color: var(--text-color);
            }

            .retail-open-work__list {
                display: block;
                flex: 1 1 auto;
                height: 100%;
                max-height: none;
                min-height: 0;
                overscroll-behavior: contain;
                overflow-y: scroll;
                overflow-x: hidden;
                padding: 6px;
                scrollbar-width: thin;
                -webkit-overflow-scrolling: touch;
            }

            .retail-open-work__item {
                align-items: center;
                background: transparent;
                border: 0;
                border-radius: 6px;
                color: var(--text-color);
                cursor: pointer;
                display: grid;
                gap: 8px;
                grid-template-columns: 28px 10px 1fr 24px;
                min-height: 36px;
                padding: 4px;
                text-align: left;
                text-decoration: none;
                width: 100%;
            }

            .retail-open-work__item + .retail-open-work__item {
                margin-top: 4px;
            }

            .retail-open-work__item:hover,
            .retail-open-work__item.is-active {
                background: var(--control-bg);
            }

            .retail-open-work__abbr {
                align-items: center;
                background: var(--gray-100);
                border-radius: 6px;
                color: var(--text-muted);
                display: inline-flex;
                font-size: 11px;
                font-weight: 700;
                height: 28px;
                justify-content: center;
                width: 28px;
            }

            .retail-open-work__item.is-active .retail-open-work__abbr {
                background: var(--blue-100);
                color: var(--blue-700);
            }

            .retail-open-work__status-dot {
                align-self: center;
                border-radius: 50%;
                display: inline-block;
                height: 8px;
                opacity: 0.95;
                width: 8px;
            }

            .retail-open-work__status-dot.is-not-saved {
                background: #ef4444;
            }

            .retail-open-work__status-dot.is-saved {
                background: #f97316;
            }

            .retail-open-work__status-dot.is-final {
                background: #22c55e;
            }

            .retail-open-work__status-dot.is-page {
                background: #94a3b8;
            }

            .retail-open-work__label {
                min-width: 0;
                opacity: 0;
                overflow: hidden;
                text-overflow: ellipsis;
                transition: opacity 120ms ease;
                white-space: nowrap;
            }

            .retail-open-work:hover .retail-open-work__label,
            .retail-open-work:focus-within .retail-open-work__label {
                opacity: 1;
            }

            .retail-open-work__close {
                align-items: center;
                background: transparent;
                border: 0;
                border-radius: 6px;
                color: var(--text-muted);
                cursor: pointer;
                display: inline-flex;
                height: 24px;
                justify-content: center;
                opacity: 0;
                width: 24px;
            }

            .retail-open-work:hover .retail-open-work__close,
            .retail-open-work:focus-within .retail-open-work__close {
                opacity: 1;
            }

            .retail-open-work__status {
                border-top: 1px solid var(--border-color);
                color: var(--text-muted);
                font-size: 11px;
                opacity: 0;
                overflow: hidden;
                padding: 6px 10px;
                text-overflow: ellipsis;
                transition: opacity 120ms ease;
                white-space: nowrap;
            }

            .retail-open-work:hover .retail-open-work__status,
            .retail-open-work:focus-within .retail-open-work__status {
                opacity: 1;
            }
        }

        @media (max-width: 991px) {
            .retail-open-work { display: none !important; }
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
            debugLog('retail_navigation: no sidebar containers found');
            return;
        }

        debugLog('retail_navigation: sidebar containers found', containers.length);

        containers.forEach(container => {
            const labelEl = container.querySelector(':scope > .desk-sidebar-item > .item-anchor .sidebar-item-label');
            const iconContainer = container.querySelector(':scope > .desk-sidebar-item > .item-anchor .sidebar-item-icon');
            const labelText = normalizeText(getSidebarIconLabel(container) || labelEl?.innerText);
            const config = findIconConfig(labelText);
            if (!config) return;

            debugLog('retail_navigation: matched item', labelText, config.icon, config.cls);

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

    function applyDisplayLabels() {
        document.querySelectorAll('.sidebar-item-container').forEach(container => {
            const workspaceName = container.getAttribute('item-workspace-name');
            const labelEl = container.querySelector(':scope > .desk-sidebar-item > .item-anchor .sidebar-item-label');
            const rawLabel = labelEl?.innerText?.trim();
            const displayLabel = WORKSPACE_DISPLAY_LABELS[workspaceName] || WORKSPACE_DISPLAY_LABELS[rawLabel];
            if (!displayLabel) return;
            if (!labelEl || labelEl.innerText.trim() === displayLabel) return;

            labelEl.innerText = __(displayLabel);
            const anchor = container.querySelector(':scope > .desk-sidebar-item > .item-anchor');
            anchor?.setAttribute("title", __(displayLabel));
        });
    }

    function hideStandardHomeSidebarItems() {
        document.querySelectorAll('.sidebar-item-container').forEach(container => {
            const label = getItemLabel(container);
            const workspaceName = container.getAttribute('item-workspace-name') || label;
            if (HIDDEN_SIDEBAR_LABELS.has(label) || HIDDEN_SIDEBAR_LABELS.has(workspaceName)) {
                container.classList.add('hidden');
                container.style.display = 'none';
                return;
            }
            if (workspaceName === 'Business Home' || label === 'Business Home') return;
            if (label !== 'Home' && workspaceName !== 'Home') return;

            container.classList.add('hidden');
            container.style.display = 'none';
        });
    }

    function hideUnauthorizedSidebarItems() {
        if (getRoleAllowedSidebarWorkspaces() === null) return;

        document.querySelectorAll('.sidebar-item-container').forEach(container => {
            const label = getItemLabel(container);
            const workspaceName = container.getAttribute('item-workspace-name');
            if (HIDDEN_SIDEBAR_LABELS.has(label) || HIDDEN_SIDEBAR_LABELS.has(workspaceName)) {
                container.classList.add('hidden');
                container.style.display = 'none';
                return;
            }
            const allowed = sidebarItemIsAllowed({
                name: workspaceName || label,
                title: workspaceName || label
            });

            container.classList.toggle('hidden', !allowed);
            container.style.display = allowed ? '' : 'none';
        });
    }

    function setDropIcon(container, open) {
        const use = container
            ?.querySelector(':scope > .desk-sidebar-item .drop-icon use');
        if (use) use.setAttribute('href', open ? '#es-small-down' : '#es-small-right');
        container?.querySelector(':scope > .desk-sidebar-item .drop-icon')
            ?.setAttribute('aria-expanded', String(!!open));
        container?.querySelector(':scope > .desk-sidebar-item > .item-anchor[data-retail-report-group]')
            ?.setAttribute('aria-expanded', String(!!open));
    }

    function getSmallDropIcon(open) {
        return `<svg class="es-icon retail-small-chevron" aria-hidden="true">
            <use href="${open ? '#es-small-down' : '#es-small-right'}"></use>
        </svg>`;
    }

    function setSidebarExpanded(container, open) {
        const section = container?.querySelector(':scope > .sidebar-child-item');
        if (!section) return;
        section.classList.toggle('hidden', !open);
        if (open) {
            section.querySelectorAll(':scope > .sidebar-item-container').forEach(child => {
                if (!sidebarItemIsAllowed({ name: getWorkspaceName(child), title: getItemLabel(child) })) return;
                child.classList.remove('hidden');
                child.style.removeProperty('display');
            });
        }
        setDropIcon(container, open);
    }

    function getVanForcedChildLabel() {
        const path = window.location.pathname.replace(/\/+$/, "");
        const title = document.querySelector(".page-title .title-text, .title-text")?.innerText?.trim();
        const route = frappe.get_route();
        const routeMap = {
            "List:Van Fleet": "Van Sales Fleet Link",
            "List:Driver": "Van Sales Driver Link",
            "List:Van Session": "Van Sales Sessions Link",
            "List:Item": "Van Sales Items Link",
            "List:Warehouse": "Van Sales Warehouses Link",
            "query-report:Van Daily Sales Summary": "Van Sales Reports Link",
            "query-report:Van Daily Stock Summary": "Van Sales Reports Link",
            "query-report:Van Detailed Sales Summary": "Van Sales Reports Link",
            "query-report:Van Profit Report": "Van Sales Reports Link",
            "query-report:Van Wastage Report": "Van Sales Reports Link",
            "query-report:Van Outstanding Collection Summary": "Van Sales Reports Link",
        };
        const pageTitleMap = {
            "Van Fleet": "Van Sales Fleet Link",
            "Driver": "Van Sales Driver Link",
            "Van Session": "Van Sales Sessions Link",
            "Van Sessions": "Van Sales Sessions Link",
            "Van Sales Invoice": "Van Sales Invoice",
            "Van Payment": "Van Payments",
            "Van Payments": "Van Payments",
            "Stock Request": "Stock Request",
            "Van Stock Entries": "Van Stock Entries",
            "Van Stock View": "Van Stock View",
            "Van Customers": "Van Customers",
            "Item": "Van Sales Items Link",
            "Item List": "Van Sales Items Link",
            "Warehouse": "Van Sales Warehouses Link",
            "Warehouse List": "Van Sales Warehouses Link",
            "Van Sales Reports": "Van Sales Reports Link",
        };
        const pathMap = {
            "/app/retail-van-sales-invoice": "Van Sales Invoice",
            "/app/van-payments": "Van Payments",
            "/app/van-stock-request": "Stock Request",
            "/app/van-stock-entries": "Van Stock Entries",
            "/app/van-stock-view": "Van Stock View",
            "/app/van-customers": "Van Customers",
        };
        return routeMap[`${route?.[0]}:${route?.[1]}`] || pathMap[path] || pageTitleMap[title] || "";
    }

    function getContainerDisplayLabel(container) {
        const label = getItemLabel(container);
        const workspaceName = container?.getAttribute("item-workspace-name");
        return WORKSPACE_DISPLAY_LABELS[workspaceName] || WORKSPACE_DISPLAY_LABELS[label] || label;
    }

    function forceVanSidebarSelection() {
        const state = getRouteState();
        if (state.main && state.main !== 'Van Sales') return;
        const forcedChild = getVanForcedChildLabel();
        if (!forcedChild) return;

        getSelectableSidebarContainers().forEach(container => {
            const displayLabel = getContainerDisplayLabel(container);
            const routingLabel = getSidebarRoutingLabel(container);
            const directItem = container.querySelector(':scope > .desk-sidebar-item');
            const childSection = container.querySelector(':scope > .sidebar-child-item');
            const isVanMain = displayLabel === "Van Sales";
            const isVanChild = CHILD_TO_PARENT[routingLabel] === "Van Sales" || CHILD_TO_PARENT[displayLabel] === "Van Sales";
            const isForcedChild = displayLabel === forcedChild || routingLabel === forcedChild;

            if (isVanMain && childSection && !manuallyClosedSidebarGroups.has('Van Sales')) {
                childSection.classList.remove("hidden");
                setDropIcon(container, true);
            }

            if (!isVanMain && !isVanChild) return;

            container.classList.toggle("retail-primary-active", isVanMain);
            container.classList.toggle("retail-secondary-active", isForcedChild);
            directItem?.classList.toggle("selected", isVanMain || isForcedChild);
        });
    }

    function syncSidebarState() {
        const state = getRouteState();
        const routeKey = (frappe.get_route() || []).join('/');
        if (routeKey !== lastSidebarStateRouteKey) {
            manuallyClosedSidebarGroups.clear();
            lastSidebarStateRouteKey = routeKey;
        }
        const userOpenGroups = readOpenSidebarGroups();

        getSelectableSidebarContainers().forEach(container => {
            const label = getItemLabel(container);
            const routingLabel = getSidebarRoutingLabel(container);
            const displayRoutingLabel = WORKSPACE_DISPLAY_LABELS[routingLabel] || routingLabel;
            const directItem = container.querySelector(':scope > .desk-sidebar-item');
            const childSection = container.querySelector(':scope > .sidebar-child-item');
            const isMain = label && state.main === label;
            const isChild = (
                (routingLabel && state.child === routingLabel)
                || (displayRoutingLabel && state.child === displayRoutingLabel)
                || (label && state.child === label)
            );
            const displayMatchKey = Object.keys(WORKSPACE_DISPLAY_LABELS).find(
                key => WORKSPACE_DISPLAY_LABELS[key] === state.child
            );
            const stateChild = getParentLabel(state.child) ? state.child : displayMatchKey;
            const isAncestor = !!(routingLabel && stateChild && isDescendantOf(stateChild, routingLabel));
            const wasOpenedByUser = userOpenGroups.has(routingLabel) || userOpenGroups.has(label);
            const wasClosedByUser = manuallyClosedSidebarGroups.has(routingLabel) || manuallyClosedSidebarGroups.has(label);
            const shouldOpen = !wasClosedByUser && (isMain || wasOpenedByUser || isAncestor);

            container.classList.toggle('retail-primary-active', !!isMain);
            container.classList.toggle('retail-secondary-active', !!isChild);
            container.classList.toggle('retail-ancestor-active', isAncestor && !isMain);
            directItem?.classList.toggle('selected', !!(isMain || isChild));

            if (childSection) {
                setSidebarExpanded(container, !!shouldOpen);
            }
        });
    }

    function ensureWorkspaceDropIcons() {
        if (!isWorkspaceRoute(frappe.get_route())) return;

        getCurrentPage()
            ?.querySelectorAll('.desk-sidebar:not(.retail-persistent-sidebar) .sidebar-item-container')
            .forEach(container => {
                const childSection = container.querySelector(':scope > .sidebar-child-item');
                const control = container.querySelector(':scope > .desk-sidebar-item > .sidebar-item-control');
                if (!childSection || !control || !childSection.children.length) return;

                let button = control.querySelector(':scope > .retail-drop-icon');
                if (!button) {
                    button = document.createElement('button');
                    button.className = 'btn-reset drop-icon retail-drop-icon';
                    button.type = 'button';
                    button.innerHTML = getSmallDropIcon(!childSection.classList.contains('hidden'));
                    control.querySelectorAll(':scope > .drop-icon').forEach(icon => icon.remove());
                    control.appendChild(button);
                }

                button.classList.remove('hidden');
                setDropIcon(container, !childSection.classList.contains('hidden'));
            });
    }

    function syncDesktopSidebarClass() {
        const hasSidebar = isDesktop() && !!document.querySelector('.layout-side-section .retail-persistent-sidebar');
        document.body.classList.toggle('retail-has-persistent-sidebar', hasSidebar);
    }

    function isWideDeskRoute(route = frappe.get_route()) {
        if (!isDesktop() || !Array.isArray(route) || route.length === 0) {
            return false;
        }

        return !["Form", "query-report"].includes(route[0]);
    }

    function applyWideTransactionLayout() {
        const enabled = isWideDeskRoute();
        document.body.classList.toggle('retail-wide-transaction-form', enabled);
        document.body.classList.toggle('retail-wide-desk', enabled);

        const selectors = [
            '.main-section',
            '#body',
            '.content',
            '.navbar > .container',
            '.container-sm',
            '.container-md',
            '.container-lg',
            '.container-xl',
            '.page-head',
            '.page-head .container',
            '.page-container',
            '.page-content',
            '.page-wrapper',
            '.layout-main',
            '.page-body',
            '.container',
            '.layout-main-section-wrapper',
            '.layout-main-section',
            '.std-form-layout',
            '.form-layout',
            '.form-page',
        ];

        selectors.forEach(selector => {
            document.querySelectorAll(selector).forEach(element => {
                if (enabled) {
                    element.style.setProperty('max-width', 'none', 'important');
                    element.style.setProperty('width', '100%', 'important');
                } else {
                    element.style.removeProperty('max-width');
                    element.style.removeProperty('width');
                }
            });
        });

        document.querySelectorAll('.layout-main-section-wrapper').forEach(element => {
            if (enabled) {
                element.style.setProperty('padding-left', '12px', 'important');
                element.style.setProperty('padding-right', '12px', 'important');
            } else {
                element.style.removeProperty('padding-left');
                element.style.removeProperty('padding-right');
            }
        });
    }

    function readOpenWorkTabs() {
        try {
            const tabs = JSON.parse(sessionStorage.getItem(OPEN_WORK_STORAGE_KEY) || '[]');
            const cutoff = Date.now() - OPEN_WORK_TTL_MS;
            const validTabs = Array.isArray(tabs)
                ? tabs.filter(tab => tab?.key && Array.isArray(tab.route) && (tab.updated_at || 0) >= cutoff)
                : [];
            const seen = new Set();
            return validTabs.filter(tab => {
                if (seen.has(tab.key)) return false;
                seen.add(tab.key);
                return true;
            });
        } catch (error) {
            return [];
        }
    }

    function writeOpenWorkTabs(tabs) {
        sessionStorage.setItem(OPEN_WORK_STORAGE_KEY, JSON.stringify(tabs));
    }

    function getCurrentWorkTab() {
        const route = frappe.get_route();
        if (!Array.isArray(route) || !route.length) return null;
        const view = route[0];
        if (isItemFamilyPageRoute(route)) {
            return {
                key: route.join('/'),
                route: route.filter(part => typeof part !== 'object'),
                label: 'Item Family List',
                type: 'Item Family List',
                status: 'page',
                updated_at: Date.now(),
            };
        }
        if (!['Form', 'List', 'query-report'].includes(view)) return null;

        const doctype = route[1] || view;
        const name = route[2] || '';
        const doc = view === 'Form' ? cur_frm?.doc : null;
        const routeParts = route.filter(part => typeof part !== 'object');
        const key = doc?.__islocal ? `Form/${doctype}/__new__` : routeParts.join('/');
        const title = doc?.__islocal
            ? `New ${doctype}`
            : (doc?.title || doc?.supplier_name || doc?.customer_name || doc?.item_name || name || doctype);

        return {
            key,
            route: routeParts,
            label: view === 'List' ? doctype : title,
            type: doctype,
            status: getCurrentWorkStatus(view, doc),
            updated_at: Date.now(),
        };
    }

    function getCurrentWorkStatus(view, doc) {
        if (view !== 'Form' || !doc) return 'page';
        if (cur_frm?.is_dirty?.()) return 'not_saved';
        if (doc.docstatus === 1) return 'final';
        if (doc.docstatus === 0) return 'saved';
        return 'page';
    }

    function getWorkStatusClass(status) {
        return {
            not_saved: 'is-not-saved',
            saved: 'is-saved',
            final: 'is-final',
            page: 'is-page',
        }[status] || 'is-page';
    }

    function getWorkStatusLabel(status) {
        return {
            not_saved: __('Not saved'),
            saved: __('Saved'),
            final: __('Final'),
            page: __('Page'),
        }[status] || __('Page');
    }

    function upsertCurrentWorkTab() {
        const tab = getCurrentWorkTab();
        if (!tab) return;
        if (openWorkClearedRouteKey === tab.key) return;
        openWorkClearedRouteKey = null;

        const tabs = readOpenWorkTabs();
        const existingIndex = tabs.findIndex(existing => existing.key === tab.key);
        if (existingIndex >= 0) {
            tabs[existingIndex] = { ...tabs[existingIndex], ...tab };
        } else {
            tabs.unshift(tab);
        }
        writeOpenWorkTabs(tabs);
        renderOpenWorkTabs();
    }

    function closeOpenWorkTab(key) {
        const currentKey = getCurrentWorkTab()?.key;
        if (key === currentKey) {
            openWorkClearedRouteKey = key;
        }
        writeOpenWorkTabs(readOpenWorkTabs().filter(tab => tab.key !== key));
        renderOpenWorkTabs();
    }

    function closeAllOpenWorkTabs() {
        openWorkClearedRouteKey = getCurrentWorkTab()?.key || null;
        sessionStorage.removeItem(OPEN_WORK_STORAGE_KEY);
        renderOpenWorkTabs();
    }

    function openWorkTab(tab) {
        if (!tab?.route?.length) return;

        try {
            frappe.route_options = null;
            frappe.route_hash = null;
            frappe.set_route(...tab.route);
        } catch (error) {
            window.location.href = getOpenWorkHref(tab.route);
        }
    }

    function getOpenWorkHref(route) {
        try {
            return frappe.router.make_url(frappe.router.convert_from_standard_route(route));
        } catch (error) {
            return `/app/${route.map(part => encodeURIComponent(String(part))).join('/')}`;
        }
    }

    function getWorkAbbr(tab) {
        const source = tab.type || tab.label || '';
        return source
            .split(/\s+/)
            .filter(Boolean)
            .slice(0, 2)
            .map(word => word[0])
            .join('')
            .toUpperCase() || 'W';
    }

    function escapeAttribute(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function ensureOpenWorkPanel() {
        if (!isDesktop()) return null;
        let panel = document.querySelector('.retail-open-work');
        if (panel) return panel;

        panel = document.createElement('aside');
        panel.className = 'retail-open-work';
        panel.setAttribute('aria-label', __('Open Work'));
        document.body.appendChild(panel);
        return panel;
    }

    function handleOpenWorkPointer(event) {
        const clearButton = event.target.closest('.retail-open-work__clear');
        if (clearButton) {
            if (!clearButton.closest('.retail-open-work')) return;
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation?.();
            closeAllOpenWorkTabs();
            return;
        }

        const closeButton = event.target.closest('.retail-open-work__close');
        if (closeButton) {
            if (!closeButton.closest('.retail-open-work')) return;
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation?.();
            closeOpenWorkTab(closeButton.dataset.key);
            return;
        }

        const item = event.target.closest('.retail-open-work__item');
        if (!item || !item.closest('.retail-open-work')) return;

        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation?.();
        const tab = readOpenWorkTabs().find(entry => entry.key === item.dataset.key);
        openWorkTab(tab);
    }

    function bindOpenWorkEvents() {
        if (window.__retailOpenWorkEventsBound) return;
        window.__retailOpenWorkEventsBound = true;
        document.addEventListener('pointerdown', handleOpenWorkPointer, true);
    }

    function renderOpenWorkTabs() {
        const tabs = readOpenWorkTabs();
        if (!tabs.length) {
            document.querySelector('.retail-open-work')?.remove();
            return;
        }

        const panel = ensureOpenWorkPanel();
        if (!panel) return;

        const currentKey = getCurrentWorkTab()?.key;
        const status = panel.dataset.status || __('Recent Tabs');
        panel.innerHTML = `
            <div class="retail-open-work__head">
                <span class="retail-open-work__count">${tabs.length}</span>
                <span class="retail-open-work__title">${__('Open Work')}</span>
                <button class="retail-open-work__clear" type="button" title="${__('Close All')}" aria-label="${__('Close All')}">x</button>
            </div>
            <div class="retail-open-work__list">
                ${tabs.map(tab => `
                    <a class="retail-open-work__item ${tab.key === currentKey ? 'is-active' : ''}"
                        href="${escapeAttribute(getOpenWorkHref(tab.route))}"
                        data-key="${escapeAttribute(tab.key)}" title="${escapeAttribute(tab.label)}">
                        <span class="retail-open-work__abbr">${escapeHtml(getWorkAbbr(tab))}</span>
                        <span class="retail-open-work__status-dot ${getWorkStatusClass(tab.status)}"
                            title="${escapeAttribute(getWorkStatusLabel(tab.status))}"></span>
                        <span class="retail-open-work__label">${escapeHtml(tab.label)}</span>
                        <span class="retail-open-work__close" data-key="${escapeAttribute(tab.key)}" title="${__('Close')}">×</span>
                    </a>
                `).join('')}
            </div>
            <div class="retail-open-work__status">${escapeHtml(status)}</div>
        `;
    }

    function removePersistentSidebar() {
        document.querySelectorAll('.retail-sidebar-overlay').forEach(sidebar => sidebar.remove());
        document.querySelectorAll('.retail-persistent-sidebar').forEach(sidebar => sidebar.remove());
        syncDesktopSidebarClass();
    }

    function getRetailSidebarHost(sideSection) {
        let host = sideSection.querySelector(':scope > .retail-sidebar-host');
        if (!host) {
            host = document.createElement('div');
            host.className = 'retail-sidebar-host';
            sideSection.prepend(host);
        }
        return host;
    }

    function getWorkspaceName(container) {
        const label = getItemLabel(container);
        return container?.getAttribute('item-workspace-name') || container?.getAttribute('item-name') || WORKSPACE_ROUTE_NAMES[label] || label;
    }

    function readOpenSidebarGroups() {
        try {
            const groups = JSON.parse(sessionStorage.getItem(OPEN_SIDEBAR_STORAGE_KEY) || '[]');
            return new Set(Array.isArray(groups) ? groups.filter(Boolean) : []);
        } catch (error) {
            return new Set();
        }
    }

    function writeOpenSidebarGroups(groups) {
        sessionStorage.setItem(OPEN_SIDEBAR_STORAGE_KEY, JSON.stringify(Array.from(groups)));
    }

    function rememberOpenSidebarGroup(label, open = true) {
        if (!label) return;
        const groups = readOpenSidebarGroups();
        if (open) {
            groups.add(label);
            manuallyClosedSidebarGroups.delete(label);
        } else {
            groups.delete(label);
            manuallyClosedSidebarGroups.add(label);
        }
        writeOpenSidebarGroups(groups);
    }

    function getSidebarMountSections() {
        const currentSideSection = getCurrentSideSection();
        if (!currentSideSection) return [];
        const overlay = currentSideSection.querySelector('.overlay-sidebar:not(.retail-sidebar-overlay)');
        return [isMobile() && overlay ? overlay : currentSideSection];
    }

    function buildPersistentSidebar(items) {
        registerSidebarItems(items);
        const seen = new Set();
        const visibleItems = items.filter(item => {
            const itemTitle = item.title || item.name;
            const key = `${item.parent_page || ''}:${itemTitle}`;
            if (seen.has(key)) return false;
            seen.add(key);
            return (
                !item.is_hidden &&
                !['Home'].includes(itemTitle) &&
                !HIDDEN_SIDEBAR_LABELS.has(itemTitle) &&
                !HIDDEN_SIDEBAR_LABELS.has(item.name) &&
                sidebarItemIsAllowed(item)
            );
        });
        const publicItems = visibleItems.filter(item => item.public);
        const roots = publicItems.filter(item => !item.parent_page);
        const wrapper = document.createElement('div');
        wrapper.className = 'retail-persistent-sidebar standard-sidebar-section nested-container';
        wrapper.dataset.title = 'CELESTA';

        roots.forEach(item => wrapper.appendChild(buildSidebarItem(item, publicItems)));
        return wrapper;
    }

    function mountPersistentSidebar(section, items) {
        if (!section) return;
        const host = getRetailSidebarHost(section);
        const sideSection = section.closest('.layout-side-section') || section;
        const sidebars = Array.from(sideSection.querySelectorAll('.retail-persistent-sidebar'));
        const sidebar = sidebars.shift();
        sidebars.forEach(duplicate => duplicate.remove());
        if (sidebar) {
            if (sidebar.parentElement !== host) host.prepend(sidebar);
        } else {
            host.prepend(buildPersistentSidebar(items));
        }
        if (isDesktop() && frappe.get_route()?.[1] === 'POS Operator Privilege') {
            sideSection.classList.remove('hide-sidebar');
            sideSection.style.removeProperty('display');
        }
        const route = frappe.get_route();
        sideSection.classList.toggle('retail-form-navigation', route?.[0] === 'Form');
        if (isDesktop() && route?.[0] === 'Form') {
            // Frappe hides the document sidebar on unsaved forms, but this
            // section also contains Retail's persistent menu and selection.
            // Keep desktop navigation visible when form metadata is hidden.
            sideSection.classList.remove('hide-sidebar');
            sideSection.style.removeProperty('display');
        }
        section.classList.add('retail-form-sidebar-mounted');
        section.classList.toggle('retail-mobile-sidebar-mounted', section.classList.contains('overlay-sidebar'));
    }

    function configureReportGroupAnchor(anchor) {
        if (!anchor) return;
        anchor.removeAttribute('href');
        anchor.removeAttribute('data-retail-route-target');
        anchor.removeAttribute('data-retail-direct-link');
        anchor.setAttribute('data-retail-report-group', '1');
        anchor.setAttribute('role', 'button');
        anchor.setAttribute('tabindex', '0');
    }

    function bindSubmenuRouting() {
        // Report categories are menu controls, never Workspace routes.
        document.addEventListener('click', event => {
            const container = event.target.closest('.sidebar-item-container');
            if (!container) return;
            const item = dynamicSidebarItems.get(getWorkspaceName(container));
            if (!item?.is_report_group && container.dataset.retailReportGroup !== '1') return;

            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
            const section = container.querySelector(':scope > .sidebar-child-item');
            if (!section) return;
            const open = section.classList.contains('hidden');
            Array.from(container.parentElement?.children || []).forEach(sibling => {
                if (sibling === container || !sibling.matches('.sidebar-item-container')) return;
                setSidebarExpanded(sibling, false);
                rememberOpenSidebarGroup(getSidebarRoutingLabel(sibling) || getItemLabel(sibling), false);
            });
            setSidebarExpanded(container, open);
            rememberOpenSidebarGroup(getSidebarRoutingLabel(container) || getItemLabel(container), open);
        }, true);

        document.addEventListener('keydown', event => {
            if (event.key !== 'Enter' && event.key !== ' ') return;
            const anchor = event.target.closest('.item-anchor[data-retail-report-group]');
            if (!anchor) return;
            event.preventDefault();
            anchor.click();
        });

        document.addEventListener('click', event => {
            if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;

            const targetElement = event.target.closest('a, button, .shortcut-widget-box, .widget, .sidebar-item-container');
            if (!targetElement) return;

            const text = normalizeText(targetElement.innerText || targetElement.textContent || '');
            const title = normalizeText(targetElement.getAttribute?.('title') || '');
            const pageTargets = {
                'van stock view': ['van-stock-view', 'Van Stock View'],
                'stock request': ['van-stock-request', 'Stock Request'],
                'van stock request': ['van-stock-request', 'Stock Request'],
            };
            const pageTarget = pageTargets[text] || pageTargets[title];
            if (!pageTarget) return;
            if (!routeIsAllowed([pageTarget[0]])) return;

            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation?.();
            rememberSidebarContext(pageTarget[1]);
            routeToTarget([pageTarget[0]]).then(() => {
                syncSidebarState();
                scheduleRetry();
            });
        }, true);

        document.addEventListener('click', event => {
            if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;

            const container = event.target.closest('.sidebar-item-container');
            const children = container?.querySelector(':scope > .sidebar-child-item');
            const mainLabel = getItemLabel(container);
            if (TOP_LEVEL_WORKSPACES.has(mainLabel) && !event.target.closest('.drop-icon, .sidebar-item-control')) {
                event.preventDefault();
                event.stopImmediatePropagation();
                const open = !children?.children.length || children.classList.contains('hidden');
                getSelectableSidebarContainers().forEach(item => {
                    const section = item.querySelector(':scope > .sidebar-child-item');
                    const expanded = open && getItemLabel(item) === mainLabel;
                    if (section) setSidebarExpanded(item, expanded);
                    rememberOpenSidebarGroup(getSidebarRoutingLabel(item) || getItemLabel(item), expanded);
                });
                // Collapsing must keep the current route so refreshes retain the closed state.
                if (!open) return;
                rememberSidebarContext(mainLabel);
                frappe.route_options = null;
                Promise.resolve(frappe.set_route(getWorkspaceUrl(mainLabel, true).replace(/^\/app\//, '')))
                    .then(() => scheduleSidebarEnhancements());
                return;
            }
            if (children?.children.length) {
                event.preventDefault();
                event.stopImmediatePropagation();
                const open = children.classList.contains('hidden');
                const siblings = container.parentElement?.children || [];
                Array.from(siblings).forEach(sibling => {
                    const section = sibling.querySelector(':scope > .sidebar-child-item');
                    if (section) setSidebarExpanded(sibling, false);
                    rememberOpenSidebarGroup(getSidebarRoutingLabel(sibling) || getItemLabel(sibling), false);
                });
                setSidebarExpanded(container, open);
                rememberOpenSidebarGroup(getSidebarRoutingLabel(container) || mainLabel, open);
                setDropIcon(container, open);
                return;
            }
            if (event.target.closest('.drop-icon, .sidebar-item-control')) return;
            const anchor = event.target.closest('.item-anchor') || container?.querySelector(':scope > .desk-sidebar-item > .item-anchor');
            const label = getItemLabel(container);
            const routingLabel = getSidebarRoutingLabel(container);
            const parent = CHILD_TO_PARENT[routingLabel];
            const target = getSidebarTarget({
                    name: getWorkspaceName(container),
                    title: routingLabel || label
                }) ||
                getAnchorRouteTarget(anchor) ||
                getTargetFromUrl(anchor);

            if (target) {
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();

                rememberSidebarContext(routingLabel || label);
                Promise.resolve(routeToTarget(target)).then(() => {
                    syncSidebarState();
                    scheduleRetry();
                });
                return;
            }

            if (parent) {
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();

                rememberSidebarContext(routingLabel || label);
                frappe.route_options = null;
                frappe.set_route(getWorkspaceUrl(getWorkspaceName(container), true).replace(/^\/app\//, ''));
                return;
            }

            if (!target && !TOP_LEVEL_WORKSPACES.has(label) && !CHILD_TO_PARENT[routingLabel]) return;

            event.preventDefault();
            frappe.route_options = null;
            rememberSidebarContext(routingLabel || label);
            frappe.set_route(getWorkspaceUrl(getWorkspaceName(container), true).replace(/^\/app\//, ''));
        }, true);
    }

    function applyDirectLinks() {
        document.querySelectorAll('.sidebar-item-container').forEach(container => {
            const label = getItemLabel(container);
            const routingLabel = getSidebarRoutingLabel(container);
            const anchor = container.querySelector(':scope > .desk-sidebar-item > .item-anchor');
            if (dynamicSidebarItems.get(getWorkspaceName(container))?.is_report_group ||
                container.dataset.retailReportGroup === '1') {
                configureReportGroupAnchor(anchor);
                return;
            }
            const target = getSidebarTarget({
                name: getWorkspaceName(container),
                title: routingLabel || label
            });

            if (target) {
                anchor?.setAttribute('href', getTargetUrl(target));
                anchor?.setAttribute('data-retail-direct-link', '1');
                setAnchorRouteTarget(anchor, target);
            } else if (CHILD_TO_PARENT[routingLabel]) {
                anchor?.setAttribute('href', getWorkspaceUrl(getWorkspaceName(container), true));
                anchor?.setAttribute('data-retail-direct-link', '1');
                anchor?.removeAttribute('data-retail-route-target');
            } else if (TOP_LEVEL_WORKSPACES.has(label)) {
                anchor?.setAttribute('href', getWorkspaceUrl(getWorkspaceName(container), true));
                anchor?.setAttribute('data-retail-direct-link', '1');
                anchor?.removeAttribute('data-retail-route-target');
            }
        });
    }

    function buildSidebarItem(item, pages) {
        const title = item.title;
        const displayTitle = WORKSPACE_DISPLAY_LABELS[item.name] || title;
        const children = pages.filter(page => page.parent_page === title && sidebarItemIsAllowed(page));
        const target = getSidebarTarget(item);
        const href = target ? getTargetUrl(target) : getWorkspaceUrl(item.name || title, item.public);
        const routeTargetAttribute = target
            ? ` data-retail-route-target="${escapeHtml(JSON.stringify(target))}"`
            : '';
        const container = document.createElement('div');
        container.className = 'sidebar-item-container retail-sidebar-item';
        let parent = item.parent_page;
        let level = 0;
        const seenParents = new Set();
        while (parent && !seenParents.has(parent)) {
            seenParents.add(parent);
            level += 1;
            parent = pages.find(page => page.title === parent || page.name === parent)?.parent_page;
        }
        container.dataset.retailLevel = level;
        if (item.is_report_group) container.dataset.retailReportGroup = '1';
        if (item.is_report_link) container.dataset.retailReportLink = '1';
        container.setAttribute('item-name', displayTitle);
        container.setAttribute('item-workspace-name', item.name || title);
        container.setAttribute('item-parent', item.parent_page || '');
        container.setAttribute('item-public', item.public || 0);
        container.setAttribute('item-is-hidden', item.is_hidden || 0);
        container.innerHTML = `
            <div class="desk-sidebar-item standard-sidebar-item">
                <a href="${href}" class="item-anchor block-click" title="${escapeHtml(__(displayTitle))}"${routeTargetAttribute}>
                    <span class="sidebar-item-icon"></span>
                    <span class="sidebar-item-label">${escapeHtml(__(displayTitle))}</span>
                </a>
                <div class="sidebar-item-control"></div>
            </div>
            <div class="sidebar-child-item nested-container hidden"></div>
        `;

        if (item.is_report_group) {
            configureReportGroupAnchor(container.querySelector(':scope > .desk-sidebar-item > .item-anchor'));
        }

        const iconConfig = findIconConfig(displayTitle) || findIconConfig(item.name || title);
        const iconContainer = container.querySelector(':scope > .desk-sidebar-item .sidebar-item-icon');
        if (iconConfig && iconContainer) {
            iconContainer.innerHTML = '';
            iconContainer.appendChild(createIconElement(iconConfig));
        }

        if (children.length) {
            const control = container.querySelector('.sidebar-item-control');
            const childSection = container.querySelector('.sidebar-child-item');
            const button = document.createElement('button');
            button.className = 'btn-reset drop-icon retail-drop-icon';
            button.type = 'button';
            button.setAttribute('aria-expanded', 'false');
            button.innerHTML = getSmallDropIcon(false);
            control.appendChild(button);
            children.forEach(child => childSection.appendChild(buildSidebarItem(child, pages)));
        }

        return container;
    }

    function ensureBusinessHomeSidebarItem(items) {
        if (!Array.isArray(items)) return [];
        if (Array.isArray(frappe.boot?.retail_sidebar_selection) && !workspaceIsAllowed('Business Home')) return items;

        const hasBusinessHome = items.some(item => (item.title || item.name) === 'Business Home');
        if (hasBusinessHome) return items;

        return [
            {
                name: 'Business Home',
                title: 'Business Home',
                public: 1,
                parent_page: '',
                is_hidden: 0
            },
            ...items
        ];
    }

    function ensureVanSalesSidebarChildren(items) {
        if (!Array.isArray(items)) return [];
        const hasVanSales = items.some(item => (item.title || item.name) === 'Van Sales');
        if (!hasVanSales || !sidebarWorkspaceIsAllowed('Van Sales')) return items;

        const nextItems = [...items];

        function insertOrMoveRequiredChild(child) {
            const { insert_after, ...childItem } = child;
            const existingIndex = nextItems.findIndex(item => (
                item.name === child.name ||
                item.title === child.title ||
                WORKSPACE_DISPLAY_LABELS[item.name] === child.title
            ));
            const existingItem = existingIndex >= 0 ? nextItems[existingIndex] : {};
            const sidebarChild = {
                ...existingItem,
                ...childItem,
                name: existingItem.name || childItem.name,
                title: childItem.title,
                parent_page: 'Van Sales',
                public: 1,
                is_hidden: 0
            };

            if (!sidebarItemIsAllowed(sidebarChild)) return;
            if (existingIndex >= 0) nextItems.splice(existingIndex, 1);

            const insertAfterLabels = insert_after || ['Van Sessions'];
            const insertAfterIndex = nextItems.findIndex(item => {
                const displayLabel = WORKSPACE_DISPLAY_LABELS[item.name] || item.title;
                return insertAfterLabels.includes(item.name) ||
                    insertAfterLabels.includes(item.title) ||
                    insertAfterLabels.includes(displayLabel);
            });
            if (insertAfterIndex >= 0) {
                nextItems.splice(insertAfterIndex + 1, 0, sidebarChild);
            } else {
                nextItems.push(sidebarChild);
            }
        }

        REQUIRED_VAN_SALES_CHILDREN.forEach(insertOrMoveRequiredChild);

        return nextItems;
    }

    function getSidebarItems() {
        if (sidebarItemsCache) return Promise.resolve(sidebarItemsCache);
        // Only Retail-filtered boot data is eligible, and only on initial mounting.
        if (useBootSidebarItems && frappe.boot?.retail_workspace_sidebar_groups &&
            Array.isArray(frappe.boot?.allowed_workspaces)) {
            useBootSidebarItems = false;
            sidebarItemsCache = ensureVanSalesSidebarChildren(
                ensureBusinessHomeSidebarItem(frappe.boot.allowed_workspaces)
            );
            registerSidebarItems(sidebarItemsCache);
            return Promise.resolve(sidebarItemsCache);
        }
        useBootSidebarItems = false;
        if (!sidebarItemsPromise) {
            const generation = sidebarItemsGeneration;
            sidebarItemsPromise = frappe
                .xcall('retail.workspace_permissions.get_workspace_sidebar_items')
                .then(result => {
                    const items = ensureVanSalesSidebarChildren(
                        ensureBusinessHomeSidebarItem(Array.isArray(result) ? result : result?.pages || [])
                    );
                    if (generation === sidebarItemsGeneration) {
                        sidebarItemsCache = items;
                        registerSidebarItems(items);
                        sidebarItemsPromise = null;
                    }
                    return items;
                })
                .catch(error => {
                    if (generation === sidebarItemsGeneration) sidebarItemsPromise = null;
                    throw error;
                });
        }
        return sidebarItemsPromise;
    }

    function renderPersistentSidebar() {
        const route = frappe.get_route();
        if (isWorkspaceRoute(frappe.get_route()) && !isItemFamilyPageRoute()) {
            removePersistentSidebar();
            syncDesktopSidebarClass();
            return;
        }

        const sideSections = getSidebarMountSections();
        if (!sideSections.length) {
            syncDesktopSidebarClass();
            if (sidebarRenderRetryCount < 8 && !sidebarRenderRetryTimer) {
                sidebarRenderRetryCount += 1;
                sidebarRenderRetryTimer = setTimeout(() => {
                    sidebarRenderRetryTimer = null;
                    renderPersistentSidebar();
                }, 250);
            }
            return;
        }
        clearTimeout(sidebarRenderRetryTimer);
        sidebarRenderRetryTimer = null;
        sidebarRenderRetryCount = 0;
        if (sideSections.every(section => section.querySelector('.retail-persistent-sidebar'))) {
            sideSections.forEach(section => mountPersistentSidebar(section, []));
            syncDesktopSidebarClass();
            return;
        }

        const generation = sidebarItemsGeneration;
        getSidebarItems().then(items => {
            if (generation !== sidebarItemsGeneration) return;
            if (isWorkspaceRoute(frappe.get_route()) && !isItemFamilyPageRoute()) {
                removePersistentSidebar();
                return;
            }
            getSidebarMountSections().forEach(section => mountPersistentSidebar(section, items));
            hideUnauthorizedSidebarItems();
            applyIcons();
            syncSidebarState();
            syncDesktopSidebarClass();
        }).catch(error => {
            console.error('retail_navigation: failed to render persistent sidebar', error);
            syncDesktopSidebarClass();
        });
    }

    let sidebarObserver;

    function refreshSidebarEnhancements() {
        hideStandardHomeSidebarItems();
        applyDisplayLabels();
        applyDirectLinks();
        hideUnauthorizedSidebarItems();
        applyIcons();
        ensureWorkspaceDropIcons();
        syncSidebarState();
        forceVanSidebarSelection();
        renderPersistentSidebar();
        syncDesktopSidebarClass();
        applyWideTransactionLayout();
        upsertCurrentWorkTab();
        // Our own synchronous DOM changes must not schedule another refresh.
        sidebarObserver?.takeRecords();
    }

    function scheduleSidebarEnhancements(delay = 80) {
        clearTimeout(observerRefreshTimer);
        observerRefreshTimer = setTimeout(refreshSidebarEnhancements, delay);
    }

    function observeSidebarChanges() {
        const sidebarSelector = ".desk-sidebar, .layout-side-section, .overlay-sidebar, .workspace-sidebar";
        sidebarObserver = new MutationObserver(mutations => {
            if (mutations.some(m => {
                if (!(m.target instanceof Element)) return false;
                if (m.target.closest('.retail-open-work')) return false;
                if (m.target.closest(sidebarSelector)) return m.addedNodes.length || m.removedNodes.length;
                // Detect newly mounted sidebars without reacting to ordinary form/grid changes.
                return Array.from(m.addedNodes).some(node => node instanceof Element &&
                    (node.matches(sidebarSelector) || node.querySelector(sidebarSelector)));
            })) {
                debugLog('retail_navigation: sidebar DOM mutated, reapplying icons');
                scheduleSidebarEnhancements();
            }
        });

        sidebarObserver.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    function scheduleRetry() {
        // Mount observer and bounded mount retry handle delayed sidebar creation.
        scheduleSidebarEnhancements(250);
    }

    function scheduleMobileSidebarRender() {
        if (!isMobile()) return;
        scheduleSidebarEnhancements(80);
    }

    function bindMobileSidebarToggle() {
        if (window.__retailMobileSidebarToggleBound) return;
        window.__retailMobileSidebarToggleBound = true;

        $(document.body).on('toggleSidebar.retailMobileSidebar', scheduleMobileSidebarRender);
        document.addEventListener('click', event => {
            if (event.target.closest('.sidebar-toggle-btn')) {
                scheduleMobileSidebarRender();
            }
        }, true);
    }

    function redirectItemFamilyListRoute() {
        const route = frappe.get_route();
        if (!Array.isArray(route) || !route.length) return false;

        const view = String(route[0] || '').toLowerCase();
        const title = decodeURIComponent(String(route[route[1] === 'private' ? 2 : 1] || ''));
        const slug = frappe.router.slug(title || route[0] || '');
        const isOldItemFamilyRoute =
            (view === 'query-report' && title === 'Item Family List') ||
            ((view === 'workspaces' || view === 'workspace') && title === 'Item Family List') ||
            slug === 'item-family-list';

        if (!isOldItemFamilyRoute) return false;

        frappe.set_route('retail-item-family-l');
        return true;
    }

    function installPOSBreadcrumbs() {
        const breadcrumbs = frappe.breadcrumbs;
        if (!breadcrumbs?.set_workspace_breadcrumb || breadcrumbs.__retail_pos_installed) return;
        const posDoctypes = new Set([
            'POS Branch Counter', 'POS Cashier Shift', 'POS Counter Session',
            'POS Closing Entry', 'POS Branch Day Closing', 'POS Sync Log',
        ]);
        const original = breadcrumbs.set_workspace_breadcrumb;
        breadcrumbs.set_workspace_breadcrumb = function (entry) {
            // These pages belong to POS even when module/history selects Promotions.
            // Copy the entry so cached breadcrumb metadata remains untouched.
            if (posDoctypes.has(entry.doctype)) {
                entry = { ...entry, workspace: 'POS' };
            }
            return original.call(this, entry);
        };
        breadcrumbs.__retail_pos_installed = true;
    }

    function init() {
        installPOSBreadcrumbs();
        registerSidebarItems(frappe.boot?.allowed_workspaces || []);
        injectRetailInlineCss();
        bindNavbarHomeToBusinessHome();
        bindViewWebsiteToRetailHome();
        redirectStandardHomeToBusinessHome();
        redirectItemFamilyListRoute();
        enforceAllowedRoute();
        waitForWorkspaceModule();
        waitForSearchFilters();
        applyDisplayLabels();
        applyDirectLinks();
        bindViewWebsiteToRetailHome();
        applyIcons();
        ensureWorkspaceDropIcons();
        syncSidebarState();
        renderPersistentSidebar();
        applyWideTransactionLayout();
        upsertCurrentWorkTab();
        observeSidebarChanges();
        scheduleRetry();
        bindSubmenuRouting();
        bindOpenWorkEvents();
        bindMobileSidebarToggle();
        frappe.realtime?.on('retail_sidebar_permissions_changed', () => window.location.reload());

        if (window.frappe?.router?.on) {
            frappe.router.on('change', () => {
                sidebarItemsGeneration += 1;
                sidebarItemsCache = null;
                sidebarItemsPromise = null;
                useBootSidebarItems = false;
                if (redirectStandardHomeToBusinessHome()) return;
                if (enforceAllowedRoute()) return;
                redirectItemFamilyListRoute();
                clearTimeout(routeRefreshTimer);
                routeRefreshTimer = setTimeout(refreshSidebarEnhancements, 120);
                setTimeout(applyWideTransactionLayout, 350);
                setTimeout(applyWideTransactionLayout, 900);
                setTimeout(upsertCurrentWorkTab, 350);
            });
        }

        window.matchMedia(DESKTOP_MEDIA).addEventListener('change', () => {
            refreshSidebarEnhancements();
            renderOpenWorkTabs();
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
