# SOAR event contract

Status: implemented payloads with local validation and recovery tests. The operator confirmed live intake with an earlier release; the artifact-label change in 0.1.4 is locally tested.

## 1. Delivery boundary

A logical submission consists of one SOAR event/container and its required submission artifact. Success requires both to be confirmed. The event contains the complete typed input; the artifact provides convenient fields for playbook datapaths.

Example files use fictional metadata, the illustrative label `automation_requests`, and container ID `12345`. The adapter replaces generated values and the artifact's container ID at runtime.

- [Container example](examples/soar-container.json)
- [Submission artifact example](examples/soar-submission-artifact.json)

Both examples disable automation for ingestion-only verification.

## 2. Canonical envelope

Store the following under `container.data.actionstack`:

| Field | Source and meaning |
| --- | --- |
| `contract_version` | Version of this envelope |
| `submission_id` | Server-generated immutable UUID |
| `submitted_at` | UTC timestamp recorded by the backend |
| `source` | App identifier and configured originating instance identifier |
| `form` | Stable ID, title, published version and field-label snapshot |
| `submitted_by` | Username, effective-role snapshot and optional trusted profile fields |
| `routing` | Published mapping version, label and tags |
| `inputs` | Every validated user field, using stable keys and original JSON types |
| `derived` | Server-computed values such as duration seconds/permanent |
| `policy` | Server-selected approval requirement; no approval decision |

The example is a Forever domain request. `requested_duration_seconds: null` with `permanent: true` means no requested automatic expiry. `approval_required: true` conveys policy to a downstream playbook.

The timestamp describes submission. Actual enforcement time and expiration belong to downstream execution.

Do not include Splunk session keys, SOAR tokens, credentials or raw HTTP authorization headers. Optional email/display name is included only if a trusted user profile supplies it.

### Configurable approval rules

Version 0.1.5 adds optional `mapping.approval` to form definitions:

```json
{"mode":"conditional","policy":"soar_playbook","conditions":[{"field":"duration","equals":"forever"}]}
```

Modes are `never`, `always`, and `conditional`. Conditional rules require 1–20 conditions; any matching condition requires approval. Other modes have an empty conditions array. Conditions reference dropdown/radio choices or typed checkbox booleans. New requests use `soar_playbook`; legacy `teams_reactions` definitions normalize to that policy. the emitted policy is `none` when approval is unnecessary. Omitting this configuration retains legacy behavior: Forever requires SOAR-playbook approval for the block-object policy, and generic forms require none.

The server validates rules during save/publish and evaluates them against normalized, visible inputs. The existing canonical policy and `actionstack_approval_required` / `actionstack_approval_policy` CEF fields remain the downstream interface. Approval decisions and enforcement remain in SOAR. New publications do not rewrite stored requests or their policy metadata.

## 3. Artifact projection

New submissions in 0.1.4 use the published form's mapping label for both the container and submission artifact, for example `automation_requests`. Requests recorded by earlier versions retain their saved artifact label (`event`) on retry; existing remote artifacts are not relabeled.

Automatic playbook selection uses the **container label**. Matching artifact labels provide consistent classification and can be used in playbook filters; they are not required for container-label routing. Enable the form's **Allow SOAR automation on delivery** setting and publish when automatic execution is intended, and configure an active SOAR playbook for the container label. [SOAR 8.6 container semantics](https://help.splunk.com/en/splunk-soar/soar-on-premises/python-playbook-api-reference/8.6.0/overview/understanding-containers)

Prefix convenience fields with `actionstack_` to avoid collisions with standard CEF names. Example values in the CEF projection are strings; canonical values retain their types in the container envelope.

Suggested playbook inputs include:

- `artifact:*.cef.actionstack_submission_id`
- `artifact:*.cef.actionstack_submitted_by`
- `artifact:*.cef.actionstack_object_type`
- `artifact:*.cef.actionstack_object_value`
- `artifact:*.cef.actionstack_hash_type`, for hash requests
- `artifact:*.cef.actionstack_duration`
- `artifact:*.cef.actionstack_approval_required`

For standard observable mappings, use `destinationAddress` for the initial IP template, `destinationDnsDomain` for the domain template and `fileHash` for hash input. These are template choices; admins can map fields differently. Include the selected hash algorithm separately. Custom CEF contains types can be added where validated.

In 0.2.0, array inputs remain typed arrays under `container.data.actionstack.inputs` and are also copied to `artifact.data.actionstack.inputs`. CEF `actionstack_<fieldId>` and optional custom CEF mappings contain JSON-encoded strings for arrays. For example, `names` becomes `["Alice", "Bob"]` in custom data; its CEF value is the JSON text of that list. Scalar CEF behavior is unchanged. The artifact data field is a documented JSON object ([Splunk reference](https://help.splunk.com/en/splunk-soar/soar-on-premises/rest-api-reference/8.5.0/artifact-endpoints/rest-artifact)). A submission does not require global SOAR custom-container-field creation for every new form field.

SOAR documents CEF, artifact custom data, source identifiers and explicit automation control on its artifact endpoint. [SOAR 8.6 artifact reference](https://help.splunk.com/en/splunk-soar/soar-on-premises/rest-api-reference/8.6.0/artifact-endpoints/rest-artifact)

## 4. Proposed HTTP sequence

1. Validate published form and current authorization.
2. Persist submission ID, input/policy snapshot and a pending delivery record.
3. POST the container to `/rest/container` with `run_automation: false` and no bundled artifacts.
4. Confirm and persist the returned container ID.
5. POST the required artifact to `/rest/artifact`, substituting that ID.
6. Confirm the artifact ID and persist the complete receipt.
7. Return **Submitted to SOAR** with the submission and event IDs.

In production, the admin's published ingestion setting may enable automation on the final required artifact. Additional artifacts, if configured, must precede that trigger. The app does not call `/rest/playbook_run`.

Container creation returns its ID. Duplicate source-identifier responses can include the matching existing container ID. Source deduplication behavior must be validated for the configured label and optional source asset. [SOAR 8.6 container reference](https://help.splunk.com/en/splunk-soar/soar-on-premises/rest-api-reference/8.6.0/container-endpoints/rest-containers)

Use HTTPS with a trusted CA and a server-held SOAR automation token. Resolve allowed destinations from setup configuration.

## 5. Retry and reconciliation

Use a stable source identifier for each stage:

- Container: `splunk_actionstack:<submission_id>`
- Submission artifact: `splunk_actionstack:<submission_id>:submission`

Serialize delivery of the same submission and verify the remote source/envelope before adopting any reported existing ID. Reconcile ambiguous outcomes before retrying. If a container exists and the artifact is absent, resume at artifact creation. Do not repeat a completed artifact stage merely to retrigger automation.

If automation was enabled and a final artifact POST times out, determine whether that artifact exists before sending it again. Event delivery and downstream side-effect deduplication have different guarantees; the latter belongs to the user's playbooks.

A receipt is complete only after every required stage is confirmed. Keep incomplete or uncertain submissions visible to authorized operators.

## 6. Compatibility validation

Validate in the actual on-prem SOAR 8.6 environment:

- Normal event creation and label availability.
- Namespaced JSON data round-trip, Unicode, booleans, numbers, nulls and arrays.
- Custom CEF keys and optional contains metadata.
- Source-identifier duplicate behavior under the configured source asset.
- Failure after container creation and recovery at artifact creation.
- Explicit disabled automation during intake testing.
- Optional final-artifact triggering after a SOAR owner configures an existing playbook.

Validation of these JSON fixtures is not a live integration test.


### Workspace and request-validation attribution (0.1.6)

New envelopes include `form.workspace_id` (legacy forms use `security`). When a reusable validation policy is selected, `form.validation_policy` records its `id` and `revision`. The full saved rules remain in the app's immutable form and receipt snapshots. Requests must pass field validation, the saved custom policy, and any lookup selection rechecks before a pending record or SOAR event is created. Approval metadata under `policy` keeps its existing meaning. Historical envelopes and retry payloads are unchanged.

### Field validation (0.2.0)

New and migrated forms store checks on each field and no longer include `form.validation_policy` in their event envelope. Historical policy-based forms retain their saved attribution. Multi-value checks evaluate each item, and selected lookup values are rechecked as one bounded batch before a receipt is recorded. The `policy` envelope member continues to mean downstream approval requirements.
