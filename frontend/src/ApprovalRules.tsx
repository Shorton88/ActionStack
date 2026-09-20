import { LockKeyhole, Plus, Trash2 } from "lucide-react";
import type { Form, ApprovalRule } from "./types";
import { approvalRule } from "./approval.js";

export function ApprovalRules({
  form,
  onChange,
}: {
  form: Form;
  onChange: (rule: ApprovalRule) => void;
}) {
  const rule = approvalRule(form);
  const fields = form.fields.filter((f) =>
    ["select", "radio", "checkbox"].includes(f.type),
  );
  const initial = (key = fields[0]?.key) => {
    const f = fields.find((x) => x.key === key);
    return {
      field: key || "",
      equals: f?.type === "checkbox" ? true : f?.options?.[0]?.value || "",
    };
  };
  return (
    <div className="config-panel">
      <div className="config-heading">
        <LockKeyhole size={23} />
        <div>
          <h2>When approval is needed</h2>
          <p>
            Choose which requests your SOAR playbook must send for approval.
          </p>
        </div>
      </div>
      <div className="notice">
        These rules mark the request as requiring approval. Your SOAR playbook
        must enforce the approval before taking action. The form does not send
        Teams messages or collect approval decisions.
      </div>
      <label className="field">
        Require approval
        <select
          value={rule.mode}
          onChange={(e) => {
            const mode = e.target.value as ApprovalRule["mode"];
            onChange({
              ...rule,
              mode,
              conditions:
                mode === "conditional"
                  ? rule.conditions.length
                    ? rule.conditions
                    : fields.length
                      ? [initial()]
                      : []
                  : [],
            });
          }}
        >
          <option value="never">Never</option>
          <option value="always">Every request</option>
          <option value="conditional">When any condition matches</option>
        </select>
      </label>
      {rule.mode === "conditional" && (
        <div className="approval-conditions">
          <p className="muted">
            A request needs approval if any row matches. Only submitted, visible
            fields are evaluated.
          </p>
          {rule.conditions.map((condition, i) => {
            const field = fields.find((f) => f.key === condition.field);
            const choices =
              field?.type === "checkbox"
                ? [
                    { value: "true", label: "Checked" },
                    { value: "false", label: "Not checked" },
                  ]
                : field?.options || [];
            return (
              <div className="approval-condition" key={i}>
                <label className="field">
                  Field
                  <select
                    value={condition.field}
                    onChange={(e) =>
                      onChange({
                        ...rule,
                        conditions: rule.conditions.map((c, n) =>
                          n === i ? initial(e.target.value) : c,
                        ),
                      })
                    }
                  >
                    {!field && (
                      <option value={condition.field}>
                        Choose an available field
                      </option>
                    )}
                    {fields.map((f) => (
                      <option key={f.key} value={f.key}>
                        {f.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Equals
                  <select
                    value={String(condition.equals)}
                    onChange={(e) =>
                      onChange({
                        ...rule,
                        conditions: rule.conditions.map((c, n) =>
                          n === i
                            ? {
                                ...c,
                                equals:
                                  field?.type === "checkbox"
                                    ? e.target.value === "true"
                                    : e.target.value,
                              }
                            : c,
                        ),
                      })
                    }
                  >
                    {!choices.some(
                      (o) => o.value === String(condition.equals),
                    ) && (
                      <option value={String(condition.equals)}>
                        Choose an available value
                      </option>
                    )}
                    {choices.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  className="button"
                  aria-label={`Remove approval condition ${i + 1}`}
                  onClick={() =>
                    onChange({
                      ...rule,
                      conditions: rule.conditions.filter((_, n) => n !== i),
                    })
                  }
                >
                  <Trash2 size={16} />
                </button>
              </div>
            );
          })}
          {!fields.length && (
            <p className="muted">
              Add a dropdown, radio, or checkbox field in Build to use a
              condition.
            </p>
          )}
          <button
            className="button"
            disabled={!fields.length || rule.conditions.length >= 20}
            onClick={() =>
              onChange({ ...rule, conditions: [...rule.conditions, initial()] })
            }
          >
            <Plus size={16} />
            Add condition
          </button>
        </div>
      )}
      <p className="muted">
        Approval workflow: handled by the SOAR playbook. Your playbook can use
        Teams or any other approval channel.
      </p>
      <p className="muted">
        Publish to apply these rules to new requests. Existing submissions
        retain their original approval requirement.
      </p>
    </div>
  );
}
