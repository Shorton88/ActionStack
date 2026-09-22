import { useEffect, useState } from "react";
import { api } from "./api";
import type { CountGroup } from "./RunCounts";

type Summary = {
  playbooks: CountGroup;
  actions: CountGroup;
  checked_at: string;
};

export function useSubmissionActivity(
  ids: string[],
  enabled: boolean,
  refresh: number,
) {
  const [data, setData] = useState<Record<string, Summary>>({});
  const key = ids.join(",");
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    setData({});
    async function poll() {
      if (stopped) return;
      if (!document.hidden) {
        const queue = key ? key.split(",") : [];
        async function worker() {
          while (!stopped && !document.hidden && queue.length) {
            const id = queue.shift()!;
            try {
              const result = await api<Summary>(
                `/submissions/${id}/activity-summary`,
              );
              if (!stopped) setData((prior) => ({ ...prior, [id]: result }));
            } catch (error) {
              if (!stopped)
                setData((prior) => {
                  const group = {
                    total: null,
                    counts: null,
                    truncated: false,
                    error: (error as Error).message,
                  };
                  return {
                    ...prior,
                    [id]: { playbooks: group, actions: group, checked_at: "" },
                  };
                });
            }
          }
        }
        // Only the current ten-row page is polled, with three reads in flight.
        await Promise.all([worker(), worker(), worker()]);
      }
      if (!stopped) timer = setTimeout(poll, 30000);
    }
    if (enabled && key) void poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [key, enabled, refresh]);
  return data;
}
