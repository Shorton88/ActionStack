/** Split pasted or typed lists, preserving order and removing duplicates.
 * @param {string[]} existing
 * @param {string} text
 * @param {boolean} [ignoreCase]
 */
export function mergeValues(existing, text, ignoreCase = false) {
  const added = text
    .split(/[,;\r\n]+/)
    .map((v) => v.trim())
    .filter(Boolean);
  if (added.some((v) => v.length > 200))
    throw new Error("Each item must be 200 characters or fewer.");
  const seen = new Set();
  const values = [...existing, ...added].filter((v) => {
    const key = ignoreCase ? v.toLowerCase() : v;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  if (values.length > 25)
    throw new Error("You can add up to 25 items. Nothing was added.");
  return values;
}
