# Accounting defaults for future Retail companies

Retail initializes accounting defaults once, when a new non-group Company creates
its chart of accounts. The Company abbreviation and currency supply account suffixes
and currency; no customer/company name is hardcoded. ERPNext core is unchanged.

The initialization marker is installed by `after_sync` and `after_migrate`. These
hooks only add schema: they do not initialize or remap any existing Company. Deploy
the updated Retail app and migrate before creating new companies. Companies created
on an older release are deliberately not retroactively enrolled.

| Company field | Default purpose |
| --- | --- |
| Default Income Account | A named Sales/Sales Account/Retail Sales/Pos Sales/Shop Sales account; otherwise create Retail Sales |
| Default Expense Account | Cost of Goods Sold |
| Default Cash Account | Main Safe when it is an enabled, non-group Cash account in company currency; otherwise Cash |
| Default Bank Account | Bank, separate from card clearing |
| Default Receivable Account | Trade receivables/debtors |
| Default Payable Account | Trade payables/creditors |
| Default Inventory Account | Stock In Hand |
| Stock Received But Not Billed | Unbilled goods receipts |
| Stock Adjustment Account | Stock adjustments and non-opening stock receipts |
| Expenses Included In Valuation | Valuation expense clearing |
| Round Off Account | Rounding differences |
| Write Off Account | Authorized write-offs |
| Exchange Gain/Loss Account | Exchange differences |

Valid defaults selected by ERPNext are retained except its arbitrary income-account
selection and the preference for a valid Main Safe: new standard-template companies
use a specifically named sales account and a usable cash ledger.
Explicit defaults supplied by the caller and populated defaults from an Existing
Company chart remain authoritative. New fallback accounts are created through the
standard Account document, beneath an appropriate account-type group when uniquely
identified, otherwise beneath the corresponding root group. An incompatible account
with the same fallback name causes a setup error rather than silently reusing it.

Payment-mode mappings for each new company are:

| Mode of Payment | Default ledger (company suffix is automatic) |
| --- | --- |
| Cash | Main Safe when valid, otherwise the Company's cash account |
| Card | Manual Visa & Master Cards |
| Credit Card | Visa & Master Credit Cards |
| Cheque | Post Dated Cheques Received |
| Bank Draft | Bank Drafts Received |
| Wire Transfer | Company's Default Bank Account |

All non-cash modes use Bank type. Card, credit-card, cheque, and bank-draft ledgers
are separate Asset collection/clearing accounts, not evidence of money deposited
in a real bank. Wire Transfer uses the selected bank ledger; set the Company's real
bank account before trading and map extra bank-specific modes as needed.
If the bank account is changed later, update the Wire Transfer company mapping too.
An automatically selected card/cheque/draft clearing ledger is not accepted as the
initial default bank; explicitly selected site-owned accounts remain authoritative.

Missing modes and matching ledgers are created. Existing company mappings, disabled
modes, and modes with a different type are preserved. During initial Company setup
only, ERPNext's automatically generated Cash mapping follows a change from its cash
default to a valid Main Safe. Later custom mappings are never reset. Additional
wallet/card-provider modes require their own site-selected mappings.

New POS Profiles for enrolled companies fill blank income, expense, cash-change,
write-off, cost-center, and write-off cost-center fields from Company. Existing POS
Profiles and supplied values are not overwritten. Payment-method selection, taxes,
warehouses, item/group/brand-specific ledgers, and counter configuration remain under
the site's control. Item-level accounts are not stamped with company defaults, so
ordinary fallback remains dynamic and special item routing remains possible.

## Setting a site's own ledgers

Change Company defaults and, where needed, the POS Profile accounts. Specific Item,
Item Group, and Brand company rows can supply their own income and expense accounts.
Change payment mappings under Mode of Payment → Accounts → company row. Warehouse
accounts can override the Company's inventory account. Existing transaction rows
retain their saved mappings. Re-running migrations does not reset these choices.

## Completing accounting setup

Correct ledger defaults do not establish opening balances, physical stock quantities,
valuation accuracy, tax registration/rates, or bank settlement. Before trading:

- Record and verify opening inventory and balances; ERPNext's new-site default keeps
  negative stock disabled. This feature does not change the existing global setting.
- Configure applicable sales/purchase tax templates, tax categories, item tax rules,
  and POS Profile tax selection for the company's jurisdiction and registration.
- Set real bank and additional payment-mode accounts, reconciliation, and any card
  fees; do not treat card collection as an immediate bank deposit.
- Verify representative cash, card, credit, purchase, and return transactions.

No tax rate is hardcoded and no submitted invoice, GL entry, stock ledger, existing
company, or historical income classification is rewritten by this feature.

## Validation

`retail.tests.test_accounting_defaults` covers the one-time Company hooks, income
selection, independent company payment mappings, preservation of user overrides,
new-profile inheritance, Main Safe validation, and submitted sales for all six
payment modes with stock received first.
Tests require the installed marker schema and roll back their business fixtures.
