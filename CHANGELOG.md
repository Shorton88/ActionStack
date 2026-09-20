# Changes

## 0.5.1 — September 19, 2026

- Fix the reported AppInspect setup-state failure by shipping `default/app.conf` with `is_configured = false`.
- Add `python.version = python3.9` to the persistent REST handler for AppInspect and older Splunk releases. Retain `python.required = 3.9, 3.13` for newer releases, where it takes precedence.
- Guard both settings during packaging to prevent these failures from recurring.

The workspace/SOAR setup wizard still determines readiness from saved configuration. Existing forms, workspaces and connection settings are preserved. Re-submit the 0.5.1 bundle to Splunkbase; hosted AppInspect has not been rerun locally.

## 0.5.0 — September 19, 2026

- Use `actionstack_` as the connection label-prefix example.
- Support read-only lookup SPL transformations and separate value/display-label mappings for single and multiple selections. Preserve requester permissions, bounded searches, and exact value revalidation.
- Add collapsible sections with a builder default and automatic expansion on validation errors.
- Keep approval conditions while standardizing approval handling on the SOAR playbook.
- Clone existing forms into independent, unsaved drafts with new IDs.
- Remove bundled generic author/publisher roles; retain workspace role provisioning.
- Add lookup, section-validation, approval-compatibility and cloning regression coverage.

Deploy the complete bundle and refresh Splunk Web. No new KV collections are required.

## 0.4.2 — September 19, 2026

- Move Team workspaces beside Settings in the sidebar's admin area, retaining app-admin access checks.
- Remove the editable Owner field and its default from the form builder. Catalog cards show and search the actual workspace name; existing author/version history remains intact.
- Fix the light-theme builder canvas and field placeholder backgrounds and text.
- Verify the desktop editor, settings without Owner, workspace navigation and both canvas themes locally; compile and package the app.

Deploy the updated app bundle and hard-refresh Splunk Web. No new collections or configuration are required.

## 0.4.1 — September 19, 2026

- Fix editing saved SOAR connections when Splunk KV Store adds metadata such as `_user`. Return only supported settings and explicitly select writable fields in the browser.
- Preserve existing credentials on edits and keep rejecting unknown input fields. The frontend also tolerates metadata returned by older handlers.
- Add server and browser-payload regression coverage; all 165 automated checks pass. Verify repeat edits against a local UI fixture that adds KV metadata and rejects unsupported fields.

Deploy the full app bundle, restart persistent handlers through the normal SHC deployment procedure, and hard-refresh Splunk Web. No new collections or configuration are required.

## 0.4.0 — September 19, 2026

- Rebrand as **ActionStack**, retaining the layered icon and adding a compact ActionStack wordmark.
- Rename the Splunk app to `splunk_actionstack`, its view/assets and REST endpoint to `actionstack`, and capabilities, KV collections and CEF metadata to the `actionstack_` prefix. New workspace roles use `as_<namespace>_<level>`.
- Use `data.actionstack` and `splunk_actionstack:` source identifiers in SOAR events. Update frontend, handlers, examples, tests, documentation and packaging together.
- This is a fresh-install namespace change, authorized before deployment; it does not migrate an earlier installed app. The preview uses a separate ActionStack demo database, preserving the earlier demo file.
- All 161 automated checks pass after the rename.

## 0.3.3 — September 19, 2026

- Replace the SOAR certificate text area with an admin-only **Ignore certificate validation** checkbox in setup and Settings. Validation stays enabled by default, including on upgrades.
- Apply the saved choice to the SOAR client's HTTPS context without changing global trust or permitting HTTP/redirects. Preserve previously saved CA chains for validated connections.
- Existing submissions keep their captured connection settings for delivery retries and activity reads; new submissions use the current setting.
- 161 automated checks pass, including default verification, explicit opt-out, re-enabling, existing settings, boolean validation, authorization and delivery propagation. Verify save/test controls locally with a simulated connection.

Deploy the full app through the SHC deployer and restart persistent handlers through the normal deployment procedure, then hard-refresh Splunk Web. No new collections are required.

## 0.3.2 — September 19, 2026

- Give generated workspace role names explicit theme-aware backgrounds, borders and text so Splunk Web inline-code highlights cannot wash out dark-mode text. Keep long names within their cards.
- Verify role previews in light and dark themes with simulated Splunk host code styles; build the production app bundle.

Deploy the updated app through the SHC deployer and hard-refresh Splunk Web. No configuration changes are required.

## 0.3.1 — September 19, 2026

- Fix light-theme heading and role-list text contrast when Splunk Web supplies dark-theme typography.
- Add a subtle lift and violet/cyan glow to catalog cards on hover and keyboard focus. Respect reduced-motion preferences.
- Replace fixed Splunk Enterprise/SOAR version labels with the ActionStack release version, sourced from package metadata at build time.
- Verify setup text and catalog interaction in both themes locally with simulated host styles; build the production app bundle.

Deploy the updated app through the SHC deployer and hard-refresh Splunk Web. No new collections or configuration are required beyond 0.3.0.

## 0.3.0 — September 18, 2026

- Add first-workspace setup with optional Splunk viewer/user/admin role creation, workspace access defaults, SOAR connection testing and event label prefix. Keep existing form permissions intact.
- Rename My submissions to Submissions and add workspace/all versus mine filters, applied before the receipt limit.
- Rename the builder Access tab to Settings; move icons there and add eight iridescent color choices with a preview. Generate new form IDs from the title plus four random characters.
- Replace free-text SOAR labels with an available-label dropdown filtered by the saved prefix.
- Add Preview → Test validation using the production validation path without creating a submission.
- Add saved Dark, Light and System themes per Splunk user in shared KV Store.
- 154 automated checks pass. Browser verification covers workspace/role setup with a simulated adapter, prefix-filtered labels, generated form IDs, saved appearance, validation errors/success, submission filters and theme persistence. Live Splunk role creation/SHC propagation remains an operator acceptance check.

Deploy the full app through the SHC deployer, including the new `actionstack_preferences` collection. Restart persistent handlers through the normal deployment procedure and hard-refresh Splunk Web.

## 0.2.1 — September 17, 2026

- Add a visual Form icon picker under the title/description in Form builder → Build: Shield, Workflow, Search, Document, Globe and Lightning.
- Use the same icon definitions in the picker, catalog cards and form headers. Existing icon choices are retained; publish to update the catalog.
- Include a collapsed **Result data** section beneath action runs, populated from `action_result.data` even when the action has no summary. Preserve separate summaries and reported status.
- Bound and redact result data previews, retain receipt access controls, and mark truncated data. Logs and action parameters remain excluded.
- 140 automated checks pass. Browser checks cover icon saving/publication and separate collapsed action results, including data-only and empty results. SOAR result reads were verified with simulated responses; live acceptance remains required.

Deploy the full app bundle through the SHC deployer and hard-refresh Splunk Web. No new collections or backend configuration are required beyond 0.2.0.

## 0.2.0 — September 17, 2026

- Move validation into each field: equals, not equal, like, not like and regex with custom messages. Remove policy management/selection from the UI and migrate saved rules when editing.
- Add reversible form deletion, Trash and restore with revision conflicts, role checks and audit events. Restored forms remain unpublished until explicitly published.
- Replace the home banner and tile wall with a team-neutral catalog, category/search filters, pagination and personal favorites in shared KV Store.
- Add multi-value text chips and multi-value lookup fields; retain single-value lookups. Revalidate selected lookup values in one exact-match batch. Deliver arrays in both container/artifact custom data and JSON text in CEF.
- 135 automated checks pass, including migration, field checks, list validation, lookup batches, favorites authorization, and delete/restore.
- Browser-verified favorites persistence, field creation/publishing, invalid-item rejection, successful multi-value submission and delete/restore. Local testing uses simulated SOAR.

Deploy the full app through the SHC deployer; the new `actionstack_favorites` collection is required. Hard-refresh Splunk Web. Republish migrated forms to apply field validation.

## 0.1.8 — September 17, 2026

- Simplify validation rules to Field ID, Validation type, Value and Message to user.
- Remove SOAR metadata controls and policy snapshots from the editor. Required settings belong in form fields; older required rules migrate when editing.
- Support camelCase field IDs such as `emailAddress` and preserve existing block event metadata.
- 118 automated checks pass. Browser verification confirms saving an email regex policy and the simplified form selector.

Deploy the full bundle through the SHC deployer and hard-refresh Splunk Web. Republish forms to apply policy changes.

## 0.1.7 — September 17, 2026

- Replace the separate Built-in checks selector with one Validation policy selector. Block object validation is now a normal editable policy with conditional Required, IP address, Domain, SHA-1, and SHA-256 rules.
- Preserve legacy published forms and receipts. Opening a legacy block form in the editor prepares a policy-based definition; publishing activates it. Forms that already have a custom policy receive a combined editable policy so their existing rules are retained. Preserve explicit approval rules and the default Forever/Teams requirement.
- Keep duration/permanent/object CEF metadata as a visible option on the policy, separate from its editable validation rules.
- Add Regex match rules with field-specific messages and optional conditions. Use Python full-value matching, inline flags, syntax checks, a 512-character pattern limit and a one-second isolated evaluation budget. Invalid or timed-out validation creates no request/event. Increase the policy rule limit to 64 to accommodate migrated combinations.
- 111 automated checks pass, including migration, normalization, snapshots, regex full matches/flags, invalid patterns, timeouts and recovery. Local browser verification covers the single selector, migrated rules, invalid regex rejection, and saving a valid regex policy.

Deploy the full 0.1.7 bundle through the SHC deployer and hard-refresh Splunk Web. No new collections beyond 0.1.6. Republish forms to apply their selected policy revisions.

## 0.1.6 — September 16, 2026

- Add administrator-managed team workspaces, role membership, archive/restore, workspace switching, and form assignment. Legacy forms remain in Security workspace. Workspace membership is enforced alongside form roles on the server.
- Rename Submission policy to Request validation. Add reusable validation policies with conditional required/equality/numeric rules, revision checks, and saved rule snapshots. Manage policies from the sidebar, then select them on the form’s Request validation tab. Republish to apply policy edits.
- Add lookup search fields using `| inputlookup lookup_name | fields value_field`, the requesting user’s Splunk permissions, a configurable typing delay (default 50 ms), minimum three characters, and 25-result limit. Revalidate selected values before accepting submissions. Serialized requests discard stale replies.
- Include bounded action result summaries with status, keeping raw output and parameters out of receipts. Read app-run summaries with event scoping and retain statuses if summary reads fail.
- Highlight the automation enablement setting and add cyan/purple glow and shine to primary buttons, with reduced-motion support.
- Ship 36/72-pixel Splunk menu icons.
- 101 automated checks pass; local browser checks cover policy creation, workspace switching, lookup publication and simulated delivery, plus the status-summary fixture. Live Splunk lookup ACLs and SOAR app-run reads require staging verification.

Deploy the complete 0.1.6 bundle through the SHC deployer. This release adds `actionstack_workspaces` and `actionstack_validation_policies` collections. Restart/reload as required by the deployment, then hard-refresh Splunk Web.

## 0.1.5 — September 16, 2026

- Add an Approvals tab with never, always, and any-matching-condition modes. Conditions use dropdown, radio, or checkbox values, with Teams reactions or a SOAR-managed approval workflow. Existing block-object forms retain the Forever/Teams rule until explicitly changed and published. Rules produce trusted metadata; playbooks still enforce approvals.
- Display the approval requirement during form review and on the receipt. Validate rule references and choice values on the server. An untouched optional checkbox is normalized to false, matching its visible state.
- Add read-only event activity to receipts: playbook/action names and reported states, refreshed every 30 seconds while visible, plus manual refresh. Delivery success remains separate from run status. Display partial permission errors, unknown states, and truncation explicitly; do not expose action parameters, results, or logs.
- Apply receipt authorization before SOAR reads, reuse the original connection, and bound status reads to 20 refreshes/user/minute across the cluster. No new KV collections are required.
- Replace the Bootstrap/Splunk `.form-actions` class with an app-specific footer class and explicitly apply its dark background.
- 85 tests pass; production build and local browser checks cover the approval editor, review notice, footer, and status panel. Live run-read permissions and responses still require validation on the installed SOAR version.

Deploy the complete 0.1.5 bundle through the SHC deployer, follow the normal required restart procedure, and hard-refresh Splunk Web. No republish is needed to retain existing approval behavior. Publish when changing rules. Status polling requires read access to playbook and action runs on the event.

## 0.1.4 — September 16, 2026

- New submission artifacts inherit the published form's SOAR label, matching their container instead of using the fixed label `event`.
- Explain the shared label in the form builder and document that automatic playbook selection uses the container label. Automation remains controlled by the published **Allow SOAR automation on delivery** setting, which defaults off.
- Preserve the saved payloads on retry: older requests keep their original artifact label, and existing SOAR artifacts are not relabeled.
- Update the example artifact and verify matching labels, automation controls, form republishing, and legacy retry behavior. Full suite: 65 passing tests.

Deploy the complete 0.1.4 bundle through the SHC deployer, follow the normal required restart procedure, and hard-refresh Splunk Web. Create a new submission to see matching labels. This change has been tested locally, not against the live cluster.

## 0.1.3 — September 16, 2026

- Check the configured label before creating a SOAR event and explain missing labels directly. The operator confirmed that creating `automation_requests` resolved the reported submission failure.
- Show the request method, endpoint, HTTP status, and bounded, credential-redacted JSON error detail when SOAR rejects a request. Preserve duplicate reconciliation and distinguish authentication, validation, and temporary failures.
- Replace the misleading “intake test” message with instructions to submit a form with automation disabled. The connection check verifies read access and warns about published forms whose labels are unavailable.
- Show the original form version and SOAR label in submission details. Retry retains the original mapping; publishing a new mapping applies to new submissions.
- Add 12 regression tests covering remote responses, label preflight, diagnostics, and retry routing. Full suite: 63 passing tests.

The configuration fix works without this upgrade. For the improved diagnostics, deploy the complete 0.1.3 bundle through the SHC deployer, follow the normal required restart procedure, and hard-refresh Splunk Web. This release was tested locally; full cluster acceptance remains required.

## 0.1.2 — September 16, 2026

- Send `X-Requested-With: XMLHttpRequest` with API requests, alongside the Splunk form key and existing session cookies, following Splunk's AJAX request convention.
- Select the CSRF cookie for the current Splunk Web port. For a reverse proxy, accept only a single unambiguous token rather than choosing the first cookie for an arbitrary instance. Refresh the token on every request.
- Block mutations before sending when the token is missing or ambiguous. Explain non-JSON Splunk CSRF/session errors without exposing response bodies or credentials. Failed POSTs are never retried automatically.
- Add 13 transport regression tests covering settings headers, cookie selection and renewal, reverse-proxy paths, missing tokens, and the reported non-JSON 401. Full suite: 51 passing tests.

Deploy the complete 0.1.2 bundle through the SHC deployer and follow the normal required restart procedure. Hard-refresh Splunk Web (sign in again if the session is stale), then use **Save connection** followed by **Test saved connection**. This fixes the client request defects; live connectivity to the user's SOAR instance has not been verified here.

## 0.1.1 — September 16, 2026

- Replace direct `crypto.randomUUID()` calls with UUID generation using cryptographically secure `getRandomValues`, including form creation, added/duplicated fields and submission keys. This handles HTTP intranet origins where `randomUUID` is unavailable.
- Clone JSON form definitions without requiring `structuredClone`.
- When browser SubtleCrypto is unavailable, obtain the exact SHA-256 fingerprint from an authenticated backend endpoint. That endpoint checks identity/capability/form access and never creates or delivers a request. Existing pending-request key semantics are preserved.
- Add five frontend compatibility tests and three backend endpoint tests. Full suite: 38 passing tests.

Upgrade the complete app on the SHC deployer, distribute the bundle, and follow the normal required restart procedure so persistent handlers load the new endpoint. Hard-refresh Splunk Web to load the updated JavaScript. HTTPS remains recommended to protect sessions and form contents.

The reported Splunk toast is generic: this release fixes a reproducible compatibility defect, but confirming the exact original error still requires the affected browser's console output.
