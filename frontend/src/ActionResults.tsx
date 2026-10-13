import { keyedActionResults } from "./action-results.js";
import { runStatusLabel } from "./run-status.js";
import type { RunGroup } from "./types";

function resultText(value: unknown) {
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

export function ActionResults({ run }: { run: RunGroup["items"][number] }) {
  const results = run.summaries || [];
  const partial = run.result_counts_complete === false;
  if (!results.length && !partial) return null;
  const counts =
    run.result_counts ||
    results.reduce<Record<string, number>>((outcomes, result) => {
      outcomes[result.status] = (outcomes[result.status] || 0) + 1;
      return outcomes;
    }, {});
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0);
  return (
    <div className="actionstack-action-results">
      <p className="actionstack-result-counts">
        {partial ? "Partial action result counts" : "Reported action results"}:{" "}
        {Object.entries(counts)
          .filter(([, count]) => count > 0)
          .map(
            ([status, count]) =>
              `${count} ${runStatusLabel(status).toLowerCase()}`,
          )
          .join(" · ") || "No results loaded"}
      </p>
      {partial && (
        <p className="muted">
          Loaded {total}
          {run.result_total != null ? ` of ${run.result_total}` : ""} results.
          Counts are incomplete; additional failures may be unreported. Open
          SOAR for all outcomes.
        </p>
      )}
      {keyedActionResults(results).map(({ result, key }, i) => (
        <section
          className="actionstack-action-result"
          aria-label={`Action result ${i + 1}: ${runStatusLabel(result.status)}, app run ${result.app_run_id}`}
          key={key}
        >
          <div className="actionstack-result-heading">
            <div>
              <b>Action result {i + 1}</b>
              <small>App run #{result.app_run_id}</small>
            </div>
            <span className={`run-status run-${result.status}`}>
              {runStatusLabel(result.status)}
            </span>
          </div>
          {result.summary !== undefined && (
            <details className="actionstack-run-summary">
              <summary>Action summary</summary>
              <pre>{resultText(result.summary)}</pre>
            </details>
          )}
          {result.data !== undefined && (
            <details className="actionstack-run-summary">
              <summary>Result data</summary>
              <pre>{resultText(result.data)}</pre>
              {result.data_truncated && (
                <p className="muted">
                  Showing a limited preview. Open SOAR for complete results.
                </p>
              )}
            </details>
          )}
          {result.summary === undefined && result.data === undefined && (
            <p className="muted">
              No summary or result data reported for this result.
            </p>
          )}
        </section>
      ))}
      {total > results.length && (
        <p className="muted">
          Showing details for {results.length} of {total} reported action
          results. Open SOAR for all results.
        </p>
      )}
    </div>
  );
}
