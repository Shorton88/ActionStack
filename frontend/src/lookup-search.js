/** Serialize searches and discard replies superseded by newer input.
 * @param {(term:string)=>Promise<any>} search
 * @param {(result:any,error:string)=>void} receive
 * @param {number} minimum
 * @param {number} delay
 */
export function lookupSearch(search, receive, minimum = 3, delay = 50) {
  let version = 0,
    running = false,
    disposed = false;
  /** @type {ReturnType<typeof setTimeout>|undefined} */ let timer;
  /** @type {{term:string,version:number}|null} */ let ready = null;
  // Per-field, per-mount cache only. Submission always rechecks live lookup data.
  /** @type {Map<string,{result:any,expires:number}>} */ const cache =
    new Map();
  async function pump() {
    if (running || !ready || disposed) return;
    const job = ready;
    ready = null;
    running = true;
    try {
      const result = await search(job.term);
      if (!disposed) {
        cache.delete(job.term);
        cache.set(job.term, { result, expires: Date.now() + 30000 });
        if (cache.size > 30) cache.delete(cache.keys().next().value ?? "");
      }
      if (!disposed && job.version === version) receive(result, "");
    } catch (e) {
      if (!disposed && job.version === version)
        receive(null, e instanceof Error ? e.message : "Search failed.");
    } finally {
      running = false;
      void pump();
    }
  }
  return {
    set(/** @type {string} */ term) {
      version++;
      clearTimeout(timer);
      ready = null;
      receive(null, "");
      if (term.length < minimum) return;
      const cached = cache.get(term);
      if (cached && cached.expires > Date.now()) {
        receive(cached.result, "");
        return;
      }
      const current = version;
      timer = setTimeout(() => {
        ready = { term, version: current };
        void pump();
      }, delay);
    },
    dispose() {
      disposed = true;
      version++;
      clearTimeout(timer);
      ready = null;
      cache.clear();
    },
  };
}
