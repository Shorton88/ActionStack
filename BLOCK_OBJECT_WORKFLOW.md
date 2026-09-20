# First form: Block an object

Status: implemented and locally tested; live intake validation pending. The user's SOAR playbooks own enforcement and approval.
Target: Splunk Enterprise 10.2.4 → Splunk SOAR 8.6, both on premises.

## 1. Form definition

| Field | Control | Validation |
| --- | --- | --- |
| Object type | Required select | IP address, File hash, Domain |
| Hash type | Conditional select | SHA-1 or SHA-256; required only for File hash |
| Object value | Required text | Validated and normalized for the selected type |
| Block duration | Required select | 4 hours, 1 day, 30 days, 60 days, 90 days, Forever |
| Reason | Required text area | Nonempty, bounded length |
| Ticket/reference | Optional short text | Bounded length |

The units for 30/60/90 are interpreted as days. Use one object per submission initially.

Show a review summary of the entered value; the backend normalizes it on acceptance. Include the object, hash type if applicable, duration and reason. For Forever, show “Requires approval in SOAR.” The submission button reads **Submit request** and the receipt reads **Submitted to SOAR**.

IP parsing supports individual IPv4/IPv6 addresses. Domain input accepts a domain rather than a URL/path and uses consistent case/IDNA normalization. SHA-1 requires 40 hexadecimal characters; SHA-256 requires 64. Normalize hash casing. Reject unexpected hidden values, such as a hash algorithm on a domain request.

## 2. Duration and policy metadata

| Display | Stored enum | Requested seconds |
| --- | --- | --- |
| 4 hours | `4h` | 14,400 |
| 1 day | `1d` | 86,400 |
| 30 days | `30d` | 2,592,000 |
| 60 days | `60d` | 5,184,000 |
| 90 days | `90d` | 7,776,000 |
| Forever | `forever` | `null` |

The backend derives:

- `requested_duration_seconds` from the enum.
- `permanent`: true only for Forever.
- `approval_required`: true only for Forever.
- `approval_policy`: `teams_reactions` for Forever; `none` otherwise.

These values describe the request and applicable downstream policy. They do not record an approval decision. Do not include `approved: true`, an actual block start, or an expiry timestamp in the intake record.

The downstream playbook can calculate expiry after actual enforcement and perform Teams approval before permanent enforcement. The app's responsibility ends at complete event delivery.

## 3. SOAR mapping

Suggested event label: `automation_requests`.
Suggested routing tag: `automation:block_object`.
Suggested title: `Block object request · <object_type> · <submission_id>`.

The complete typed input and trusted submission metadata live under `container.data.actionstack`. A submission artifact exposes selected scalar fields as CEF, using stable prefixed keys and standard observable keys where suitable.

See [SOAR event contract](SOAR_EVENT_CONTRACT.md) and its example payload files for the exact proposed structure.

Metadata includes server-generated submission ID/time, form ID/version/title, server-derived Splunk username/role snapshot, requested duration and approval requirement. Arbitrary custom forms retain the same envelope while their `inputs` differ.

## 4. Downstream context

The intended security products are Palo Alto firewall, Infoblox ThreatDefense DNS and TrendAI endpoint platform. Initial potential assignments are IP to Palo Alto, domain to Infoblox and hashes to TrendAI; the user's playbooks determine the final actions and assets.

Temporary requests are available to authenticated Splunk users. Forever requires the existing Teams reaction approval. Its verified local action name is **ask for approval via reactions**, identifier `ask_for_approval_reactions`. See [Teams action reference](TEAMS_INTEGRATION_REFERENCE.md).

The app does not need product API credentials, product connector mappings, an active-block registry, expiration jobs, approval polling or a dispatcher playbook for this release.

## 5. Acceptance criteria

1. Type selection controls field visibility and server validation.
2. Both hash algorithms and all six durations produce the intended normalized payload.
3. Temporary requests have `approval_required: false`; Forever has `approval_required: true`.
4. The authenticated requester and UTC submission time are derived server-side.
5. The configured label/tags and all accepted fields appear in the SOAR event/artifact.
6. A failed artifact stage cannot produce a successful delivery receipt.
7. Repeating the same submission does not create a second logical request.
8. The complete intake flow works without any blocking or approval playbook installed.

## Approval configuration

The duration policy above describes the shipped default. In 0.1.5, administrators can view or change it under **Form builder → Approvals**, then publish the updated form. The original Forever/Teams rule is preserved for existing definitions. Playbooks should use the submitted policy metadata rather than assuming every form uses the default rule. The ActionStack receipt shows the original requirement and read-only event run summaries; approval decisions and enforcement still belong to the SOAR workflow.
