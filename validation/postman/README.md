# Manual offline POS test in Postman

Use **retail-test.localhost**, not your live site. These requests create real records in the test database. No transactions have been sent by preparing these files.

## Get started

1. Import `offline-pos-manual.postman_collection.json` and `retail-test.postman_environment.json` into Postman.
2. Select the **Retail Test — Offline POS** environment.
3. Enter the existing API key and secret for `pos.api@arabscale.com` into `api_key` and `api_secret`. Keep them in Postman; do not send them in chat.
4. `base_url` is `http://127.0.0.1:8000` when Postman runs on the ERP computer. If accessing it from another computer, use that ERP computer's address and port. The collection's Host header selects `retail-test.localhost`.
5. Open **01 — Check connection** and click **Send**. The reply should show `message.status: "OK"`.
6. Run each numbered request manually. Read the reply and Postman's test results before continuing. Do not run the whole collection automatically.

The collection uses Karama, `counter01` / `T01`, cashier `E-6` (Maya), customer `C-1` and item `I-1` (Water). It later transfers to `counter02` / `T02`.

## What to expect

| Steps | What you are checking |
|---|---|
| 01–02 | Connection works; the cashier and counter are free. |
| 03 | Bill waits because its opening has not arrived. `Failed` with `BlockedDependency` is the expected result. |
| 04–05 | Opening succeeds, then the exact same saved bill succeeds. ERP returns its own numbers. |
| 06 | Sending the bill again returns `duplicate: true` and the same invoice number. |
| 07 | Changing the amount under the same reference is rejected. A reference conflict is expected. |
| 08–10 | Credit sale of AED 10.50; collect AED 5, leaving AED 5.50 due; take an AED 5 deposit. |
| 11–13 | Cash in AED 10, cash out AED 5, then refund the original AED 10.50 cash sale. |
| 14–16 | Release counter01, continue the same shift at counter02, then close the shift. |
| 17 | Check the closed shift's cash figures. See the known issue below. |
| 18 | Recover all saved results, including opening numbers, as if replies had been lost. |
| 19 | Preview the branch day closing and review totals. |
| 20–21 | Submit and retry Day Close. Only proceed after the cash check passes and all branch work is finished. |

Starting cash is AED 100. After all listed activities, counted cash should be **AED 115**:

`100 + 10.50 sale + 5 collection + 5 deposit + 10 cash in − 5 cash out − 10.50 refund = 115`

## Known issue to check

The current shift expected-cash formula includes invoice payments and cash movements but omits separate customer collections and deposits. Step 17 deliberately checks the correct total of AED 115 and zero difference. It is expected to expose an AED 10 difference in this scenario. **Stop before submitting Day Close if this check fails.** This needs correction before treating cash reconciliation as ready for rollout.

## Keep the test references

Postman creates the references once and saves them as collection variables. They stay unchanged when you press Send again. Opening and sale requests send external references only; they never need ERP shift/session numbers.

Do not clear `run_id` or change saved dates to retry a request. Clear `run_id` only for a genuinely new test, after the previous shift is finished, using an open business date. Previously posted test records remain in ERP.

In ERP, search **POS Cashier Shift**, **POS Counter Session**, **POS Invoice**, **POS Cash Movement**, **Payment Entry**, and **POS Sync Log**. Match them using the returned numbers and external references. The sale, return and each payment should appear only once.

Postman verifies the ERP API flow. A later test in the actual .NET POS is still needed to prove that billing, saving work and reconnecting function while the device is offline.

If a step fails unexpectedly, share its request number and response, with credentials removed.
