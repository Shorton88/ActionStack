/** @param {string} status */
export function runStatusLabel(status) {
  if (status === "success") return "Succeeded";
  if (status === "mixed") return "Mixed results";
  if (status === "incomplete") return "Results incomplete";
  return status.charAt(0).toUpperCase() + status.slice(1).replaceAll("_", " ");
}
