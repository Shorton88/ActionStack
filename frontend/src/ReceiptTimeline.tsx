import { receiptTimeline } from "./receipt-audit.js";
import type { Activity, Submission } from "./types";

export function ReceiptTimeline({
  submission,
  activity,
}: {
  submission: Submission;
  activity: Activity | null;
}) {
  const rows = receiptTimeline(submission, activity);
  return (
    <div className="actionstack-receipt-timeline">
      <p className="muted">
        Oldest update first. Times show the latest reported updates. Previous
        status changes and individual delivery attempts are not retained here.
      </p>
      {activity &&
        Object.entries({
          playbooks: activity.playbooks,
          actions: activity.actions,
          blocks: activity.blocks,
        }).map(
          ([key, group]) =>
            group && (
              <div key={key}>
                {group.error && (
                  <p role="status" className="activity-error">
                    {key}: {group.error}
                  </p>
                )}
                {(group.truncated ||
                  group.summary_truncated ||
                  group.summary_error ||
                  group.notice) && (
                  <p className="muted">
                    {key}:{" "}
                    {group.notice ||
                      "Some results are limited or unavailable. Use Grouped view for details and SOAR for the complete history."}
                  </p>
                )}
              </div>
            ),
        )}
      <ol aria-label="Receipt timeline">
        {rows.map((row) => (
          <li key={row.id}>
            <small>
              {row.kind} ·{" "}
              {row.at ? (
                <time dateTime={row.at}>
                  {new Date(row.at).toLocaleString(undefined, {
                    timeZoneName: "short",
                  })}
                </time>
              ) : (
                "Time not reported"
              )}
            </small>
            <div>
              <b>{row.name}</b>
              <span className={`run-status run-${row.status}`}>
                {row.status === "submitted"
                  ? "Delivered"
                  : row.status === "success"
                    ? "Succeeded"
                    : row.status.charAt(0).toUpperCase() +
                      row.status.slice(1).replaceAll("_", " ")}
              </span>
            </div>
            <small className="actionstack-timeline-reference">
              {row.detail}
            </small>
          </li>
        ))}
      </ol>
    </div>
  );
}
