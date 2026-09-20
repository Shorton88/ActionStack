import { useEffect, useRef, useState } from "react";
import { ValueChips } from "./MultiInput";
import { api } from "./api";
import { lookupSearch } from "./lookup-search.js";
import type { Field, Form, LookupConfig } from "./types";
export const defaultLookup: LookupConfig = {
  search: "| inputlookup identity_lookup_expanded | fields identity",
  app: "search",
  value_field: "identity",
  label_field: "identity",
  min_chars: 3,
  debounce_ms: 50,
};
export function LookupSettings({
  field,
  onChange,
}: {
  field: Field;
  onChange: (patch: Partial<Field>) => void;
}) {
  const c = field.lookup || defaultLookup;
  const change = (p: Partial<LookupConfig>) =>
    onChange({ lookup: { ...c, ...p } });
  return (
    <div className="actionstack-lookup-config">
      <h4>Lookup source</h4>
      <label className="field">
        Search
        <textarea
          value={c.search}
          onChange={(e) => change({ search: e.target.value })}
        />
        <small>
          Start with | inputlookup lookup_name. Add read-only SPL such as eval,
          where, rename, table or stats. Keep both result fields in the output.
          Macros, subsearches and commands that write data are not supported.
        </small>
      </label>
      <label className="field">
        Value field sent to SOAR
        <input
          value={
            c.value_field ??
            c.search.match(/\|\s*fields\s+(\w+)\s*$/i)?.[1] ??
            ""
          }
          onChange={(e) => change({ value_field: e.target.value })}
          placeholder="identity"
        />
      </label>
      <label className="field">
        Display label field
        <input
          value={
            c.label_field ??
            c.value_field ??
            c.search.match(/\|\s*fields\s+(\w+)\s*$/i)?.[1] ??
            ""
          }
          onChange={(e) => change({ label_field: e.target.value })}
          placeholder="display_name"
        />
        <small>
          Users can search by label or value. Only the selected value is
          submitted.
        </small>
      </label>
      <label className="field">
        Splunk app namespace
        <input
          value={c.app}
          onChange={(e) => change({ app: e.target.value })}
        />
        <small>
          Runs with the requesting user's lookup permissions in this app.
        </small>
      </label>
      <div className="two-column">
        <label className="field">
          Minimum characters
          <input
            type="number"
            min={3}
            max={10}
            value={c.min_chars}
            onChange={(e) => change({ min_chars: Number(e.target.value) })}
          />
        </label>
        <label className="field">
          Typing delay (ms)
          <input
            type="number"
            min={50}
            max={1000}
            value={c.debounce_ms}
            onChange={(e) => change({ debounce_ms: Number(e.target.value) })}
          />
        </label>
      </div>
      <p>
        Returns up to 25 prefix matches. Selected values are checked again when
        the request is submitted.
      </p>
    </div>
  );
}
export function LookupField({
  form,
  field,
  value,
  onChange,
  preview = false,
}: {
  form: Form;
  field: Field;
  value: string | string[];
  onChange: (v: string | string[]) => void;
  preview?: boolean;
}) {
  const multiple = field.type === "lookup_multi";
  const values = Array.isArray(value) ? value : [];
  const [term, setTerm] = useState(typeof value === "string" ? value : ""),
    [options, setOptions] = useState<{ value: string; label: string }[]>([]),
    [more, setMore] = useState(false),
    [error, setError] = useState(""),
    [searching, setSearching] = useState(false),
    [open, setOpen] = useState(false),
    [active, setActive] = useState(-1);
  const input = useRef<HTMLInputElement>(null),
    skipValueSync = useRef(false),
    selectedLabels = useRef<Record<string, string>>({}),
    queue = useRef<ReturnType<typeof lookupSearch> | null>(null);
  const c = field.lookup || defaultLookup,
    id = "input-" + field.key;
  useEffect(() => {
    if (skipValueSync.current) {
      skipValueSync.current = false;
      return;
    }
    if (!multiple)
      setTerm(selectedLabels.current[String(value)] || String(value || ""));
  }, [value, multiple]);
  useEffect(() => {
    input.current?.setCustomValidity(
      term && (multiple || !value)
        ? "Select a value from the lookup results."
        : "",
    );
  }, [term, value]);
  useEffect(() => {
    const q = lookupSearch(
      (t) =>
        api<{ options: { value: string; label: string }[]; more: boolean }>(
          preview ? "/admin/lookups/preview" : "/lookups/options",
          preview
            ? { config: c, term: t }
            : {
                form_id: form.id,
                form_version: form.version,
                field: field.key,
                term: t,
              },
        ),
      (result, message) => {
        setOptions(result?.options || []);
        setMore(!!result?.more);
        setError(message);
        if (result || message) setSearching(false);
        setActive(-1);
      },
      c.min_chars,
      c.debounce_ms,
    );
    queue.current = q;
    return () => q.dispose();
  }, [form.id, form.version, field.key, JSON.stringify(c), preview]);
  const select = (option: { value: string; label: string }) => {
    const v = option.value;
    queue.current?.set("");
    if (multiple && (values.includes(v) || values.length >= 25)) return;
    selectedLabels.current[v] = option.label;
    setTerm(multiple ? "" : option.label);
    onChange(multiple ? [...values, v] : v);
    setOpen(false);
    setSearching(false);
    input.current?.focus();
  };
  return (
    <div className="actionstack-lookup">
      {multiple && (
        <ValueChips
          values={values}
          labels={selectedLabels.current}
          onChange={onChange}
        />
      )}
      <input
        ref={input}
        id={id}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open && options.length > 0}
        aria-controls={id + "-results"}
        aria-activedescendant={
          active >= 0 ? id + "-option-" + active : undefined
        }
        autoComplete="off"
        required={field.required && (!multiple || !values.length)}
        placeholder={
          field.placeholder || "Type " + c.min_chars + " characters to search…"
        }
        value={term}
        maxLength={200}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onChange={(e) => {
          const t = e.target.value;
          if (!multiple && value) {
            skipValueSync.current = true;
            onChange("");
          }
          setTerm(t);
          setOpen(true);
          setSearching(t.length >= c.min_chars);
          queue.current?.set(t);
        }}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false);
          if (e.key === "ArrowDown" && options.length) {
            e.preventDefault();
            setOpen(true);
            setActive((n) => Math.min(n + 1, options.length - 1));
          }
          if (e.key === "ArrowUp" && options.length) {
            e.preventDefault();
            setActive((n) => Math.max(n - 1, 0));
          }
          if (e.key === "Enter" && term) e.preventDefault();
          if (e.key === "Enter" && open && active >= 0 && options[active]) {
            e.preventDefault();
            select(options[active]);
          }
        }}
      />
      {open && options.length > 0 && (
        <div
          id={id + "-results"}
          role="listbox"
          className="actionstack-lookup-results"
        >
          {options.map((o, i) => (
            <div
              id={id + "-option-" + i}
              key={o.value}
              role="option"
              aria-selected={i === active}
              aria-disabled={
                multiple && (values.includes(o.value) || values.length >= 25)
              }
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => select(o)}
            >
              {o.label}
            </div>
          ))}
        </div>
      )}
      <small role="status">
        {error ||
          (searching
            ? "Searching…"
            : multiple && !term
              ? values.length + "/25 selected · Search to add another."
              : !multiple && value
                ? "Selected from lookup"
                : term.length < c.min_chars
                  ? "Enter at least " + c.min_chars + " characters."
                  : more
                    ? "More matches available. Keep typing to narrow the list."
                    : options.length
                      ? options.length + " matches"
                      : "No matches found.")}
      </small>
    </div>
  );
}
