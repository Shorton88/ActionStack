import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import type { Field } from "./types";
import { mergeValues } from "./multi-values.js";
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
  function add(raw = text) {
    try {
      onChange(mergeValues(value, raw));
      setText("");
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
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
          maxLength={5025}
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
          onPaste={(e) => {
            const pasted = e.clipboardData.getData("text");
            if (!/[,;\r\n]/.test(pasted)) return;
            e.preventDefault();
            const el = e.currentTarget;
            const raw =
              text.slice(0, el.selectionStart ?? text.length) +
              pasted +
              text.slice(el.selectionEnd ?? text.length);
            setText(raw);
            add(raw);
          }}
        />
        <button
          type="button"
          className="button"
          disabled={!text.trim()}
          onClick={() => add()}
        >
          Add
        </button>
      </div>
      <small role="status">
        {error ||
          `${value.length}/25 items · Press Enter to add. Paste a comma-separated list to add several.`}
      </small>
    </div>
  );
}
