/** Errors safe to display without exposing response bodies or credentials. */
export class ApiError extends Error {
  /** @param {string} message @param {number} status @param {Record<string,string>} [fields] */
  constructor(message, status, fields = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fields = fields;
  }
}

/**
 * Cookies are shared across ports. Prefer the current Splunk Web port, then a
 * single unambiguous candidate for reverse proxies with a different public port.
 * Never send another instance's token merely because it appeared first.
 * @param {string} cookie
 * @param {string} port
 * @param {string} protocol
 * @returns {string | undefined}
 */
export function csrfToken(cookie, port, protocol) {
  const candidates = cookie.split(";").flatMap((part) => {
    const match = /^splunkweb_csrf_token_(\d+)=(.*)$/.exec(part.trim());
    if (!match) return [];
    let value;
    try {
      value = decodeURIComponent(match[2]);
    } catch {
      return [];
    }
    if (value.startsWith('"') && value.endsWith('"'))
      value = value.slice(1, -1);
    if (!value || /[\s\x00-\x1f\x7f]/.test(value)) return [];
    return [{ port: match[1], value }];
  });
  const effectivePort = port || (protocol === "https:" ? "443" : "80");
  const exact = candidates.filter((entry) => entry.port === effectivePort);
  const values = [
    ...new Set((exact.length ? exact : candidates).map((entry) => entry.value)),
  ];
  return values.length === 1 ? values[0] : undefined;
}

/**
 * @typedef {Object} BrowserEnvironment
 * @property {string} pathname
 * @property {string} port
 * @property {string} protocol
 * @property {() => string} cookie
 * @property {typeof fetch} fetch
 */

/** @param {BrowserEnvironment} env */
export function createTransport(env) {
  const inSplunk = env.pathname.includes("/app/splunk_actionstack");
  const root = inSplunk
    ? env.pathname.split("/app/")[0] + "/splunkd/__raw/services/actionstack"
    : "/api";
  /** @param {string} path @param {unknown} [body] */
  return async function request(path, body) {
    /** @type {Record<string,string>} */
    const headers = {
      Accept: "application/json",
      "X-ActionStack-Request": "1",
      "X-Requested-With": "XMLHttpRequest",
    };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (inSplunk) {
      // Resolve per request, so a renewed Splunk session uses its current token.
      const token = csrfToken(env.cookie(), env.port, env.protocol);
      if (token) headers["X-Splunk-Form-Key"] = token;
      else if (body !== undefined) {
        throw new ApiError(
          "Splunk’s CSRF token is missing or ambiguous. Reload this Splunk page and sign in again if needed, then retry. No request was sent.",
          401,
        );
      }
    }
    let response;
    try {
      response = await env.fetch(root + path, {
        method: body === undefined ? "GET" : "POST",
        headers,
        credentials: "same-origin",
        cache: "no-store",
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(
        "The connection was interrupted. Your submission key has been kept so you can safely try again.",
        0,
      );
    }
    let raw;
    try {
      raw = await response.text();
    } catch {
      throw new ApiError(
        "The response was interrupted. Check My submissions before retrying a request.",
        response.status,
      );
    }
    if (
      inSplunk &&
      [401, 403].includes(response.status) &&
      /csrf|cross.site.request.forgery/i.test(raw + " " + response.statusText)
    ) {
      throw new ApiError(
        "Splunk Web rejected the request because CSRF validation failed. Reload the page and retry; sign in again if it persists. The request did not reach SOAR.",
        response.status,
      );
    }
    if (inSplunk && response.status === 401) {
      throw new ApiError(
        "Your Splunk session was rejected or has expired. Reload the page and sign in again, then retry.",
        401,
      );
    }
    let result;
    try {
      result = JSON.parse(raw);
    } catch {
      throw new ApiError(
        inSplunk
          ? "Splunk returned an unexpected response. Reload the page and check your Splunk session."
          : "The local demo API returned an unexpected response. Check that the demo server is running.",
        response.status,
      );
    }
    if (!result || typeof result !== "object" || Array.isArray(result)) {
      throw new ApiError(
        "The server returned an unexpected response.",
        response.status,
      );
    }
    if (!response.ok || result.error) {
      throw new ApiError(
        typeof result.error === "string" ? result.error : "Request failed.",
        response.status,
        result.fields,
      );
    }
    if (!Object.prototype.hasOwnProperty.call(result, "data")) {
      throw new ApiError(
        "The server returned an unexpected response.",
        response.status,
      );
    }
    return result.data;
  };
}
