# Unified app login

POST `/api/method/retail.api.auth.login`

Send JSON with `Content-Type: application/json` and retain the ERP session cookie for subsequent calls:

```json
{"usr": "user@example.com", "pwd": "password"}
```

No module parameter is required or trusted. Optionally set **App Module** on the User's assigned **Role Profile**. This explicit value determines `app_module`, even when the profile also contains roles for supporting operations. If the field is blank, exactly one matching functional module can be inferred:

| Roles in assigned Role Profile | Module |
| --- | --- |
| Sales User / Sales Manager | sales_order |
| Van Sales User / Van Sales Manager | van_sales |
| Purchase User / Purchase Manager | purchase |

A renamed/custom profile keeps its App Module setting. Standard Sales User, Van Sales User and Purchase User profiles receive matching defaults; existing Van Sales and VSDriver profiles receive van_sales. Existing nonempty settings are preserved. Missing or ambiguous module classification returns `app_module: null` and does not block login. Administrator/Store Manager profiles are not automatically assigned a module. Extra roles directly assigned to a User do not change classification. Login requires effective Sales or Van Sales area access, or Purchase Order read permission, independently of classification. Classification grants no permissions. Van assignment resolution runs only for a classified Van Sales account with Van Sales access; transaction endpoints retain their permission and assignment checks.

Successful Sales Order example (all successful modules use the same keys):

```json
{
  "message": {
    "status": "Success",
    "user": "user@example.com",
    "app_module": "sales_order",
    "sales_person_id": "SP-1",
    "sales_person_name": "Salesperson",
    "roles": ["Sales User"],
    "permissions": {"Sales": true, "Sales Orders": true},
    "driverid": null,
    "vanid": null,
    "warehouse": null,
    "organizationid": null,
    "sessionid": null
  }
}
```

Native top-level login metadata can also be present. Van logins populate the driver, van, organization and active business session fields using the existing assignment resolver; they do not open a Van Session. Other modules return null in those fields. `sessionid` is a business Van Session ID, never the authentication cookie. Purchase Order read permission also permits login; this does not introduce new purchase business APIs.

Native password reset, two-factor authentication, licensing, login throttling, and disabled-user checks remain active. Incomplete native authentication returns `message.status = AuthenticationRequired` and must not be treated as success. Native authentication/authorization errors retain their normal HTTP error responses. Follow the existing ERP authentication challenge flow when required.

Both this endpoint and native `/api/method/login` are classified into the Sales Order API Log or Van Sales Sync Log by the account's Role Profile, including failed attempts for identifiable accounts. Credentials are redacted. Unknown, unmapped and multi-module accounts are not copied into either module log; native authentication logging remains available. Purchase has no dedicated module login log yet.

Existing native login and `driver_login` endpoints retain their request/response contracts. Existing driver-specific calls continue to appear in Van Sales logs. Move both apps to this endpoint to obtain the shared response structure. No User assignments or historical logs are rewritten.

`message.permissions` is a flat object of visible Retail sidebar display names
with `true` values, using the same selection, module and role filters as Desk:

```json
"permissions": {
  "Business Home": true,
  "Sales": true,
  "Sales Orders": true,
  "Van Sales": true,
  "Van Fleet": true
}
```

Only allowed, visible menus are included. Duplicate display names appear once.
There is no `retail_sidebar` wrapper, operation detail, or separate `sales` /
`van_sales` boolean. Internal login and van-assignment checks still use the existing
area gates. This login-time snapshot is for menu visibility; server authorization
continues to enforce document operations. Native and legacy login responses are
unchanged.
