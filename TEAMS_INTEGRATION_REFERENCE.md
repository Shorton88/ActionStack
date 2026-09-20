# Existing Teams SOAR app — reference for future automation

Inspected locally on September 15, 2026. This reference preserves the downstream integration details; Teams execution is outside the initial form-ingestion implementation.

## Verified local action

- Project: external `phantom_microsoftteams` connector (not included in this repository)
- Manifest app version: `3.1.9-206`
- Action display name: **ask for approval via reactions**
- Action identifier: `ask_for_approval_reactions`

Sources in that external connector: `microsoftteams.json` (action manifest), `microsoftteams_connector.py` (handler), and `README.md`. These files belong to the separate connector project.

## Inputs available to a downstream playbook

- `destination`: channel, direct_message or chat.
- `group_id` and `channel_id` for channels; `user_id` for direct messages; `chat_id` for an existing chat.
- `title`, `message`, and `details` for the approval content.
- `approvers`: configured identities resolved against the tenant.
- `reactions`: emoji/label/approval-value mapping.
- Optional `adaptive_card` and reaction-seeding controls.
- `max_checks` and `check_interval_seconds` for polling/timeout.

The manifest defaults are 60 checks with a 30-second interval, described as approximately 30 minutes. The loop waits between checks and also performs network work.

## Decision outputs

The manifest and handler expose:

- `approved`, `answer`, `reaction`, `reaction_emoji`
- `answered_by`, `answered_by_upn`, `answered_by_email`, `answered_by_aad_id`
- `answered_at`, `timed_out`, `checks_performed`
- `message_id`, `web_url`, destination and ignored-reaction details

The handler records the responder fields when it finds an eligible reaction. Timeout records `approved: false` and `timed_out: true`. The action distinguishes configured approvers and ignores the sending account's seeded reactions. Empty `approvers` permits responses from anyone who can see the message; a future role-restricted approval playbook should supply the authorized list.

The action uses Teams directory identities. Splunk-role authorization requires the downstream workflow to supply/validate the corresponding eligible identities; it is not implied by the action itself.

## Relationship to this app

The form app delivers requester metadata, reason, requested object/duration and `approval_required`. A future Forever workflow can format that data into this existing action and consume its result.

This review establishes the local action contract. It does not establish the deployed Teams app version or perform a live action test. No changes were made to the Teams project.
