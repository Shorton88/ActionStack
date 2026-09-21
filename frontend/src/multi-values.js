/** Split pasted or typed lists, preserving order and removing duplicates.
 * @param {string[]} existing
 * @param {string} text
 */
export function mergeValues(existing, text) {
  const added = text
    .split(/[,;\r\n]+/)
    .map((v) => v.trim())
    .filter(Boolean);
  if (added.some((v) => v.length > 200))
    throw new Error("Each item must be 200 characters or fewer.");
  const values = [...new Set([...existing, ...added])];
  if (values.length > 25)
    throw new Error("You can add up to 25 items. Nothing was added.");
  return values;
}
