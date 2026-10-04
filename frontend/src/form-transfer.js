import { cloneDefinition } from "./browser-compat.js";

export const MAX_FORM_FILE_BYTES = 200 * 1024;

/** Export a portable definition, excluding environment-specific access and history.
 * @param {import('./types').Form} form @param {string} appVersion */
export function formExport(form, appVersion) {
  const { title, description, category, icon, accent, intro, fields, mapping } =
    form;
  return {
    format: "actionstack-form",
    format_version: 1,
    app_version: appVersion,
    form: cloneDefinition({
      title,
      description,
      category,
      icon,
      accent,
      intro,
      fields,
      mapping,
    }),
  };
}

/** @param {string} text @returns {unknown} */
export function parseFormFile(text) {
  if (new TextEncoder().encode(text).length > MAX_FORM_FILE_BYTES)
    throw new Error("Choose an ActionStack form JSON file under 200 KB.");
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("This file is not valid JSON.");
  }
  if (!data || data.format !== "actionstack-form" || data.format_version !== 1)
    throw new Error("Choose an ActionStack form export (format version 1).");
  return data;
}
