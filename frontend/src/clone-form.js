import { cloneDefinition } from "./browser-compat.js";

/** @param {import('./types').Form} source
 * @param {string} suffix
 * @returns {import('./types').Form} */
export function cloneForm(source, suffix) {
  const title = source.title.slice(0, 110) + " (copy)";
  const slug =
    title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .replace(/^[^a-z]+/, "")
      .slice(0, 48)
      .replace(/-$/g, "") || "form";
  return {
    workspace_id: source.workspace_id || "security",
    id: slug + "-" + suffix,
    title,
    description: source.description,
    category: source.category,
    icon: source.icon,
    accent: source.accent,
    intro: source.intro,
    fields: cloneDefinition(source.fields),
    mapping: cloneDefinition(source.mapping),
    access: cloneDefinition(source.access),
    revision: 0,
    version: 0,
    state: "draft",
  };
}
