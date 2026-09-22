# Deployment

Download ActionStack from [Splunkbase](https://splunkbase.splunk.com/app/9812).

## Install

ActionStack runs on a standalone Splunk Enterprise search head or a search head cluster. Both require KV Store to be enabled. Install the complete `splunk_actionstack` app:

- **Standalone search head:** in Splunk Web, open **Apps → Manage Apps → Install app from file**, upload the package, and restart Splunk if prompted.
- **Search head cluster:** use the SHC deployer and confirm the same version is installed on every member. Do not install the app directly on individual cluster members.

The REST handler supports Python 3.9 and 3.13. The app uses the signed-in Splunk session for identity and roles, KV Store collections for application data, and Splunk's encrypted credential store for the SOAR token.

After installation, open **ActionStack** as a Splunk administrator. Existing forms, workspaces, and submissions are retained when updating the app. Refresh Splunk Web after an update to load the new browser assets.

## Workspace setup

The setup wizard creates the first workspace. Select **Create roles in Splunk** to provision:

| Role | Default access to new workspace forms |
| --- | --- |
| `as_<namespace>_viewer` | View forms and all workspace submissions |
| `as_<namespace>_user` | View, submit, and read all workspace submissions |
| `as_<namespace>_admin` | View, submit, edit, and publish workspace forms |

Creating roles requires Splunk's `edit_roles` or `edit_roles_grantable` capability. Assign these roles to users or identity-provider groups in Splunk. Existing roles can also be selected. Workspace defaults apply to new forms; existing forms retain their permissions. Workspace administrators do not receive app-wide administration or Splunk search access automatically.

Manage workspaces through **Team workspaces**, and use the workspace selector to switch the catalog and submissions view.

## SOAR connection

In the setup wizard or **Settings**, enter:

- The SOAR HTTPS origin, such as `https://soar.example.com`, without a path or embedded credentials.
- An automation-user token with access to the intended labels and permission to create/read containers and artifacts.
- An optional label prefix, such as `actionstack_`, to filter the builder's label list.
- A source instance name and optional SOAR source asset ID.
- A request timeout.

The token also needs read access to playbook runs, action runs, app runs, and action results to display execution status. Every search head must be able to reach SOAR, and its outbound IP must be permitted by the automation user's allowed IP configuration.

Certificate verification is enabled by default. **Ignore certificate validation** skips certificate-chain and hostname verification for that connection; it does not install or pin a certificate.

Select **Save connection**, then **Test saved connection**. The test checks connectivity and retrieves container options. To check write access, publish and submit a form with automation disabled. Labels must already exist in SOAR.

The integration uses SOAR's REST APIs. SOAR Cloud exposes the same intake APIs, but Cloud compatibility has not been verified for this release.

## Forms and automation

Use **Form builder** to add fields, validation, lookup searches, sections, and access rules. Field types and settings are grouped into collapsible sections. **Preview → Test validation** checks the form without creating a SOAR event. Save a draft while editing; publish to apply changes to new submissions.

**Static text** adds a heading and message without collecting input. Choose plain text for section descriptions, or Information or Warning for a callout. Use **Show condition** to display it when an earlier field has a particular value. Line breaks are preserved; HTML is displayed as text. Static text is not included in submitted inputs or SOAR field mappings.

Under **SOAR mapping**, choose a label, tags, and optional CEF mappings. **Allow SOAR automation on delivery** starts enabled for new forms and permits automation on the final submission artifact. Existing and cloned forms keep their saved setting. Configure an active SOAR playbook for the container label. Delivery success means the event and artifact were created; execution status is shown separately.

The **Approvals** tab marks requests that require approval. The SOAR playbook must enforce that requirement before performing actions. ActionStack does not collect approval decisions.

**Clone** creates an unsaved copy with a new ID. **Delete** moves a form to **Trash**; restore and publish it to make it available again. Existing submissions remain accessible.

## Lookup fields

Single-value and multiple-value lookup fields use the requesting Splunk user’s permissions in the selected app namespace. SPL searches require search capability and read access to the lookup. Simple KV Store lookups can use direct collection reads with that same user’s read permissions.

```spl
| inputlookup identity_lookup_expanded
| eval display_name=coalesce(firstName . " " . lastName, identity)
| table identity display_name
```

Set **Value field sent to SOAR** to `identity` and **Display label field** to `display_name`. Keep both in the final results. Suggestions match either field; only selected values are submitted and revalidated.

Searches must start with `inputlookup`. ActionStack adds `strict=true` so lookup errors fail the search. The `inputlookup` command does not support `local=true` or `local=false`; remove these options from any existing form searches and republish the form. Supported transformations are `eval`, `where`, `search`, `fields`, `table`, `rename`, `dedup`, `sort`, `head`, `tail`, `fillnull`, `rex`, `regex`, `spath`, `stats`, `eventstats`, `streamstats`, `mvexpand`, `makemv`, `mvcombine`, `nomv`, `convert`, and `replace`. Macros, subsearches, custom commands, and write commands are not supported.

For a KV Store lookup whose output fields are declared `string` in `collections.conf`, with only `fields` or `table` projections, ActionStack resolves the lookup definition and reads matching records directly from the collection. No search job is created. Scalar `mvexpand` also uses this path; array results fall back to SPL. Definitions with filters or time fields, CSV lookups, and other transformations use SPL so their semantics are preserved. Direct reads require access to the lookup definition, collection configuration, and underlying collection; otherwise the app tries the normal search path. For the fastest experience, materialize expensive transformations into a KV Store lookup and use a simple projection.

The default search delay is 50 ms after at least three characters. Results are limited to 25 prefix matches. Search jobs have a five-second execution limit. Each form supports up to five lookup fields; multiple-value fields accept up to 25 items. Recent suggestions are cached in the field for 30 seconds; submission checks always run against the lookup again. Large lookups may require scans even when results are limited.

Multiple-value text and lookup fields accept comma-, newline-, or semicolon-separated lists. Paste a list, or type it and press Enter or **Add values**. For lookups, use values from the configured SOAR value field (matching ignores case); use search suggestions to select by display label. A batch with unknown values is rejected without adding a partial list. Duplicate values are removed. Lookup verification also removes case-only duplicates and returns the stored value, including its casing, before validation and delivery.

## Permissions

| Capability | Permission |
| --- | --- |
| `actionstack_use` | Access the app and catalog |
| `actionstack_submit` | Submit permitted forms and retry own requests |
| `actionstack_edit` | Create and edit permitted drafts |
| `actionstack_publish` | Publish and archive permitted forms; also requires edit access |
| `actionstack_read_team` | Read submissions where form team roles match |
| `actionstack_audit` | Read audit metadata |
| `actionstack_admin` | Configure connections and administer the app |

The bundled configuration grants baseline use/submit capabilities to `user` and administration to `admin`. Form permissions and workspace membership further restrict access. Empty view/submit role lists allow users with the relevant capability; empty team roles grant no team submission access.

Lookup searches use the requesting user's session. Application storage uses server-side authorization and the Splunk system token. Keep the backing KV collections and credential store restricted to administrators.

## Submissions and recovery

**Submissions** shows authorized requests in the selected workspace. **My submissions** filters to the signed-in user. The list shows ten requests per page with playbook/action totals and colored status counts. Only the current page is polled, with at most three status requests in flight. Receipts poll SOAR status every 30 seconds while open and visible. Unavailable status is distinct from zero runs. If history exceeds 25 playbook runs or 100 actions, totals include the history but status counts cover the latest runs and are marked accordingly.

Receipts prefer custom action run names over action types, and retain collapsible summaries and result data. Other block results are read for the latest three playbook runs, up to 100 results each. Format/filter/decision/code datapaths are available through SOAR’s `block_results` API. Utility blocks appear only when their explicit run headers are included in SOAR’s playbook report; coverage varies by version. Output existence, a false condition, or overall playbook success is never treated as a block status. Use SOAR for missing statuses and complete history.

A submission is recorded before delivery. Use **Retry delivery** for a failed or uncertain request. Only the original requester can retry, and current permissions are checked. Retries preserve the original form, inputs, identity, connection settings, and source identifiers. Connection changes apply to new submissions; retain old credentials until pending requests have been resolved.

Delivery locks do not expire automatically. If a handler crashes while holding a lock, stop/drain the ActionStack handlers on the standalone search head or on **all** cluster members, verify no delivery remains active, and inspect the submission and SOAR objects. Back up the records before removing only the abandoned `delivery:<submission-id>` key from `actionstack_locks`. Resume the handlers and retry through the app. Do not clear locks based only on age.

## Operations

- Back up ActionStack KV collections and encrypted credentials with the Splunk deployment.
- Preserve form revisions, connection snapshots, unfinished submissions, and active delivery locks during retention cleanup.
- The catalog is paginated; submission lists show the latest 200 authorized records. KV scans are bounded at 50,000 records.
- Delivery attempts are limited to 10 per user per minute. These limits are shared across members in a cluster. Lookup searches are limited to 60, receipt activity refreshes to 20, and submission-list status reads to 60 per user per minute, with separate budgets.
- The app does not run a background retry or retention service. Prune old rate-limit records through your administration process, retaining at least the last 24 hours.
- Validate role isolation, credential access, delivery/retry behavior, and, for clusters, member failover in your deployment.

For a Splunk Web CSRF error, sign in again and check that the reverse proxy preserves session cookies, `X-Requested-With`, and `X-Splunk-Form-Key`. For a missing-label error, create the configured label in SOAR or change the form's mapping and publish it. Retrying an existing submission keeps its original label.
