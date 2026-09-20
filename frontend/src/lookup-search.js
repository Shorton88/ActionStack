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
  async function pump() {
    if (running || !ready || disposed) return;
    const job = ready;
    ready = null;
    running = true;
    try {
      const result = await search(job.term);
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
    },
  };
}
