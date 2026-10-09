# Celesta access profiles

Access control lives in the retail app and uses the standard ERP User, Role
Profile, Module Profile, Role Permission Manager and User Permission forms.
There are no replacement screens or layout changes. Existing assignment editors
become read-only for users who are not Super Admin.

## Installation

`retail.access_control.install` runs after installation and migration. It creates
missing default profiles, native document permissions for Super Admin and
Customer Administrator, and records a one-time Patch Log marker. It never creates
users, assigns an existing user to a profile, or changes passwords. Existing
profiles with matching names are preserved. Subsequent runs preserve edits and
deletions; defaults are not continuously enforced over administrator choices.

The **Administrator Role Profile** is the customer business profile. Its internal
customer role is `Customer Administrator`; Frappe's reserved automatic
`Administrator` role is never assigned to customer users.

The **Super Admin role** identifies a protected developer account, regardless of
its username or profile name. Assigning that role also ensures the native System
Manager role is present for native administration tools. The built-in account
named `Administrator` is always treated as Super Admin and remains the recovery
account. Keep its installation password with Celesta.

## Each customer installation

1. Sign in as the built-in Administrator.
2. Create your chosen developer user and assign the Super Admin profile.
3. Review the Administrator profile's business roles and its permissions.
4. Create native Module Profiles appropriate for this customer's modules.
5. Create the customer's user and assign the Administrator profile and the
   appropriate Module Profile.
6. Create staff users and assign the appropriate profile, module access and
   company/branch/warehouse User Permissions. Only Super Admin assigns access.
7. Review workflows, refund/discount limits and the existing POS Operator
   Privilege records before granting operational access.

Store Manager is a starting combination of sales, purchase, stock and POS manager
roles. Supervisor and Cashier start with POS User. Department Manager and Normal
User start with Employee and need the relevant job roles; ERPNext removes Employee
when there is no linked Employee record. Separate Sales, Purchase, Stock,
Accounts, HR and Van Sales User profiles are provided. These are editable presets,
not an automatic branch or approval policy. Existing profiles are retained even
if they differ from these defaults.

Native Module Profiles primarily control module visibility. POS and Van Sales
also have the retail app's existing server-side module gates. Use document roles,
User Permissions and workflows to enforce business access; a hidden workspace is
not a purchased-module licence boundary.

## Protected administration

Only Super Admin may edit roles, profiles, module assignments, user restrictions,
POS operator privilege assignments, scripts, workflows or protected technical
settings. A legacy System Manager account without Super Admin is also restricted.
Customer administrators can create unassigned users and maintain ordinary user
details and passwords through the standard User form. Super Admin assigns their
access. Role/module changes, including nested child records and native permission
RPCs, are checked on the server.

Developer accounts are excluded from permission-aware User lists, link searches
and mentions. Other users cannot open or modify those accounts or use customer
password-recovery requests to reset them. This does not erase audit authorship or
historical references from business documents, and is not invisibility from
server/database administrators. No security depends on keeping a username secret.

Full native document permissions are seeded for Super Admin at installation,
including higher field permission levels. Frappe operations hardcoded exclusively
to the literal built-in Administrator (for example impersonation) retain that
framework restriction; use the recovery account for those operations. New apps or
doctype additions need their permissions reviewed when installed. Existing native
permissions and later edits are not silently replaced.

## Verification

`retail.test_access_control` exercises real document saves, lists, profile
propagation, customer business access, protected accounts and RPC guards on the
test site. `retail.test_module_access` covers the existing POS/Van gates.

## Permission popups

Customer-facing permission popups never name the internal developer role.
Protected technical actions direct users to the software team. Business actions
direct users to their company administrator only when an enabled user with the
Customer Administrator role has the relevant document permission; otherwise they
direct users to the software team. Company administrators are not directed back
to themselves. Internal traces and required-role lists are omitted from customer
permission responses, including on development sites. Native status codes and
permission enforcement are unchanged.
