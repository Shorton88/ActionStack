# Deployment and operations

## ActionStack 0.4.0 installation

Install `splunk_actionstack-0.5.1.spl` as a new app. This release adopts the ActionStack namespace before production deployment; it is not an in-place upgrade of the earlier prototype. App IDs, REST routes, capabilities, collections and SOAR custom fields use the new names documented below. The Splunk menu shows **ActionStack** with the existing layered icon.

## 1. Search head cluster installation

Target: Splunk Enterprise 10.2.4 on a healthy search head cluster with KV Store enabled; SOAR 8.6 on premises. Use an intake test label with no active playbooks for initial acceptance.

1. Run `npm ci`, `npm test`, and `npm run package` on a build machine.
2. Back up the current app configuration and relevant KV collections using your existing Splunk backup procedures.
3. On the **SHC deployer**, extract the `.spl` archive into `$SPLUNK_HOME/etc/shcluster/apps/`. Its top-level directory is `splunk_actionstack`.
4. Review the bundled `authorize.conf`. It grants catalog and submission capabilities to `user`, administration to `admin`, Workspace creation can provision namespace viewer/user/admin roles. The bundle no longer defines generic author/publisher roles. If your authenticated users do not inherit `user`, grant the two baseline capabilities through your centrally managed role configuration.
5. Apply the SHC configuration bundle using your established deployment process, including any required rolling restart. The app's `deployer_push_mode = full` controls the shipped app content; runtime form data is in KV Store.
6. Verify the same app version, REST registration, KV configuration, and Python runtime on every member. `restmap.conf` declares `python.version = python3.9` for AppInspect and older releases, plus `python.required = 3.9, 3.13` for newer releases (which takes precedence). The local tests ran on Python 3.14; run them with the actual installed runtime before release.
7. Open `/en-US/app/splunk_actionstack/actionstack` through Splunk Web. Adapt the locale/root prefix for your environment. Use HTTPS for Splunk Web to protect sessions and form contents. Version 0.1.1 also supports ID generation on HTTP intranet origins: it uses getRandomValues and a server-side SHA-256 fallback when SubtleCrypto is unavailable.

Example operator checks on each member:

```sh
$SPLUNK_HOME/bin/splunk btool restmap list script:actionstack --debug
$SPLUNK_HOME/bin/splunk btool collections list --app=splunk_actionstack --debug
$SPLUNK_HOME/bin/splunk btool authorize list --debug
```

Follow Splunk's [SHC deployer guidance](https://help.splunk.com/en/splunk-enterprise/administer/distributed-search/10.2/update-search-head-cluster-members/use-the-deployer-to-distribute-apps-and-configuration-updates). This repository does not deploy to your cluster automatically.

## 2. Connection setup

The initial **Setup wizard** guides an app administrator through workspace creation and connection setup. You can revisit the connection from **Settings**. Enter:

- The final HTTPS origin of SOAR, e.g. `https://soar.internal.example`. Redirects, URL credentials, and URL paths are rejected.
- A dedicated SOAR automation token. Restrict the identity to reading/creating containers and artifacts in the intended labels. Do not grant administration or playbook editing solely for intake.
- An event label prefix (for example, `actionstack_`). Leave empty to list all available SOAR labels.
- An originating instance name for attribution.
- An optional source asset ID, if you use an existing intake/source asset in SOAR.
- Optional **Ignore certificate validation** checkbox for self-signed or untrusted SOAR certificates. Off by default. When enabled, HTTPS is still used but certificate-chain and hostname verification are skipped for this connection; it does not install or pin a certificate. Previously saved CA chains remain available when validation is re-enabled.
- Per-request timeout (default 15 seconds).

Save and test the connection. The connection test reads the documented `/rest/container_options` endpoint and lists available labels. It confirms connectivity, authentication and read access using the saved certificate-validation setting. There is no separate intake-test button: to verify event and artifact creation, publish a form using an available label with **Allow SOAR automation on delivery** off, then submit that form.

Credentials use `storage/passwords` in the app namespace, with an opaque reference in shared settings. Verify that each member can resolve the reference after SHC replication and failover. Missing credentials fail closed. Do not deploy plaintext tokens in app files or distribute them through browser storage.

Connection changes apply to new submissions. Existing submissions retain their saved connection snapshot (including certificate validation) for retries and activity reads.

In Form builder → SOAR mapping, set the label and tags to values agreed with the SOAR owner. Labels must already exist. Publishing validates the definition, connection, and label against SOAR’s container options; SOAR also enforces label access on ingestion. **Allow SOAR automation on delivery** defaults off. When enabled, only the final submission artifact permits automation; container creation always sets it false. The app never explicitly invokes a playbook.

Starting in 0.1.4, new submission artifacts inherit the form label as well. SOAR selects automatic playbooks by the container label; matching artifact labels are for consistent classification. For automatic execution, enable **Allow SOAR automation on delivery**, publish the form, and configure an active playbook for that container label. Existing artifacts and retries of older requests retain their original labels.

## 3. RBAC

| Capability | Permission |
| --- | --- |
| `actionstack_use` | Access the endpoint/catalog |
| `actionstack_submit` | Submit and retry own permitted requests |
| `actionstack_edit` | Create/edit permitted drafts |
| `actionstack_publish` | Publish/archive permitted forms; also requires edit |
| `actionstack_read_team` | Read receipts for forms whose team roles match |
| `actionstack_audit` | Read redacted audit metadata |
| `actionstack_admin` | Configure connection; app-wide administration |

Form ACLs further restrict view/submit/edit by Splunk role. Empty view/submit lists allow holders of the relevant capability. Empty edit lists allow all editors. Empty team lists grant no team visibility. The blocking form retained from older installations is editable by administrators. Fresh production installations use the setup wizard and start without a published example. Inherited roles are expanded for form checks; effective capabilities come from Splunk's authenticated current-context endpoint.

The handler resolves user identity with the user's token, then performs narrowly defined storage operations with Splunk's system token. The browser cannot choose the username, capabilities, routing, approval metadata, credential, or arbitrary remote URL.

Back-end KV collections and stored credentials are restricted to administrators. **Test direct KV and credential access with an ordinary user**, in addition to UI checks. Custom app administrators can operate through the handler without broad direct KV access. Do not publish unrestricted KV lookup definitions for submission content.

Splunk Web's raw REST proxy supplies session authentication and CSRF protection. The UI sends `X-Requested-With: XMLHttpRequest` and the current instance’s `X-Splunk-Form-Key` with same-origin session cookies. Verify rejection of a POST without a valid form key through Splunk Web. Management-port API clients require their own authenticated Splunk token. Keep management access within your existing network policy.

## 4. Data and API

Application base endpoint: `/services/actionstack` on splunkd; browser traffic uses the locale-aware `/splunkd/__raw/services/actionstack` proxy.

| Method/path | Purpose |
| --- | --- |
| GET `/context` | Trusted user and capability context |
| GET `/forms` | Role-filtered published catalog |
| GET `/admin/forms` | Editable latest drafts/versions |
| POST `/admin/forms/save`, `/admin/forms/publish` | Immutable revision update with expected revision |
| GET `/admin/forms/{id}/versions` | Authorized revision history |
| POST `/admin/forms/{id}/archive` | Archive with expected revision |
| GET/POST `/settings` | Admin-only connection configuration; token never returned |
| POST `/settings/test` | Read-only connection check |
| POST `/submission-fingerprint` | Authenticated hash-only fallback for browsers without SubtleCrypto; no delivery |
| GET/POST `/submissions` | Authorized receipts / new intake |
| GET `/submissions/{id}` | Authorized receipt |
| GET `/submissions/{id}/activity` | Authorized read-only SOAR playbook/action summaries |
| POST `/submissions/{id}/retry` | Original requester retry with current permission check |
| GET `/audit` | Last 1,000 audit metadata records for audit capability holders |

Responses wrap success in `data`; errors contain `error` and optional field errors. Maximum request body is 256 KB. Delivery attempts are limited to **10 per user per fixed minute across the cluster**, including retries; reading an existing receipt uses no slot. Add normal authentication and request-rate controls at your Splunk Web/reverse-proxy boundary.

KV collections: `actionstack_forms`, `actionstack_submissions`, `actionstack_settings`, `actionstack_locks`, `actionstack_ratelimits`, `actionstack_audit`, `actionstack_workspaces`, `actionstack_validation_policies` (legacy), `actionstack_favorites`. No filesystem queue or automatic background worker runs on members. Audit records contain actor, UTC time, event type, and entity ID, without raw inputs or secrets. Audit records are mutable by Splunk administrators; this is not a tamper-proof audit archive. Forward/export them into your restricted audit system if that guarantee is needed.

## 5. Staging acceptance

Complete these on the actual versions before wider use:

1. Check the persistent-handler request shape (`session.authtoken`, `system_authtoken`, `path_info`, and raw JSON payload), response headers, CSRF handling, and local app asset loading.
2. Log in as an ordinary user. Confirm only permitted forms/receipts are visible; settings, builder APIs, other users' receipts, direct KV, and passwords are inaccessible. Repeat with inherited roles and a scoped team reader.
3. Configure a test label, keep automation off, and submit `192.0.2.42`, `example.test`, a 40-character SHA-1, and a 64-character SHA-256. Check canonical inputs, label/tags, username/roles, UTC time, source identifiers, and both remote IDs.
4. Check every duration. Forever must contain `approval_required: true` and `soar_playbook`; no approval or block is performed by this app.
5. Repeat a POST with the same key/body through two different members. Confirm one local submission and one matching SOAR event/artifact. Change the body under the same key and confirm HTTP 409.
6. Interrupt delivery after container creation and after a remote POST whose response is lost. Retry and verify reconciliation without duplicate event/artifact creation. Check data returned by SOAR GET endpoints includes the namespaced envelope/CEF used for reconciliation.
7. Edit one form from two members; the stale writer must receive 409. Save a draft while the older published form remains usable; publish, restore, and archive.
8. Exercise member/captain/KV-primary failover while records are created. Verify acknowledged unique inserts and lock ownership remain consistent. Local concurrency tests are not a proof of distributed failover semantics.
9. Verify stored credential replication and decryption on every member. Rotate credentials and confirm the behavior below.
10. Only after intake succeeds, enable automation on a dedicated test form and confirm your SOAR configuration triggers at the expected final-artifact boundary. Receipt success still means delivery, not playbook success.

Run AppInspect and your normal security/load checks as part of this staging gate. They have not been run against a live instance in this workspace.

## 6. Delivery recovery

The request is persisted before network delivery. `submitted` means both required remote IDs were confirmed. `pending`, `submitting`, `failed`, and `needs_attention` do not claim automation success.

### Missing SOAR label

The starter form uses `automation_requests`. That label must exist in SOAR even when the automation identity has administrator permissions. If the connection check lists only `events`, either create `automation_requests` in SOAR and retry the failed request, or change the form's SOAR mapping to `events`, publish, and make a new submission. Retrying an existing request preserves its original label. Keep automation disabled for intake testing.

Version 0.1.3 checks label availability before creating an event, includes the original label in submission details, and provides sanitized SOAR rejection details instead of a generic permissions hint. The connection check also reports published forms with unavailable labels.

### Retrying and reconciling requests

- Use **Submissions → My submissions → Retry delivery** for a failed/uncertain request. Only the original requester can initiate retries; current form permissions are rechecked. Retries use the original published schema, inputs, identity, and destination snapshot.
- Browser retries retain a payload-bound idempotency key after an ambiguous response. A receipt can also be recovered through Submissions. A new deliberate submission after receipt creates a new request.
- Each delivery holds a unique shared lock at `_key = delivery:<submission-id>`. Locks do not expire automatically: a timed lease could let a second member send while the first is still running.
- After a process crash leaves an abandoned lock, the Splunk administrator must quiesce this endpoint on **all** members and stop/drain its persistent handlers. Verify no delivery can still run, inspect the submission and SOAR source identifiers, back up the relevant records, then remove **only that lock key** from `actionstack_locks` through the admin KV API. Resume the endpoint; the original requester can retry. Never clear a lock just because its timestamp is old.
- Do not manually mark a receipt submitted or overwrite a stored remote ID without verifying both objects and their canonical data. Mismatched/duplicate source identifiers stop delivery for administrator investigation.
- Connection snapshots pin the original origin, CA, source asset, and secret reference. Credential rotation creates a new reference for future submissions; pending requests retain their original reference. Keep the old credential valid while those requests are reconciled, or resolve them during a controlled maintenance window. Revoking the old token makes their retries fail safely. The release has no automatic credential rebinding tool.

## 7. Retention and scale

This is a modest-volume initial release: catalog and history operations scan bounded KV datasets. Any one list scan reaching 50,000 records fails closed rather than returning silently incomplete authorization data. The UI shows the latest 200 authorized submissions. Delivery is synchronous; configure frontend/proxy timeouts for several outbound requests, or use receipts after an interrupted response.

Set an operational retention policy before broad use:

- Export/back up completed receipts and audit records under your organization's data policy, then remove eligible records through an administrator-only maintenance process.
- Preserve unfinished submissions, referenced form revisions, connection snapshots and their credentials, and any active delivery locks.
- Prune `actionstack_ratelimits` records with `minute` older than the current UTC epoch-minute minus 1,440 (24 hours). Filter by numeric minute, never remove current-minute slots. These records contain hashed-user keys and minute only. Schedule maintenance in your existing operations tooling; this release has no automatic retention scheduler.
- Coordinate SOAR and local retention. Deleting an idempotency receipt permits a later replay of the original key to be treated as new; keep receipts for at least the maximum accepted replay period, and retain the corresponding SOAR source identifiers.
- Do not clear form records to reset setup: receipts and historical versions depend on them. Production installs no longer seed a default form when the collection is empty.

Upgrade plan for higher volume: indexed/paginated queries for receipts and audit, explicit idempotency tombstone retention, a supported single-owner retry service, and load/failover tests.

## 8. Splunk Web CSRF errors during connection setup

A console response of **401: Splunk cannot authenticate the request. CSRF validation failed** means Splunk Web rejected the POST before the app could contact SOAR.

1. Deploy app version 0.1.2 or later to every SHC member and hard-refresh the page so the new JavaScript loads.
2. If the session is stale, sign in again. The app needs a valid CSRF cookie from that same Splunk Web session.
3. Retry **Save connection**, then **Test saved connection**. The test uses the saved settings.
4. If the rejection remains, inspect the browser Network entry locally: it should send `X-Requested-With: XMLHttpRequest`, a nonempty `X-Splunk-Form-Key`, and session cookies. The form key must match the current instance's CSRF cookie. Check that your reverse proxy preserves these headers and cookies. Avoid sharing cookie or token values in screenshots/logs.

CSRF protection stays enabled. The request convention follows [Splunk's documented JSON AJAX headers](https://help.splunk.com/en/splunk-cloud-platform/collect-stream-data/install-and-configure-splunk-stream/8.0/splunk-stream-rest-api/splunk-stream-rest-api-reference).

## 9. Approval rules and automation status (0.1.5)

**Form builder → Approvals** exposes the policy previously built into the starter template. Choose never, every request, or when any condition matches; conditions compare dropdown, radio, or checkbox values. The original block-object form still requires SOAR-playbook approval for `duration = forever` unless an administrator explicitly changes and publishes its rules. Other legacy forms default to no approval. An untouched optional checkbox is treated as false; hidden fields cannot match. Invalid/deleted rule fields prevent saving or publishing until corrected.

Approval is always handled by the SOAR playbook, which may use Teams or another approval channel. The backend evaluates the published rules after field validation and supplies `approval_required` and `approval_policy` in the existing event/CEF contract. These rules are intake metadata: downstream playbooks must branch on that metadata and enforce approval before any action. A successful Teams action does not necessarily mean approval was granted, so the status panel never infers an approval decision from action success.

Submission receipts poll `GET /submissions/{id}/activity` every 30 seconds after the previous request finishes while open and visible. Polling pauses in hidden tabs and stops when the receipt closes. Manual Refresh is available. Reads are authorized using the same owner/team/admin receipt rules, use the submission's original saved connection, and do not retry delivery or launch automation. The existing rate-limit collection enforces a separate 20-refreshes/user/minute budget across cluster members.

The adapter reads `/rest/playbook_run` and `/rest/action_run` with `_filter_container=<saved event ID>`, `pretty`, and bounded page sizes. It verifies each returned record belongs to that event and returns run identifiers, display names, status, and update timestamps. It also returns bounded connector summaries and, as of 0.2.1, result data previews described below. Playbook names use `_pretty_playbook` when present, otherwise the numeric playbook ID. Logs and action parameters are excluded. SOAR token permissions must permit these reads. The UI distinguishes no runs, permission/unavailable errors, unknown states, and truncated results (latest 25 playbooks / 100 actions). Event activity can include manual runs, reruns, and multiple playbooks; it is not guaranteed to be attributable only to the submitted artifact.

On upgrade, verify status read access with a submitted event and an active playbook. Check pending/running, success, failure, and denied read access. This implementation follows the SOAR 8.6 REST contract; the operator's recent playbook-settings screenshot showed platform version 8.7.0.232, so validate the returned fields and permissions on that actual installation.

Local UI QA: `http://127.0.0.1:5173/qa/activity.html` renders fictional running, failed, and partially unavailable results using the production status component. The fixture is not included in the Splunk package.

API references: [SOAR query filters and related records](https://help.splunk.com/en/splunk-soar/soar-on-premises/rest-api-reference/8.6.0/using-the-splunk-soar-rest-api/query-for-data), [playbook run states](https://help.splunk.com/en/splunk-soar/soar-on-premises/rest-api-reference/8.6.0/run-playbook-endpoints/rest-run-playbook), and [action run states](https://help.splunk.com/en/splunk-soar/soar-on-premises/rest-api-reference/8.6.0/run-action-endpoints/rest-run-action).


## 10. Workspaces, request validation, and lookup fields (0.1.6)

Deploy the **complete app**: the new `actionstack_workspaces` and `actionstack_validation_policies` KV collections must exist on every member. Configuration is shared through KV Store; no member-local workspace files are used. Immutable unique revision keys reject concurrent edits. Back up these collections with forms. Do not prune policy/workspace revisions without retaining the latest record for each ID.

**Team workspaces:** app admins can create, edit, archive, and restore workspaces from the sidebar. Empty membership roles allow all app users; otherwise at least one effective Splunk role must match. Form ACLs also apply. Admins can move forms between workspaces in the form editor. Existing forms default to `security`. Archived workspaces accept no new requests; owners retain historical receipts. Team receipt readers must also belong to the receipt's saved workspace. Select a workspace in the sidebar or top bar (All workspaces includes authorized historical receipts after membership changes); the selection is stored locally per username. Workspaces group forms within this app and are not separate Splunk apps or SOAR tenants.

**Field validation (0.2.0):** select a field in **Form builder → Build** and use its Validation section. Legacy policy management is removed from the UI. Existing policy snapshots migrate to field checks when editing; see section 11. Approvals remain in their own tab.

**Lookup fields:** add Lookup · single value or Lookup · multiple values in the field palette and configure, for example:

```spl
| inputlookup identity_lookup_expanded
| eval display_name=coalesce(firstName . " " . lastName, identity)
| table identity display_name
```

Set **Value field sent to SOAR** to `identity` and **Display label field** to `display_name`. Keep both fields in the final results. Suggestions match either field, while submission revalidation checks only the selected underlying value. Existing single-column configurations continue to work.

The search must start with `inputlookup`. Supported transformations: `eval`, `where`, `search`, `fields`, `table`, `rename`, `dedup`, `sort`, `head`, `tail`, `fillnull`, `rex`, `regex`, `spath`, `stats`, `eventstats`, `streamstats`, `mvexpand`, `makemv`, `mvcombine`, `nomv`, `convert`, and `replace`. Macros, subsearches, index searches, custom commands, and write commands are not supported. Set the app namespace containing the shared lookup (for example, `search` or the owning app). Both CSV and KV-backed lookup definitions can be used through `inputlookup`. The handler uses the signed-in user's session token for search; privileged storage credentials are never used for lookup execution. Ensure each requester has Splunk search capability, access to that app, and read permission on the lookup definition/file or collection. This feature does not grant search or lookup permissions.

Search starts after 3–10 characters and 50–1000 ms of idle typing (defaults 3/50), with one in-flight request per field and up to 25 case-insensitive prefix matches. No periodic full-lookup polling occurs. Results are narrowed by the server, not downloaded wholesale. Search jobs have a five-second execution limit and are deleted after reads; incomplete/failed jobs fail closed. Large CSV lookups may still require scans; use suitable lookup definitions and increase typing delay if needed. Each user has a shared cluster budget of 60 lookup searches/minute, including exact selection checks at submission. At most five lookup fields per form. Preview searches run as the author; published form searches run as the requester. Ordinary clients cannot replace the stored search configuration. Local demo searches use fictional example.test identities only.

Added endpoints:

| Endpoint | Access / purpose |
| --- | --- |
| GET `/workspaces` | Accessible workspace list |
| GET `/admin/workspaces`, POST `/admin/workspaces/save` | App admin workspace management |
| GET `/validation-policies` | Legacy compatibility endpoint |
| GET `/admin/validation-policies`, POST `/admin/validation-policies/save` | Legacy compatibility; current UI uses field checks |
| POST `/lookups/options` | Published form/field/version reference; submit and workspace access required |
| POST `/admin/lookups/preview` | Form authors: test a permitted lookup configuration as themselves |

**Action results:** receipts also read `/rest/app_run` filtered to the saved container. The UI shows separate, initially collapsed sections for action-result `summary` and `data` with their reported status, grouped beneath the corresponding action run. Results containing only `data` are included; an empty data array displays `[]`. If the list omits result data, the adapter uses the documented `/rest/app_run/{id}/action_result` endpoint after checking container membership. A refresh reads up to 100 app-run records, with at most five fallback result reads (five results each); additional results are marked omitted. Each action displays at most five results. Summary strings, nesting, and size are bounded. Data previews limit strings to 600 characters, lists to 25 entries, dictionaries to 30 keys, and nesting to five levels. Oversized previews show a 16,000-character prefix of sanitized JSON. A 256,000-character serialized data budget per refresh replaces further previews with small omission notices. The UI flags shortened data and directs users to SOAR for complete results. Known token values and credential-like keys are redacted; logs and action parameters are excluded. The same receipt owner/team/admin ACL applies to result data. Result-read failures leave action statuses available. The SOAR integration identity needs app-run/action-result read access in addition to the existing run permissions. Test against your deployed SOAR version; local tests use simulated responses.

Primary buttons have a glow/shine hover treatment and respect reduced motion. Standard `static/appIcon.png`, `appIcon_2x.png`, and alternate variants are included. Splunk may cache menu icons until the app bundle and browser cache refresh.

Staging checks: create a role-restricted workspace and verify denial for a nonmember; publish field validation and confirm invalid inputs create no SOAR event; test the identity lookup as an ordinary requester and with denied lookup access; confirm separate collapsed summary/data sections, including actions without summaries, and verify that denied receipt access also denies result data; verify switching and menu icons on each search head through the load balancer.

References: [Splunk inputlookup](https://help.splunk.com/en/splunk-enterprise/spl-search-reference/10.4/search-commands/inputlookup), [SOAR action-result summary API](https://help.splunk.com/en/splunk-soar/soar-on-premises/rest-api-reference/8.6.0/run-action-endpoints/rest-run-action).


## 11. Field validation and catalog upgrade (0.2.0)

Deploy the **complete app bundle** through the SHC deployer, including `actionstack_favorites` in collections.conf and `bin/actionstack/field_validation.py`. Keep existing policy collections and revisions for historical data and upgrade compatibility. Hard-refresh Splunk Web on all members.

### Field validation

Select a field in **Form builder → Build**, then add validation in its properties. Each check has Validation type, Value and Message to user. Required remains a field setting. Field IDs support camelCase such as `emailAddress`.

| Check | Example value | Meaning |
| --- | --- | --- |
| Equals | `approved` | Exact case-sensitive equality |
| Not equal | `root` | Reject that exact value |
| Like | `*@example.test` | Entire value matches; `*` is any text, `?` is one character |
| Not like | `test-*` | Reject matching values |
| Regex | `(?i)INC-[0-9]+` | Python regex matching the whole value |

Numeric/checkbox equality uses typed values (enter a number or true/false). Text-list, multi-lookup and multiple-choice checks apply to every selected item. Empty optional and hidden fields are skipped. All applicable checks must pass. Invalid patterns or field references prevent saving. Regex patterns are limited to 512 characters; wildcard values to 200. Matching runs in the existing isolated worker with a one-second timeout and fails before any receipt/event is created. Required, type, choice and length checks also apply. Verify worker execution with Splunk's installed Python runtime on each member.

When opening an older form, the editor moves its saved policy checks onto their fields and removes the policy reference. Required rules migrate to Required settings; existing conditional requirements and checks retain their conditions. Existing block-object checks, normalization, approval metadata and SOAR projections are preserved. Published revisions and pending receipts are not rewritten. Republish to activate field-owned checks; subsequent policy changes cannot affect that form. No separate policy permissions are needed for editing field checks.

### Multi-value inputs

Choose Text · multiple values for Enter-to-add chips, Lookup · multiple values for several selected lookup results, or Lookup · single value for one selection. Up to 25 unique non-empty values of at most 200 characters are accepted. Text values are trimmed; lookup values retain their exact spelling. Uncommitted text prompts the user to add/select it before review.

On submission, all selected values for a lookup field are verified together in one bounded exact-match search, using the signed-in user's permissions and the stored lookup configuration. One batch consumes one lookup budget slot. If any value is missing or results are incomplete, no receipt/event is created. Arrays remain arrays in container and artifact custom data. CEF convenience values are JSON strings; see SOAR_EVENT_CONTRACT.md.

### Catalog and favorites

The home page has category/search filters, 12-item pagination and a Favorites view. Favorite stars persist per authenticated Splunk username in the shared `actionstack_favorites` collection. Favorites never grant access: form and workspace permissions are rechecked on reads/writes. Test the same favorite from two cluster members and with a second user.

GET `/favorites` reads the caller's visible favorites. POST `/favorites` accepts only `form_id` and boolean `favorite`. The caller cannot nominate another username.

### Delete and restore

The builder's Delete action moves a form to Trash after a confirmation. It disappears from the catalog and normal form list and cannot accept new requests or delivery retries. Previously accepted in-flight deliveries may finish. Existing receipts, revisions and remote SOAR events remain intact. Trash offers Restore; restored forms stay unpublished, including after draft saves, until explicitly published.

POST `/admin/forms/<id>/delete` and `/restore` require publish capability, edit access, workspace access and the current `expected_revision`. Immutable revision inserts reject conflicting edits across cluster members. Deletion/restoration are audited. Deletion is reversible and does not purge stored data. Retention maintenance must preserve the newest state marker or an old form could reappear.

### Acceptance checks

- Save/publish per-field regex and wildcard checks; reject invalid values without an event.
- Verify migrated block checks and Forever approval in the starter form.
- Submit multiple text and lookup values; verify arrays on both container and artifact.
- Favorite across members; verify user isolation and access revocation.
- Delete a test form, confirm it is unavailable, restore and save a draft, then explicitly publish. Confirm historical receipts remain available throughout.


## 12. Workspace setup and preferences upgrade (0.3.0)

Deploy the **complete 0.3.0 bundle** through the SHC deployer, including `actionstack_preferences` in `collections.conf` and `bin/actionstack/workspace_roles.py`. Apply your normal rolling-restart procedure for persistent Python handlers, and hard-refresh Splunk Web. The new preferences collection uses the same administrator-only direct KV ACL as the other app collections. Back it up with workspace and form records. Immutable per-user revisions reject concurrent preference updates; retain at least the latest record per username during maintenance.

### First workspace and role creation

A fresh production installation opens the setup wizard for an app administrator and does not seed a public security workspace or example form. Upgrades retain existing forms and their compatibility workspace. The sidebar wizard can create another workspace or use an existing one, then save and test the SOAR connection.

The **Create roles in Splunk** option is off by default and only shown as available to accounts with Splunk role-management capabilities. The backend uses the **requesting user's session token**, never the system token, for `/services/authorization/roles` writes. Splunk enforces grantable roles/capabilities. Generated role names replace namespace hyphens with underscores. No user assignments, imported roles, index permissions, search capability or app-wide administration are added.

| Role suffix | App capabilities | New form defaults |
| --- | --- | --- |
| `_viewer` | `use`, `read_team` | View forms and all workspace submissions |
| `_user` | `use`, `read_team`, `submit` | View and submit; read all workspace submissions |
| `_admin` | `use`, `read_team`, `submit`, `edit`, `publish` | View, submit, edit and publish; read all workspace submissions |

Capability names above have the `actionstack_` prefix. Workspace admins can create forms in their own mapped workspace; a viewer who has edit capabilities from another workspace cannot use them to create a form here. Existing form ACLs still govern editing. App administrators retain app-wide access.

The administrator assigns the roles to users or identity-provider groups in Splunk after creation. Alternatively, select existing viewer/user/admin roles and ensure they have the listed capabilities. Lookup users additionally need your existing search and lookup ACL grants; the wizard does not add these.

Workspace role mappings become form ACL defaults for newly created forms; changing a workspace never rewrites existing form or receipt ACL snapshots. Existing workspace membership lists remain supported. At least one admin role is required for new role mappings to avoid generating an empty edit ACL.

Role creation is not an atomic transaction across three Splunk roles. The adapter preflights names and never overwrites an existing role. A retry reuses roles only if their direct capabilities match exactly and they import no other roles. On partial failure, the workspace is not saved; correct the permission problem and retry, or select existing roles. Verify role propagation across members using Splunk's normal configuration replication. See [role REST parameters](https://help.splunk.com/en/splunk-enterprise/leverage-rest-apis/rest-api-reference/10.0/access-endpoints/access-endpoint-descriptions) and [SHC authentication replication](https://help.splunk.com/en?resourceId=Splunk_DistSearch_AdduserstotheSHC&version=splunk-9_4).

### Labels, previews and preferences

The SOAR label dropdown reads `container_options` using the configured server credential and exposes only labels beginning with `label_prefix`. No SOAR label is created. Publishing verifies label availability and the prefix; an existing published form can retain its previously published label when the prefix changes. A draft cannot bypass the prefix restriction. Prefix changes do not rewrite existing events or retries.

`POST /admin/forms/validate` validates the unsaved definition and inputs, including regex, required/conditional fields and exact lookup membership, using the same checks as a real submission. It requires editor access and workspace membership. Lookup searches run as the requesting user. No form, receipt or SOAR object is written by preview validation.

`POST /submissions/list` accepts `workspace_id` and `mine`. These filters run before sorting/limiting to 200 receipts. Owner/team/admin access is rechecked for every receipt; choosing a workspace never grants additional visibility.

`GET/POST /preferences` reads/writes only the authenticated user's theme (`dark`, `light`, `system`) with an expected revision. No username from the browser is accepted. System mode follows operating-system appearance changes.

Staging acceptance: complete setup as a Splunk admin; test role-creation failure and retry; confirm all three roles on every member; assign separate viewer/user/workspace-admin test accounts; verify cross-workspace denials and team receipt access; verify SOAR label filtering and publishing; exercise invalid/valid preview inputs without event creation; save a theme on one search head and read it on another. Local QA uses simulated SOAR and role creation; live role provisioning and cluster replication still need operator verification.


## 0.5.0 builder changes

- **Clone** in the form list or **Clone form** in the editor creates an unsaved draft with a new ID. Fields, lookup mappings, approval conditions, SOAR mapping and permissions are copied; publication state and author/history identifiers are not. Review the copy and save/publish it normally.
- A **Section** groups fields through the next section. **Collapsed by default** controls its initial display in preview and submission. Required fields and validation still apply inside collapsed sections; errors expand the affected section.
- Approval conditions remain configurable, but their workflow is always the SOAR playbook. Legacy `teams_reactions` definitions are accepted and interpreted as `soar_playbook` for new requests; existing submission snapshots retain their original metadata.
- The package no longer defines `actionstack_author` or `actionstack_publisher`. Workspace role creation continues to provision `as_<namespace>_viewer`, `as_<namespace>_user`, and `as_<namespace>_admin`. Existing externally managed roles and assignments are not deleted by this app.

Deploy the complete 0.5.0 bundle and refresh Splunk Web. No new KV collections are required. Test your lookup SPL and requesting-user permissions in Splunk; the local demo uses fictional rows and does not execute SPL.


## 0.5.1 AppInspect packaging corrections

The distributed `default/app.conf` now sets `is_configured = false`, as required for an unconfigured install package. ActionStack still derives setup readiness from saved workspace and SOAR connection records; this change does not clear them. The REST handler explicitly declares `python.version = python3.9` while retaining its newer `python.required` declaration. Packaging validates these settings before producing an archive. Submit the new bundle for a fresh Splunkbase AppInspect run.
