import type { Field } from "./types";
export function FieldValidation({
  field,
  onChange,
}: {
  field: Field;
  onChange: (patch: Partial<Field>) => void;
}) {
  const rules = field.validation || [];
  const text = !["number", "checkbox"].includes(field.type);
  const types = [
    ["equals", "Equals"],
    ["not_equals", "Not equal"],
    ...(text
      ? [
          ["like", "Like"],
          ["not_like", "Not like"],
          ["regex", "Regex"],
        ]
      : []),
  ];
  const legacy = [
    ...(!text
      ? [
          ["regex", "Regex (text fields)"],
          ["like", "Like (text fields)"],
          ["not_like", "Not like (text fields)"],
        ]
      : []),
    ["ip_address", "IP address"],
    ["domain", "Domain"],
    ["sha1", "SHA-1 hash"],
    ["sha256", "SHA-256 hash"],
    ["min", "Minimum"],
    ["max", "Maximum"],
  ];
  function update(i: number, patch: Partial<(typeof rules)[number]>) {
    onChange({
      validation: rules.map((r, n) => (n === i ? { ...r, ...patch } : r)),
    });
  }
  if (field.type === "section") return null;
  return (
    <section className="actionstack-field-validation">
      <h4>Validation</h4>
      <p>
        Optional checks for this field.{" "}
        {["text_list", "lookup_multi", "multiselect"].includes(field.type)
          ? "Each item must pass."
          : "Empty optional fields are skipped."}
      </p>
      {rules.map((r, i) => (
        <div className="actionstack-field-rule" key={i}>
          <label className="field">
            Validation type
            <select
              value={r.operator}
              onChange={(e) =>
                update(i, { operator: e.target.value, value: "" })
              }
            >
              {[...types, ...legacy.filter(([v]) => v === r.operator)].map(
                ([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ),
              )}
            </select>
          </label>
          {!["ip_address", "domain", "sha1", "sha256"].includes(r.operator) && (
            <label className="field">
              Value
              <input
                value={String(r.value ?? "")}
                maxLength={r.operator === "regex" ? 512 : 200}
                placeholder={
                  r.operator === "like" || r.operator === "not_like"
                    ? "e.g. *@example.com"
                    : r.operator === "regex"
                      ? "e.g. INC-[0-9]+"
                      : field.type === "checkbox"
                        ? "true or false"
                        : "Value to compare"
                }
                onChange={(e) => update(i, { value: e.target.value })}
              />
              {["like", "not_like"].includes(r.operator) && (
                <small>
                  Use * for any text and ? for one character. Case-sensitive.
                </small>
              )}
              {r.operator === "regex" && (
                <small>Matches the whole value. Use (?i) to ignore case.</small>
              )}
            </label>
          )}
          <label className="field">
            Message to user
            <input
              value={r.message}
              maxLength={240}
              placeholder="Explain how to correct the value"
              onChange={(e) => update(i, { message: e.target.value })}
            />
          </label>
          {r.when && (
            <small>
              Applies when {r.when.field} = {String(r.when.equals)}
            </small>
          )}
          <button
            className="button"
            type="button"
            onClick={() =>
              onChange({ validation: rules.filter((_, n) => n !== i) })
            }
          >
            Remove check
          </button>
        </div>
      ))}
      <button
        type="button"
        className="button"
        disabled={rules.length >= 64}
        onClick={() =>
          onChange({
            validation: [
              ...rules,
              { operator: "equals", value: "", message: "Check this value." },
            ],
          })
        }
      >
        + Add validation
      </button>
    </section>
  );
}
