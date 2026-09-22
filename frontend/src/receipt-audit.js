/** @typedef {import('./types').Submission} Submission */
/** @typedef {import('./types').Activity} Activity */
/** @typedef {{data: Activity | null, error: string, loading: boolean}} ActivitySnapshot */

/** @param {string | null | undefined} value */
function timestamp(value) {
  if (!value) return null;
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? new Date(ms).toISOString() : null;
}

/** Current observations, not reconstructed run or delivery history.
 * @param {Submission} submission
 * @param {Activity | null} activity */
export function receiptTimeline(submission, activity) {
  const rows = [
    {
      id: "submitted",
      kind: "Submission",
      name: `Submitted by ${submission.submitted_by}`,
      detail: submission.id,
      status: "recorded",
      at: timestamp(submission.submitted_at),
    },
    {
      id: "delivery",
      kind: "Delivery",
      name: "Latest delivery update",
      detail: `${submission.attempts} delivery attempt${submission.attempts === 1 ? "" : "s"}`,
      status: submission.status,
      at: timestamp(submission.updated_at),
    },
  ];
  for (const [key, kind] of [
    ["playbooks", "Playbook"],
    ["actions", "Action"],
    ["blocks", "Block"],
  ]) {
    const group =
      activity?.[/** @type {'playbooks'|'actions'|'blocks'} */ (key)];
    for (const run of group?.items || []) {
      rows.push({
        id: `${key}:${run.id}`,
        kind: run.block_type || kind,
        name: run.name,
        detail: `${key === "blocks" ? "Block" : "Run"} #${run.id}${run.playbook_run_id ? ` · Playbook run #${run.playbook_run_id}` : ""}`,
        status: run.status,
        at: timestamp(run.updated_at),
      });
    }
  }
  return rows.sort((a, b) => {
    if (!a.at) return b.at ? 1 : 0;
    if (!b.at) return -1;
    return a.at.localeCompare(b.at);
  });
}

/** Only export the public receipt fields; never connection or delivery credentials.
 * @param {Submission} s */
function receiptRecord(s) {
  return {
    id: s.id,
    workspace_id: s.form.workspace_id || "security",
    form_id: s.form_id,
    form_title: s.form_title,
    form_version: s.form_version,
    submitted_by: s.submitted_by,
    submitted_at: s.submitted_at,
    updated_at: s.updated_at,
    status: s.status,
    attempts: s.attempts,
    error: s.error,
    inputs: s.inputs,
    approval: s.approval ?? null,
    container_id: s.container_id,
    artifact_id: s.artifact_id,
    event_url: s.event_url,
    demo: s.demo,
    form_snapshot: {
      id: s.form.id,
      version: s.form.version,
      revision: s.form.revision,
      title: s.form.title,
      fields: s.form.fields,
      mapping: s.form.mapping,
      updated_by: s.form.updated_by,
      updated_at: s.form.updated_at,
    },
  };
}

/** @param {Submission} submission
 * @param {ActivitySnapshot} snapshot
 * @param {{exported_at: string, exported_by: string, app_version: string}} meta */
export function receiptExport(submission, snapshot, meta) {
  return {
    schema_version: 1,
    export_type: "actionstack_receipt",
    ...meta,
    scope:
      "Current receipt and last loaded SOAR activity. Not a complete or tamper-evident audit log.",
    activity_note:
      "Run timestamps are last updates, not start or completion times. Missing times, errors, truncation flags, and result limits are preserved. Includes manual runs and reruns on the event.",
    receipt: receiptRecord(submission),
    activity: snapshot.data,
    activity_error: snapshot.error || null,
    activity_loading: snapshot.loading,
    timeline: receiptTimeline(submission, snapshot.data),
  };
}

/** Quote every cell and neutralize spreadsheet formulas, including whitespace prefixes.
 * @param {unknown} value */
export function csvCell(value) {
  let text =
    value == null
      ? ""
      : typeof value === "object"
        ? JSON.stringify(value)
        : String(value);
  if (/^[\s\u0000-\u001f]*[=+@-]/.test(text) || /^[\t\r\n]/.test(text))
    text = "'" + text;
  return '"' + text.replaceAll('"', '""') + '"';
}

/** @param {Submission[]} submissions
 * @param {{exported_at: string, exported_by: string, app_version: string, workspace_id: string, mine: boolean}} meta */
export function submissionsCsv(submissions, meta) {
  const columns = [
    "exported_at",
    "exported_by",
    "app_version",
    "scope",
    "workspace_filter",
    "ownership_filter",
    "submission_id",
    "workspace_id",
    "form_id",
    "form_title",
    "form_version",
    "submitted_by",
    "submitted_at",
    "updated_at",
    "delivery_status",
    "delivery_attempts",
    "delivery_error",
    "soar_label",
    "soar_event_id",
    "artifact_id",
    "event_url",
    "automation_enabled",
    "approval_required",
    "approval_policy",
    "demo",
    "inputs_json",
  ];
  const rows = submissions.map((s) => [
    meta.exported_at,
    meta.exported_by,
    meta.app_version,
    "Filtered recent submissions (up to 200); delivery snapshot; SOAR activity is in receipt exports",
    meta.workspace_id,
    meta.mine ? "mine" : "workspace",
    s.id,
    s.form.workspace_id || "security",
    s.form_id,
    s.form_title,
    s.form_version,
    s.submitted_by,
    s.submitted_at,
    s.updated_at,
    s.status,
    s.attempts,
    s.error,
    s.form.mapping.label,
    s.container_id,
    s.artifact_id,
    s.event_url,
    s.form.mapping.run_automation,
    s.approval?.approval_required,
    s.approval?.approval_policy,
    s.demo,
    s.inputs,
  ]);
  return (
    "\uFEFF" +
    [columns, ...rows].map((row) => row.map(csvCell).join(",")).join("\r\n") +
    "\r\n"
  );
}

/** @param {string} contents @param {string} filename @param {string} mime */
export function downloadAudit(contents, filename, mime) {
  const url = URL.createObjectURL(new Blob([contents], { type: mime }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename.replace(/[^a-zA-Z0-9._-]/g, "_");
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
