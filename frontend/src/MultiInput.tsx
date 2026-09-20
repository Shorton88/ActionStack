import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import type { Field } from "./types";
export function ValueChips({
  values,
  labels = {},
  onChange,
}: {
  values: string[];
  labels?: Record<string, string>;
  onChange: (values: string[]) => void;
}) {
  return (
    <div className="actionstack-value-chips">
      {values.map((v, i) => (
        <span key={v}>
          {labels[v] || v}
          <button
            type="button"
            aria-label={"Remove " + (labels[v] || v)}
            onClick={() => onChange(values.filter((_, n) => n !== i))}
          >
            <X size={13} />
          </button>
        </span>
      ))}
    </div>
  );
}
export function MultiInput({
  field,
  value,
  onChange,
}: {
  field: Field;
  value: string[];
  onChange: (v: string[]) => void;
}) {
  const [text, setText] = useState(""),
    [error, setError] = useState("");
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    ref.current?.setCustomValidity(
      text.trim() ? "Press Enter or Add to include this value." : error,
    );
  }, [text, error]);
  function add() {
    const next = text.trim();
    if (!next) return;
    if (value.includes(next)) {
      setError("This item is already added.");
      return;
    }
    if (value.length >= 25) {
      setError("You can add up to 25 items.");
      return;
    }
    onChange([...value, next]);
    setText("");
    setError("");
  }
  return (
    <div className="actionstack-multi-input">
      <ValueChips
        values={value}
        onChange={(v) => {
          onChange(v);
          setError("");
        }}
      />
      <div className="actionstack-multi-entry">
        <input
          ref={ref}
          id={"input-" + field.key}
          aria-describedby={"input-" + field.key + "-help"}
          required={field.required && !value.length}
          value={text}
          maxLength={200}
          placeholder={field.placeholder || "Type a value and press Enter"}
          onChange={(e) => {
            setText(e.target.value);
            setError("");
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.nativeEvent.isComposing) {
              e.preventDefault();
              add();
            }
          }}
        />
        <button
          type="button"
          className="button"
          disabled={!text.trim()}
          onClick={add}
        >
          Add
        </button>
      </div>
      <small role="status">
        {error || `${value.length}/25 items · Press Enter to add each value.`}
      </small>
    </div>
  );
}
