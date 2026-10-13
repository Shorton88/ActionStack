/** Keep disclosure state with the returned result when asynchronous results
 * arrive in a different order. SOAR does not always report an action-result ID.
 * Identical results remain separate groups rather than being deduplicated.
 * @param {import('./types').ActionResult[]} results */
export function keyedActionResults(results) {
  const occurrences = new Map();
  return results.map((result) => {
    const signature = JSON.stringify({
      app_run_id: result.app_run_id,
      status: result.status,
      summary: result.summary,
      data: result.data,
      data_truncated: result.data_truncated,
    });
    const occurrence = occurrences.get(signature) || 0;
    occurrences.set(signature, occurrence + 1);
    return { result, key: `${signature}:${occurrence}` };
  });
}
