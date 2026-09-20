import { Fragment, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { api } from "./api";
import type { Activity, RunGroup } from "./types";

function Runs({ title, group }: { title: string; group: RunGroup }) {
  return (
    <div className="activity-group">
      <h4>
        {title}
        {group.total !== null ? ` (${group.total})` : ""}
      </h4>
      {group.error ? (
        <p role="status" className="activity-error">
          {group.error}
        </p>
      ) : (
        <>
          {!group.items.length && (
            <p className="muted">No {title.toLowerCase()} reported yet.</p>
          )}
          {group.items.map((run) => (
            <div className="activity-run" key={run.id}>
              <div>
                <b>{run.name}</b>
                <small>
                  Run #{run.id}
                  {run.playbook_run_id
                    ? ` · Playbook run #${run.playbook_run_id}`
                    : ""}
                </small>
                {run.summaries?.map((s, i) => (
                  <Fragment key={s.app_run_id + ":" + i}>
                    {s.summary !== undefined && (
                      <details className="actionstack-run-summary">
                        <summary>
                          Action summary · {s.status} · app run #{s.app_run_id}
                        </summary>
                        <pre>
                          {typeof s.summary === "string"
                            ? s.summary
                            : JSON.stringify(s.summary, null, 2)}
                        </pre>
                      </details>
                    )}
                    {s.data !== undefined && (
                      <details className="actionstack-run-summary">
                        <summary>
                          Result data · {s.status} · app run #{s.app_run_id}
                        </summary>
                        <pre>
                          {typeof s.data === "string"
                            ? s.data
                            : JSON.stringify(s.data, null, 2)}
                        </pre>
                        {s.data_truncated && (
                          <p className="muted">
                            Showing a limited preview. Open SOAR for complete
                            results.
                          </p>
                        )}
                      </details>
                    )}
                  </Fragment>
                ))}
              </div>
              <span className={`run-status run-${run.status}`}>
                {run.status === "success"
                  ? "Succeeded"
                  : run.status.charAt(0).toUpperCase() + run.status.slice(1)}
              </span>
            </div>
          ))}
          {group.summary_error && (
            <p role="status" className="activity-error">
              {group.summary_error}
            </p>
          )}
          {group.summary_truncated && (
            <p className="muted">
              Some action results are shortened or omitted. Open SOAR for all
              results.
            </p>
          )}
          {group.truncated && (
            <p className="muted">
              Showing the latest {group.items.length} of {group.total}. Open
              SOAR for the complete history.
            </p>
          )}
        </>
      )}
    </div>
  );
}

export function AutomationActivity({
  id,
  containerId,
  enabled,
}: {
  id: string;
  containerId: number | null;
  enabled: boolean;
}) {
  const [data, setData] = useState<Activity | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    setData(null);
    setError("");
    setBusy(false);
    async function poll() {
      if (stopped || !containerId) return;
      if (!document.hidden) {
        setBusy(true);
        try {
          const next = await api<Activity>(`/submissions/${id}/activity`);
          if (!stopped) {
            setData(next);
            setError("");
          }
        } catch (e) {
          if (!stopped) setError((e as Error).message);
        } finally {
          if (!stopped) setBusy(false);
        }
      }
      if (!stopped) timer = setTimeout(poll, 30000);
    }
    void poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [id, containerId, refresh]);
  return (
    <section
      className="automation-activity"
      aria-label="SOAR automation activity"
    >
      <div className="activity-heading">
        <h3>SOAR automation</h3>
        <button
          className="button"
          disabled={busy || !containerId}
          onClick={() => setRefresh((n) => n + 1)}
        >
          <RefreshCw size={14} className={busy ? "spin" : ""} />
          Refresh
        </button>
      </div>
      <p className="muted">
        {enabled
          ? "Automatic execution requested on delivery."
          : "Automatic execution was disabled for this submission."}{" "}
        Event activity includes manual runs and reruns.
      </p>
      {!containerId ? (
        <p className="muted">Waiting for a SOAR event ID.</p>
      ) : (
        <>
          {error && (
            <p role="status" className="activity-error">
              Status unavailable: {error}
              {data
                ? " The results below are from the last successful refresh."
                : ""}
            </p>
          )}
          {!data && !error && (
            <p className="muted">
              {busy
                ? "Checking SOAR…"
                : "Refresh resumes when this tab is visible."}
            </p>
          )}
          {data && (
            <>
              {data.demo && (
                <p className="muted">Demo mode does not run playbooks.</p>
              )}
              <Runs title="Playbooks" group={data.playbooks} />
              <Runs title="Actions" group={data.actions} />
              <small className="muted">
                Last checked {new Date(data.checked_at).toLocaleTimeString()} ·
                Refreshes every 30 seconds while this receipt is visible.
              </small>
            </>
          )}
          <p className="muted">
            Run status does not confirm an approval decision or a successful
            outcome. Open SOAR for those details.
          </p>
        </>
      )}
    </section>
  );
}
