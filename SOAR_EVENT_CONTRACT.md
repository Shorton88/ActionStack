# SOAR event contract

Each submission creates one SOAR container and one submission artifact. Both IDs must be confirmed before delivery is marked complete.

- [Container example](examples/soar-container.json)
- [Artifact example](examples/soar-submission-artifact.json)

## Container data

The complete request is stored under `container.data.actionstack`.

| Field | Contents |
| --- | --- |
| `contract_version` | Envelope version, currently `1` |
| `submission_id` | Immutable submission UUID |
| `submitted_at` | UTC submission timestamp |
| `source` | App ID and configured source instance |
| `form` | Workspace ID, form ID, title, published version, and field labels |
| `submitted_by` | Splunk username, effective roles, and available profile fields |
| `routing` | Mapping revision, SOAR label, and tags |
| `inputs` | Validated fields with their original JSON types |
| `derived` | Additional values calculated by a configured mapping, if any |
| `policy` | Approval requirement for the SOAR playbook |

Field IDs are the keys in `inputs`. Lookup fields contain the selected values, not their display labels. Multiple-value inputs are arrays. Section headings are not submitted as inputs.

## Artifact data and CEF

The artifact uses the form's SOAR label. `artifact.data.actionstack.inputs` contains the same typed inputs as the container. Standard metadata is available in CEF:

- `actionstack_submission_id`
- `actionstack_form_id`
- `actionstack_form_version`
- `actionstack_submitted_at`
- `actionstack_submitted_by`
- `actionstack_approval_required`
- `actionstack_approval_policy`

Each input also receives an `actionstack_<fieldId>` CEF key. CEF values are strings; arrays are encoded as JSON strings. Optional field mappings add standard CEF keys such as `destinationAddress`.

For example, a field named `users` is available as:

- `container.data.actionstack.inputs.users`: `["alice", "bob"]`
- `artifact.data.actionstack.inputs.users`: `["alice", "bob"]`
- `artifact:*.cef.actionstack_users`: the JSON string `["alice","bob"]`

## Approvals

The form's approval rules are evaluated on the server after field validation. Rules can require approval for every request, no requests, or requests matching any configured condition.

```json
{"approval_required": true, "approval_policy": "soar_playbook"}
```

When approval is unnecessary, the policy is `none`. These fields express a requirement, not a decision. The SOAR playbook performs and enforces approval.

## Delivery and automation

1. Validate the published form, authorization, fields, and lookup selections.
2. Record the submission and its destination snapshot.
3. Create the container with `run_automation: false`.
4. Create the artifact with the container ID and the form's automation setting.
5. Save both IDs and mark delivery complete.

Automatic playbooks are selected by the container label. **Allow SOAR automation on delivery** starts enabled for new forms. Publish the form with this enabled, and configure an active playbook for that label. ActionStack reads playbook status but does not explicitly start playbooks through the run API.

Source identifiers are stable across delivery retries:

- Container: `splunk_actionstack:<submission_id>`
- Artifact: `splunk_actionstack:<submission_id>:submission`

After an uncertain response, the app checks for matching remote objects before creating them again. Retries use saved payloads; subsequent form edits do not change the original request. Delivery completion does not imply successful playbook execution.
