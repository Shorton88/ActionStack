/**
 * Uses getRandomValues, which remains available when randomUUID is unavailable
 * (for example on an intranet HTTP origin). Never falls back to Math.random.
 * @param {Pick<Crypto, 'getRandomValues'>} [source]
 */
export function randomId(source = globalThis.crypto) {
  if (!source || typeof source.getRandomValues !== "function") {
    throw new Error(
      "This browser cannot generate request IDs. Use a supported browser.",
    );
  }
  const bytes = source.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join(
    "",
  );
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/** Form definitions contain JSON data only; no browser structuredClone is needed.
 * @template T
 * @param {T} value
 * @returns {T}
 */
export function cloneDefinition(value) {
  return JSON.parse(JSON.stringify(value));
}

/**
 * Preserve the exact SHA-256 storage key across browser environments. The server
 * fallback only computes the hash; it never records or delivers a submission.
 * @param {string} value
 * @param {(value: string) => Promise<string>} serverHash
 * @param {Pick<Crypto, 'subtle'> | undefined} [source]
 */
export async function submissionFingerprint(
  value,
  serverHash,
  source = globalThis.crypto,
) {
  if (!source?.subtle) return serverHash(value);
  const bytes = await source.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return Array.from(new Uint8Array(bytes), (b) =>
    b.toString(16).padStart(2, "0"),
  ).join("");
}
