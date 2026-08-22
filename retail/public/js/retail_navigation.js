(function() {
    const DEBUG = false;
    const debugLog = (...args) => DEBUG && console.log(...args);
    debugLog('retail_navigation: script loaded', {host: window.location.host, readyState: document.readyState});
    const OPEN_WORK_STORAGE_KEY = 'retail_open_work_tabs_v3';
    const OPEN_WORK_TTL_MS = 12 * 60 * 60 * 1000;
    const ICON_MAP = {
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
        'bom': { icon: 'fa fa-sitemap', cls: 'color-manufacturing' },
        'production plan': { icon: 'fa fa-calendar-check-o', cls: 'color-manufacturing' },
        'work orders': { icon: 'fa fa-tasks', cls: 'color-manufacturing' },
        'job cards': { icon: 'fa fa-id-card-o', cls: 'color-manufacturing' },
        'stock entries': { icon: 'fa fa-exchange', cls: 'color-manufacturing' },
        'quality inspection': { icon: 'fa fa-check-square-o', cls: 'color-manufacturing' },
        'manufacturing reports': { icon: 'fa fa-line-chart', cls: 'color-manufacturing' },
        'manufacturing setup': { icon: 'fa fa-cogs', cls: 'color-manufacturing' },
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
        , 'pos sales summary': { icon: 'fa fa-bar-chart', cls: 'color-accounts' }
        , 'pos transaction log': { icon: 'fa fa-list', cls: 'color-accounts' }
        , 'pos item-wise sales': { icon: 'fa fa-cubes', cls: 'color-sales' }
        , 'pos category/item group sales': { icon: 'fa fa-sitemap', cls: 'color-sales' }
        , 'pos category item group sales': { icon: 'fa fa-sitemap', cls: 'color-sales' }
        , 'counter performance': { icon: 'fa fa-tachometer', cls: 'color-sales' }
        , 'pos hourly sales': { icon: 'fa fa-clock-o', cls: 'color-sales' }
        , 'pos return report': { icon: 'fa fa-undo', cls: 'color-sales' }
        , 'cashier wise sales': { icon: 'fa fa-user', cls: 'color-pos-shifts' }
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
        , 'promo price': { icon: 'fa fa-tags', cls: 'color-sales' }
        , 'buy x get y promotion': { icon: 'fa fa-gift', cls: 'color-sales' }
        , 'gift voucher promotion': { icon: 'fa fa-ticket', cls: 'color-sales' }
        , 'gift voucher ledger': { icon: 'fa fa-list-alt', cls: 'color-sales' }
    };
    const DESKTOP_MEDIA = '(min-width: 992px)';
    const DIRECT_MAPPING = {
        'Items List': ['List', 'Item'],
        'Item Family List': ['retail-item-family-l'],
        'Item Groups': ['List', 'Item Group'],
        'Price Lists': ['List', 'Item Price'],
        'Brands': ['List', 'Brand'],
        'Customers': ['List', 'Customer'],
        'Quotation': ['List', 'Quotation'],
        'Quotations': ['List', 'Quotation'],
        'Sales Orders': ['List', 'Sales Order'],
        'Sales Invoices': ['List', 'Sales Invoice'],
        'Sales Returns': ['List', 'Sales Invoice', { is_return: 1 }],
        'POS Invoices': ['List', 'POS Invoice'],
        'Trading Invoices': ['List', 'Sales Invoice', { is_pos: 0 }],
        'All Sales Invoices': ['List', 'Sales Invoice'],
        'POS Profile': ['List', 'POS Profile'],
        'POS Profiles': ['List', 'POS Profile'],
        'POS Cashier Shifts': ['List', 'POS Cashier Shift'],
        'POS Counter Sessions': ['List', 'POS Counter Session'],
        'POS Opening Entry': ['List', 'POS Opening Entry'],
        'POS Opening Entries': ['List', 'POS Opening Entry'],
        'POS Closing Entry': ['List', 'POS Closing Entry'],
        'POS Closing Entries': ['List', 'POS Closing Entry'],
        'POS Branch Day Closing': ['List', 'POS Branch Day Closing'],
        'POS Branch Day Closings': ['List', 'POS Branch Day Closing'],
        'POS Sync Log': ['List', 'POS Sync Log'],
        'POS Sync Logs': ['List', 'POS Sync Log'],
        'Mode of Payment': ['List', 'Mode of Payment'],
        'POS Counters': ['List', 'POS Branch Counter'],
        'POS Payments': ['List', 'Payment Entry'],
        'POS Sales Summary': ['query-report', 'POS Sales Summary'],
        'POS Transaction Log': ['query-report', 'POS Transaction Log'],
        'POS Item-wise Sales': ['query-report', 'POS Item-wise Sales'],
        'POS Category/Item Group Sales': ['query-report', 'POS Category Item Group Sales'],
        'POS Category Item Group Sales': ['query-report', 'POS Category Item Group Sales'],
        'POS Hourly Sales': ['query-report', 'POS Hourly Sales'],
        'POS Return Report': ['query-report', 'POS Return Report'],
        'Cashier Wise Sales': ['query-report', 'Cashier Wise Sales'],
        'Counter Wise Sales': ['query-report', 'Counter Wise Sales'],
        'Shift Closing Variance': ['query-report', 'Shift Closing Variance'],
        'Payment Mode Summary': ['query-report', 'POS Payment Mode Summary'],
        'POS Payment Mode Summary': ['query-report', 'POS Payment Mode Summary'],
        'POS Discount Report': ['query-report', 'POS Discount Report'],
        'POS Price Override Report': ['query-report', 'POS Price Override Report'],
        'POS Daily Closing Summary': ['query-report', 'POS Daily Closing Summary'],
        'POS Cash Movement Report': ['query-report', 'POS Cash Movement Report'],
        'Item Group Sales Analysis': ['query-report', 'Item Group Sales Analysis'],
        'Daily Sales Summary': ['query-report', 'Daily Sales Summary'],
        'Daily Transaction Log': ['query-report', 'Daily Transaction Log'],
        'Sales Payment Mode Summary': ['query-report', 'Sales Payment Mode Summary'],
        'Daily Profit Report': ['query-report', 'Daily Profit Report'],
        'Gross Profit': ['query-report', 'Gross Profit'],
        'Sales Tax Report': ['query-report', 'Sales Tax Report'],
        'Sales Day wise Tax Report': ['query-report', 'Sales Day wise Tax Report'],
        'Purchase Register': ['query-report', 'Purchase Register'],
        'Purchase Tax Report': ['query-report', 'Purchase Tax Report'],
        'Purchase Day wise Tax Report': ['query-report', 'Purchase Day wise Tax Report'],
        'Supplier Wise Returns': ['query-report', 'Supplier Wise Returns'],
        'Stock Balance': ['query-report', 'Stock Balance'],
        'Stock Ledger': ['query-report', 'Stock Ledger'],
        'Packing Stock Balance': ['query-report', 'Packing Stock Balance'],
        'Packing Stock Ledger': ['query-report', 'Packing Stock Ledger'],
        'Stock Movement Summary': ['query-report', 'Stock Movement Summary'],
        'Stock Adjustment History': ['query-report', 'Stock Adjustment History'],
        'Low Stock Reorder Report': ['query-report', 'Low Stock Reorder Report'],
        'Fast Moving Items': ['query-report', 'Fast Moving Items'],
        'Slow Moving Items': ['query-report', 'Slow Moving Items'],
        'Negative Stock Report': ['query-report', 'Negative Stock Report'],
        'Near Expiry Report': ['query-report', 'Near Expiry Report'],
        'Expiry Loss': ['query-report', 'Expiry Loss'],
        'General Ledger': ['query-report', 'General Ledger'],
        'Trial Balance': ['query-report', 'Trial Balance'],
        'Balance Sheet': ['query-report', 'Balance Sheet'],
        'Profit and Loss Statement': ['query-report', 'Profit and Loss Statement'],
        'Tax Report': ['query-report', 'Tax Report'],
        'Tax Payable Report Summary': ['query-report', 'Tax Payable Report Summary'],
        'Counter Performance': ['query-report', 'Counter Performance'],
        'Delivery Notes': ['List', 'Delivery Note'],
        'Promo Price': ['List', 'Promo Price'],
        'Buy X Get Y Promotion': ['List', 'Buy X Get Y Promotion'],
        'Gift Voucher Promotion': ['List', 'Gift Voucher Promotion'],
        'Gift Voucher Ledger': ['List', 'Gift Voucher Ledger'],
        'Suppliers': ['List', 'Supplier'],
        'Material Request': ['List', 'Material Request'],
        'Material Requests': ['List', 'Material Request'],
        'Request for Quotation': ['List', 'Request for Quotation'],
        'Request for Quotations': ['List', 'Request for Quotation'],
        'Supplier Quotation': ['List', 'Supplier Quotation'],
        'Supplier Quotations': ['List', 'Supplier Quotation'],
        'Purchase Orders': ['List', 'Purchase Order'],
        'Purchase Receipts': ['List', 'Purchase Receipt'],
        'Purchase Invoice': ['List', 'Purchase Invoice'],
        'Purchase Invoices': ['List', 'Purchase Invoice'],
        'Purchase Bills': ['List', 'Purchase Invoice'],
        'Purchase Returns': ['List', 'Purchase Receipt', { is_return: 1 }],
        'BOM': ['List', 'BOM'],
        'Production Plan': ['List', 'Production Plan'],
        'Work Orders': ['List', 'Work Order'],
        'Job Cards': ['List', 'Job Card'],
        'Stock Entries': ['List', 'Stock Entry'],
        'Quality Inspection': ['List', 'Quality Inspection'],
        'BOM Stock Report': ['query-report', 'BOM Stock Report'],
        'Work Order Stock Report': ['query-report', 'Work Order Stock Report'],
        'Open Work Orders': ['query-report', 'Open Work Orders'],
        'Work Orders in Progress': ['query-report', 'Work Orders in Progress'],
        'Completed Work Orders': ['query-report', 'Completed Work Orders'],
        'Work Order Summary': ['query-report', 'Work Order Summary'],
        'Job Card Summary': ['query-report', 'Job Card Summary'],
        'Production Analytics': ['query-report', 'Production Analytics'],
        'Operations': ['List', 'Operation'],
        'Workstations': ['List', 'Workstation'],
        'Routing': ['List', 'Routing'],
        'BOM Creator': ['List', 'BOM Creator'],
        'Manufacturing Settings': ['Form', 'Manufacturing Settings', 'Manufacturing Settings'],
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
        'User List': ['List', 'User'],
        'Employee List': ['List', 'Employee'],
        'Branding': ['List', 'Letter Head'],
        'System Rules': ['List', 'Document Naming Rule'],
        'POS Counters': ['List', 'POS Branch Counter']
    };
    const DOCTYPE_TO_WORKSPACE = {
        'Item': 'Items',
        'Item Group': 'Items',
        'Price List': 'Items',
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
        'Letter Head': 'Settings',
        'Document Naming Rule': 'Settings',
        'POS Branch Counter': 'POS'
    };
    const DOCTYPE_TO_CHILD = {
        'Item': 'Items List',
        'Item Group': 'Item Groups',
        'Price List': 'Price Lists',
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
        'Letter Head': 'Branding',
        'Document Naming Rule': 'System Rules',
        'POS Branch Counter': 'POS Counters'
    };
    const CHILD_TO_PARENT = Object.freeze({
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
        'Promo Price': 'Sales',
        'Buy X Get Y Promotion': 'Sales',
        'Gift Voucher Promotion': 'Sales',
        'Gift Voucher Ledger': 'Sales',
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
        'System Rules': 'Settings'
    });
    const ROUTE_ALIAS_TO_CHILD = Object.freeze({
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
    const WORKSPACE_DISPLAY_LABELS = Object.freeze({
        'Manufacturing BOM': 'BOM',
        'Manufacturing Production Plan': 'Production Plan',
        'Manufacturing Quality Inspection': 'Quality Inspection',
        'Manufacturing Reports': 'Reports',
        'Manufacturing Setup': 'Setup'
    });
    const TOP_LEVEL_WORKSPACES = new Set([
        'Business Home',
        'Items',
        'Sales',
        'POS',
        'Purchases',
        'Stocks',
        'Manufacturing',
        'Accounts',
        'Reports',
        'Settings'
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
        'Sales Invoices': 'Accounts',
        'Sales Returns': 'Accounts',
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
        'Employee List': 'HR'
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
    });
    let sidebarItemsPromise = null;
    let sidebarItemsCache = null;
    let observerRefreshTimer = null;
    let routeRefreshTimer = null;
    let sidebarRenderRetryCount = 0;
    let workspaceCustomCardsPatched = false;
    let openWorkClearedRouteKey = null;
    let lastSidebarTogglePointerAt = 0;
    const dynamicChildToParent = {};
    const dynamicReportToGroup = {};

    function redirectStandardHomeToBusinessHome() {
        const route = frappe.get_route?.() || [];
        const routeName = route[0] === 'private' ? route[1] : route[0];
        if (frappe.router.slug(routeName || '') !== 'home') return false;

        const target = getWorkspaceUrl('Business Home', true).replace(/^\/app\//, '');
        if (route.join('/') === target) return false;

        frappe.set_route(target);
        return true;
    }

    function bindNavbarHomeToBusinessHome() {
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
        return !moduleName || !getBlockedModules().has(moduleName);
    }

    function getWorkspaceModule(workspaceName) {
        if (!workspaceName) return '';
        return WORKSPACE_TO_MODULE[workspaceName] || frappe.boot?.retail_workspace_modules?.[workspaceName] || '';
    }

    function workspaceIsAllowed(workspaceName) {
        let current = workspaceName;
        const seen = new Set();

        while (current && !seen.has(current)) {
            seen.add(current);
            if (!moduleIsAllowed(getWorkspaceModule(current))) return false;
            current = getParentLabel(current);
        }

        return true;
    }

    function doctypeIsAllowed(doctype) {
        if (!doctype) return true;
        const workspace = DOCTYPE_TO_CHILD[doctype] || DOCTYPE_TO_WORKSPACE[doctype];
        return workspace ? workspaceIsAllowed(workspace) : true;
    }

    function reportIsAllowed(reportName, report) {
        const workspace = REPORT_TO_WORKSPACE[reportName];
        if (workspace) return workspaceIsAllowed(workspace);
        return doctypeIsAllowed(report?.ref_doctype);
    }

    function routeIsAllowed(route) {
        if (!Array.isArray(route) || !route.length) return true;
        const view = route[0];
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
        return true;
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
        frappe.set_route(getWorkspaceUrl('Business Home', true).replace(/^\/app\//, ''));
        return true;
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

    function waitForWorkspaceModule() {
        if (suppressCustomDocumentCards()) return;

        let attempts = 0;
        const timer = setInterval(() => {
            attempts += 1;
            if (suppressCustomDocumentCards() || attempts >= 40) clearInterval(timer);
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

    function clearSalesReturnFilter() {
        if (window.cur_list?.doctype !== "Sales Invoice") return false;

        const filter = window.cur_list.filter_area?.get_filter("is_return");
        if (!filter) return false;

        filter.remove();
        window.cur_list.filter_area.update_filters();
        return true;
    }

    function routeToTarget(target) {
        const route = target.filter(part => !$.isPlainObject(part));
        const filters = target.find(part => $.isPlainObject(part));

        // A route option alone keeps the same URL as an unfiltered list. When
        // moving from Sales Invoices to Sales Returns, Frappe can therefore
        // reuse the already-rendered list and ignore the new filter. Put list
        // filters in the URL so this is always a distinct, reloadable route.
        if (filters && Object.keys(filters).length) {
            return routeToUrl(getTargetUrl(target));
        }

        // Sales Invoices is the normal, unfiltered list. Remove only the
        // return filter left by the Sales Returns submenu, preserving any
        // other filters the user has selected.
        const clearedReturnFilter = route[0] === "List" && route[1] === "Sales Invoice"
            ? clearSalesReturnFilter()
            : false;
        frappe.route_options = filters || null;
        return frappe.set_route(...route).then(() => {
            if (clearedReturnFilter && window.cur_list?.doctype === "Sales Invoice") {
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
        if (isVisibleElement(pageSideSection)) return pageSideSection;

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
            && (
                getParentLabel(workspaceName)
                || DIRECT_MAPPING[workspaceName]
                || WORKSPACE_TO_MODULE[workspaceName]
                || container?.dataset?.retailReportLink === '1'
                || container?.dataset?.retailReportGroup === '1'
            )
        ) {
            return workspaceName;
        }
        return label;
    }

    function getParentLabel(label) {
        return CHILD_TO_PARENT[label] || dynamicChildToParent[label] || '';
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

    function isDescendantOf(label, parentLabel) {
        let current = label;
        const seen = new Set();
        while (getParentLabel(current) && !seen.has(current)) {
            seen.add(current);
            current = getParentLabel(current);
            if (current === parentLabel) return true;
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
        const mappedChild = getMappedChildFromRoute(route, filters);

        if (isItemFamilyPageRoute(route)) {
            return { main: 'Items', child: 'Item Family List' };
        }

        if (mappedChild) {
            return { main: getTopParentLabel(mappedChild) || DOCTYPE_TO_WORKSPACE[route?.[1]], child: mappedChild };
        }

        if (view === 'query-report' && route[1]) {
            const group = dynamicReportToGroup[route[1]];
            if (group) return { main: 'Reports', child: route[1] };
        }

        if (view === 'workspaces' || view === 'workspace') {
            const title = decodeURIComponent(route[route[1] === 'private' ? 2 : 1] || '');
            if (getParentLabel(title)) {
                return { main: getTopParentLabel(title), child: title };
            }
            return { main: title, child: '' };
        }

        const workspaceSlug = frappe.router.slug(
            route?.[0] === 'private' ? route?.[1] || '' : route?.[0] || ''
        );
        const workspaceTitle = frappe.workspaces?.[workspaceSlug]?.title;
        if (workspaceTitle) {
            if (getParentLabel(workspaceTitle)) {
                return { main: getTopParentLabel(workspaceTitle), child: workspaceTitle };
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
        const href = '/assets/retail/css/retail_icons.css?v=22';
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

    function hideStandardHomeSidebarItems() {
        document.querySelectorAll('.sidebar-item-container').forEach(container => {
            const label = getItemLabel(container);
            const workspaceName = container.getAttribute('item-workspace-name') || label;
            if (label !== 'Home' && workspaceName !== 'Home') return;

            container.classList.add('hidden');
            container.style.display = 'none';
        });
    }

    function setDropIcon(container, open) {
        const use = container
            ?.querySelector(':scope > .desk-sidebar-item .drop-icon use');
        if (use) use.setAttribute('href', open ? '#es-small-down' : '#es-small-right');
    }

    function getSmallDropIcon(open) {
        return `
            <svg class="es-icon retail-small-chevron" aria-hidden="true">
                <use href="${open ? '#es-small-down' : '#es-small-right'}"></use>
            </svg>
        `;
    }

    function syncSidebarState() {
        const state = getRouteState();

        getSelectableSidebarContainers().forEach(container => {
            const label = getItemLabel(container);
            const routingLabel = getSidebarRoutingLabel(container);
            const directItem = container.querySelector(':scope > .desk-sidebar-item');
            const childSection = container.querySelector(':scope > .sidebar-child-item');
            const isMain = label && state.main === label;
            const isChild = (routingLabel && state.child === routingLabel) || (label && state.child === label);
            const shouldOpen = isMain || isChild;
            const isAncestor = !!(routingLabel && state.child && isDescendantOf(state.child, routingLabel));

            container.classList.toggle('retail-primary-active', !!isMain);
            container.classList.toggle('retail-secondary-active', !!isChild);
            container.classList.toggle('retail-ancestor-active', isAncestor && !isChild && !isMain);
            directItem?.classList.toggle('selected', !!(isMain || isChild));

            if (childSection && shouldOpen) {
                childSection.classList.remove('hidden');
                setDropIcon(container, true);
            }
        });
    }

    function ensureWorkspaceDropIcons() {
        if (!isWorkspaceRoute(frappe.get_route())) return;

        const toggleSidebarSection = (container, event) => {
            const childSection = container?.querySelector(':scope > .sidebar-child-item');
            if (!container || !childSection) return;

            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation?.();
            const isHidden = childSection.classList.toggle('hidden');
            setDropIcon(container, !isHidden);
        };

        getCurrentPage()
            ?.querySelectorAll('.desk-sidebar:not(.retail-persistent-sidebar) .sidebar-item-container')
            .forEach(container => {
                const childSection = container.querySelector(':scope > .sidebar-child-item');
                const control = container.querySelector(':scope > .desk-sidebar-item > .sidebar-item-control');
                const anchor = container.querySelector(':scope > .desk-sidebar-item > .item-anchor');
                if (!childSection || !control || !childSection.children.length) return;

                const button = document.createElement('button');
                button.className = 'btn-reset drop-icon retail-drop-icon';
                button.type = 'button';
                const childItems = Array.from(childSection.querySelectorAll(':scope > .sidebar-item-container'));
                const isClosed = childSection.classList.contains('hidden') ||
                    (childItems.length && childItems.every(child => child.classList.contains('hidden')));
                button.innerHTML = getSmallDropIcon(!isClosed);
                button.addEventListener('click', event => toggleSidebarSection(container, event));
                control.replaceChildren(button);

                if (anchor && !anchor.dataset.retailToggleBound) {
                    anchor.dataset.retailToggleBound = '1';
                    anchor.addEventListener('click', event => toggleSidebarSection(container, event));
                }
            });
    }

    function syncDesktopSidebarClass() {
        const hasSidebar = isDesktop() && !!document.querySelector('.layout-side-section .retail-persistent-sidebar');
        document.body.classList.toggle('retail-has-persistent-sidebar', hasSidebar);
    }

    function isWideDeskRoute(route = frappe.get_route()) {
        return isDesktop() && Array.isArray(route) && route.length > 0;
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
        document.querySelectorAll('.layout-side-section.retail-form-sidebar-mounted').forEach(section => {
            section.classList.remove('retail-form-sidebar-mounted', 'retail-mobile-sidebar-mounted');
            section.style.removeProperty('display');
        });
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

    function hideDuplicateSidebars(sideSection) {
        if (!sideSection) return;
        sideSection.querySelectorAll('.desk-sidebar, .standard-sidebar-section').forEach(section => {
            if (section.classList.contains('retail-persistent-sidebar')) return;
            if (section.closest('.retail-sidebar-host')) return;
            section.classList.add('hidden');
            section.style.display = 'none';
        });
    }

    function getWorkspaceName(container) {
        const label = getItemLabel(container);
        return container?.getAttribute('item-workspace-name') || WORKSPACE_ROUTE_NAMES[label] || label;
    }

    function getSidebarMountSections() {
        const overlaySections = Array.from(document.querySelectorAll('.overlay-sidebar'))
            .filter(section => !section.classList.contains('retail-sidebar-overlay'));

        if (isMobile() && overlaySections.length) {
            return overlaySections;
        }

        const sections = [];
        const currentSideSection = getCurrentPage()?.querySelector('.layout-side-section') || getCurrentSideSection();
        if (currentSideSection) sections.push(currentSideSection);
        return sections;
    }

    function buildPersistentSidebar(items) {
        const visibleItems = items.filter(item => !item.is_hidden && (item.title || item.name) !== 'Home');
        const publicItems = visibleItems.filter(item => item.public);
        const roots = publicItems.filter(item => !item.parent_page);
        const wrapper = document.createElement('div');
        wrapper.className = 'retail-persistent-sidebar standard-sidebar-section nested-container';
        wrapper.dataset.title = 'CELESTA';

        roots.forEach(item => wrapper.appendChild(buildSidebarItem(item, publicItems)));
        return wrapper;
    }

    function mountPersistentSidebar(section, items) {
        if (!section || section.querySelector('.retail-persistent-sidebar')) return;

        if (isDesktop() && section.classList.contains('layout-side-section')) {
            document.querySelectorAll('.retail-persistent-sidebar').forEach(sidebar => {
                if (!section.contains(sidebar)) sidebar.remove();
            });
        }

        const host = getRetailSidebarHost(section);
        host.prepend(buildPersistentSidebar(items));
        section.classList.add('retail-form-sidebar-mounted');
        section.classList.toggle('retail-mobile-sidebar-mounted', section.classList.contains('overlay-sidebar'));
        if (isDesktop() && section.classList.contains('layout-side-section')) {
            section.classList.remove('hidden');
            section.style.setProperty('display', 'block', 'important');
        }
        hideDuplicateSidebars(section);
    }

    function toggleSidebarSection(container, event) {
        const childSection = container?.querySelector(':scope > .sidebar-child-item') ||
            container?.querySelector('.sidebar-child-item');
        if (!container || !childSection?.children?.length) return false;

        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation?.();

        if (container.closest('.retail-persistent-sidebar')) {
            const isHidden = childSection.classList.toggle('hidden');
            setDropIcon(container, !isHidden);
            return true;
        }

        const childItems = Array.from(childSection.querySelectorAll(':scope > .sidebar-item-container'));
        const isClosed = childSection.classList.contains('hidden') ||
            (childItems.length && childItems.every(child => child.classList.contains('hidden')));

        if (childItems.length) {
            childSection.classList.toggle('hidden', false);
            childItems.forEach(child => {
                child.classList.toggle('hidden', !isClosed);
                child.style.removeProperty('display');
            });
        } else {
            childSection.classList.toggle('hidden', !isClosed);
        }
        setDropIcon(container, isClosed);
        setTimeout(() => setDropIcon(container, isClosed), 0);
        return true;
    }

    function bindWorkspaceSidebarToggle() {
        if (window.__retailWorkspaceSidebarToggleBound) return;
        window.__retailWorkspaceSidebarToggleBound = true;

        const handleArrowToggle = event => {
            if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;

            const control = event.target.closest('.drop-icon, .sidebar-item-control');
            const container = control?.closest('.sidebar-item-container');
            if (!container?.closest('.desk-sidebar:not(.retail-persistent-sidebar)')) return;

            if (container.querySelector(':scope > .sidebar-child-item')?.children?.length) {
                if (event.type === 'click' && Date.now() - lastSidebarTogglePointerAt < 450) {
                    event.preventDefault();
                    event.stopPropagation();
                    event.stopImmediatePropagation?.();
                    return;
                }
                if (event.type === 'pointerdown') {
                    lastSidebarTogglePointerAt = Date.now();
                }
                toggleSidebarSection(container, event);
            }
        };

        document.addEventListener('pointerdown', handleArrowToggle, true);
        document.addEventListener('click', handleArrowToggle, true);
    }

    function bindSubmenuRouting() {
        document.addEventListener('click', event => {
            if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            if (event.target.closest('.drop-icon, .sidebar-item-control')) return;

            const anchor = event.target.closest('.item-anchor');
            const container = anchor?.closest('.sidebar-item-container');
            const label = getItemLabel(container);
            const routingLabel = getSidebarRoutingLabel(container);
            const parent = getParentLabel(routingLabel);
            const target = getAnchorRouteTarget(anchor) || DIRECT_MAPPING[routingLabel] || DIRECT_MAPPING[label] || getTargetFromUrl(anchor);
            const childSection = container?.querySelector(':scope > .sidebar-child-item');
            const hasChildren = !!childSection?.children?.length;

            if (isWorkspaceRoute(frappe.get_route()) && hasChildren) {
                toggleSidebarSection(container, event);
                frappe.route_options = null;
                rememberSidebarContext(routingLabel || label);
                frappe.set_route(getWorkspaceUrl(getWorkspaceName(container), true).replace(/^\/app\//, ''));
                return;
            }

            if (container?.dataset?.retailReportGroup === '1') {
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();
                if (childSection) {
                    const open = childSection.classList.toggle('hidden');
                    setDropIcon(container, !open);
                }
                return;
            }

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

            if (!target && !TOP_LEVEL_WORKSPACES.has(label) && !getParentLabel(routingLabel)) return;

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
            const target = DIRECT_MAPPING[routingLabel] || DIRECT_MAPPING[label];

            if (target) {
                anchor?.setAttribute('href', getTargetUrl(target));
                anchor?.setAttribute('data-retail-direct-link', '1');
                setAnchorRouteTarget(anchor, target);
            } else if (getParentLabel(routingLabel)) {
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

    function getSidebarItemLevel(item, pages) {
        let level = 0;
        let parent = item.parent_page;
        const seen = new Set();
        while (parent && !seen.has(parent)) {
            seen.add(parent);
            level += 1;
            const parentItem = pages.find(page => page.title === parent || page.name === parent);
            parent = parentItem?.parent_page;
        }
        return level;
    }

    function buildSidebarItem(item, pages) {
        const title = item.title;
        const displayTitle = WORKSPACE_DISPLAY_LABELS[item.name] || title;
        const children = pages.filter(page => page.parent_page === title);
        const target = item.route || DIRECT_MAPPING[title];
        const href = target ? getTargetUrl(target) : getWorkspaceUrl(item.name || title, item.public);
        const routeTargetAttribute = target
            ? ` data-retail-route-target="${escapeHtml(JSON.stringify(target))}"`
            : '';
        const container = document.createElement('div');
        container.className = 'sidebar-item-container retail-sidebar-item';
        container.dataset.retailLevel = getSidebarItemLevel(item, pages);
        container.setAttribute('item-name', displayTitle);
        container.setAttribute('item-workspace-name', item.name || title);
        container.setAttribute('item-parent', item.parent_page || '');
        container.setAttribute('item-public', item.public || 0);
        container.setAttribute('item-is-hidden', item.is_hidden || 0);
        if (item.parent_page) {
            dynamicChildToParent[item.name || title] = item.parent_page;
            dynamicChildToParent[title] = item.parent_page;
        }
        if (item.is_report_link) {
            container.dataset.retailReportLink = '1';
            dynamicReportToGroup[item.name || title] = item.parent_page;
        }
        if (item.is_report_group) {
            container.dataset.retailReportGroup = '1';
        }
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

        if (children.length) {
            const control = container.querySelector('.sidebar-item-control');
            const childSection = container.querySelector('.sidebar-child-item');
            const button = document.createElement('button');
            button.className = 'btn-reset drop-icon retail-drop-icon';
            button.type = 'button';
            button.innerHTML = getSmallDropIcon(false);
            button.addEventListener('click', event => {
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation?.();
                const open = childSection.classList.toggle('hidden');
                setDropIcon(container, !open);
            });
            control.appendChild(button);
            children.forEach(child => childSection.appendChild(buildSidebarItem(child, pages)));
        }

        return container;
    }

    function getSidebarItems() {
        sidebarItemsCache = null;
        if (!sidebarItemsPromise) {
            sidebarItemsPromise = frappe
                .xcall('frappe.desk.desktop.get_workspace_sidebar_items')
                .then(result => {
                    sidebarItemsCache = Array.isArray(result) ? result : result?.pages || [];
                    sidebarItemsPromise = null;
                    return sidebarItemsCache;
                })
                .catch(error => {
                    sidebarItemsPromise = null;
                    throw error;
                });
        }
        return sidebarItemsPromise;
    }

    function renderPersistentSidebar() {
        if (isWorkspaceRoute(frappe.get_route()) && !isItemFamilyPageRoute()) {
            removePersistentSidebar();
            syncDesktopSidebarClass();
            return;
        }

        const sideSections = getSidebarMountSections();
        if (!sideSections.length) {
            syncDesktopSidebarClass();
            if (sidebarRenderRetryCount < 8) {
                sidebarRenderRetryCount += 1;
                setTimeout(renderPersistentSidebar, 250);
            }
            return;
        }
        sidebarRenderRetryCount = 0;
        if (sideSections.every(section => section.querySelector('.retail-persistent-sidebar'))) {
            syncDesktopSidebarClass();
            return;
        }

        getSidebarItems().then(items => {
            if (isWorkspaceRoute(frappe.get_route()) && !isItemFamilyPageRoute()) {
                removePersistentSidebar();
                return;
            }
            getSidebarMountSections().forEach(section => mountPersistentSidebar(section, items));
            applyIcons();
            syncSidebarState();
            syncDesktopSidebarClass();
        }).catch(error => {
            console.error('retail_navigation: failed to render persistent sidebar', error);
            syncDesktopSidebarClass();
        });
    }

    function refreshSidebarEnhancements() {
        hideStandardHomeSidebarItems();
        applyDirectLinks();
        applyIcons();
        ensureWorkspaceDropIcons();
        syncSidebarState();
        renderPersistentSidebar();
        syncDesktopSidebarClass();
        applyWideTransactionLayout();
        upsertCurrentWorkTab();
    }

    function scheduleSidebarEnhancements(delay = 80) {
        clearTimeout(observerRefreshTimer);
        observerRefreshTimer = setTimeout(refreshSidebarEnhancements, delay);
    }

    function observeSidebarChanges() {
        const observer = new MutationObserver(mutations => {
            if (mutations.some(m => {
                if (!(m.target instanceof Element)) return false;
                if (m.target.closest('.retail-open-work')) return false;
                return m.addedNodes.length || m.removedNodes.length;
            })) {
                debugLog('retail_navigation: sidebar DOM mutated, reapplying icons');
                scheduleSidebarEnhancements();
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
                debugLog('retail_navigation: retry applyIcons after delay', delay);
                refreshSidebarEnhancements();
            }, delay);
        });
    }

    function scheduleMobileSidebarRender() {
        if (!isMobile()) return;
        [0, 80, 250, 600].forEach(delay => {
            setTimeout(() => {
                renderPersistentSidebar();
                refreshSidebarEnhancements();
            }, delay);
        });
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

    function init() {
        ensureRetailCss();
        injectRetailInlineCss();
        bindNavbarHomeToBusinessHome();
        bindViewWebsiteToRetailHome();
        redirectStandardHomeToBusinessHome();
        redirectItemFamilyListRoute();
        enforceAllowedRoute();
        waitForWorkspaceModule();
        waitForSearchFilters();
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
        bindWorkspaceSidebarToggle();
        bindSubmenuRouting();
        bindOpenWorkEvents();
        bindMobileSidebarToggle();

        if (window.frappe?.router?.on) {
            frappe.router.on('change', () => {
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
