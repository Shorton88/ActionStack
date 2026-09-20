/** @param {import('./types').Form} form
 * @returns {import('./types').ApprovalRule} */
export function approvalRule(form) {
  return (
    (form.mapping.approval
      ? { ...form.mapping.approval, policy: "soar_playbook" }
      : undefined) ??
    (form.mapping.policy === "block_object"
      ? {
          mode: "conditional",
          policy: "soar_playbook",
          conditions: [{ field: "duration", equals: "forever" }],
        }
      : { mode: "never", policy: "soar_playbook", conditions: [] })
  );
}

/** Preview only; the server evaluates the published rule against validated inputs.
 * @param {import('./types').Form} form
 * @param {Record<string, unknown>} values */
export function approvalRequired(form, values) {
  const rule = approvalRule(form);
  return (
    rule.mode === "always" ||
    (rule.mode === "conditional" &&
      rule.conditions.some((c) => {
        const field = form.fields.find((f) => f.key === c.field);
        const value =
          values[c.field] ??
          field?.default ??
          (field?.type === "checkbox" ? false : undefined);
        return (
          field &&
          (!field.show_when ||
            values[field.show_when.field] === field.show_when.equals) &&
          value !== undefined &&
          value === c.equals
        );
      }))
  );
}
