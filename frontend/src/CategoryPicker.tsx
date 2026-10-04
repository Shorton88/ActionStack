import { useState } from "react";

export function CategoryPicker({
  value,
  categories,
  onChange,
}: {
  value: string;
  categories: string[];
  onChange: (value: string) => void;
}) {
  const [adding, setAdding] = useState(false);
  const choices = Array.from(
    new Set(
      ["General", ...categories, value].map((c) => c.trim()).filter(Boolean),
    ),
  ).sort((a, b) => a.localeCompare(b));
  return (
    <div>
      <label className="field">
        Category
        <select
          value={adding ? "new" : "category:" + (value.trim() || "General")}
          onChange={(e) => {
            if (e.target.value === "new") {
              setAdding(true);
              onChange("");
            } else {
              setAdding(false);
              onChange(e.target.value.slice(9));
            }
          }}
        >
          {choices.map((c) => (
            <option key={c} value={"category:" + c}>
              {c}
            </option>
          ))}
          <option value="new">Add a new category…</option>
        </select>
      </label>
      {adding && (
        <label className="field">
          New category
          <input
            autoFocus
            maxLength={80}
            value={value}
            placeholder="e.g. Identity and access"
            onChange={(e) => onChange(e.target.value)}
          />
          <small>Available on other forms after you save this form.</small>
        </label>
      )}
    </div>
  );
}
