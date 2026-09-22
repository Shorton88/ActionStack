import type { RunGroup } from "./types";

export type CountGroup = Pick<
  RunGroup,
  "counts" | "total" | "truncated" | "error"
>;

export function RunCounts({
  group,
  label,
}: {
  group?: CountGroup;
  label: string;
}) {
  if (!group) return <span className="muted">Checking…</span>;
  if (group.error || group.total === null)
    return (
      <span className="muted" title={group.error || "Status unavailable"}>
        Unavailable
      </span>
    );
  return (
    <span
      className="actionstack-run-counts"
      aria-label={`${label}: ${group.total} total`}
    >
      <b>
        {group.total} <span className="muted">total</span>
      </b>
      {Object.entries(group.counts || {}).map(
        ([status, count]) =>
          count > 0 && (
            <span
              key={status}
              className={`run-status run-${status}`}
              title={`${count} ${status}${group.truncated ? " in the latest runs" : ""}`}
            >
              {status === "success"
                ? "✓"
                : status === "failed"
                  ? "✕"
                  : status === "running"
                    ? "↻"
                    : status === "pending"
                      ? "◷"
                      : status === "cancelled"
                        ? "−"
                        : "?"}{" "}
              {count}
              <span className="sr-only"> {status}</span>
            </span>
          ),
      )}
      {group.truncated && (
        <small title="Status counts cover the latest runs; open the receipt for details.">
          Recent runs
        </small>
      )}
    </span>
  );
}
