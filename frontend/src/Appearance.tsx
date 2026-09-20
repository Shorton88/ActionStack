import { formIcon, FormIconPicker } from "./FormIcons";
import type { Form, Preferences } from "./types";

export const accents = [
  ["violet", "Amethyst", "#c2a5f5", "#91c6df"],
  ["cyan", "Opal", "#85d5df", "#b3adf2"],
  ["rose", "Rose quartz", "#eba4cd", "#b2b7f1"],
  ["mint", "Aurora", "#8edfc1", "#a8b7f2"],
  ["amber", "Moonstone", "#efcd91", "#e4aed5"],
  ["indigo", "Twilight", "#a5b4fa", "#d4a5e6"],
  ["pearl", "Pearl", "#d6ddeb", "#a1d7d5"],
  ["sunset", "Sunset", "#f3b4a5", "#c8a7ed"],
];
export function FormAppearance({
  form,
  onChange,
}: {
  form: Form;
  onChange: (patch: Partial<Form>) => void;
}) {
  const Icon = formIcon(form.icon);
  return (
    <section className="actionstack-appearance">
      <h2>Appearance</h2>
      <p className="muted">Choose how your form appears in the catalog.</p>
      <FormIconPicker
        value={form.icon}
        onChange={(icon) => onChange({ icon })}
      />
      <fieldset className="actionstack-color-picker">
        <legend>Form color</legend>
        <div>
          {accents.map(([value, label, a, b]) => (
            <label
              key={value}
              className={form.accent === value ? "selected" : ""}
            >
              <input
                type="radio"
                name="form-color"
                value={value}
                checked={form.accent === value}
                onChange={() => onChange({ accent: value })}
              />
              <span
                style={{ background: `linear-gradient(120deg, ${a}, ${b})` }}
              />
              {label}
            </label>
          ))}
        </div>
      </fieldset>
      <div className={"actionstack-appearance-preview " + form.accent}>
        <span className="automation-icon">
          <Icon size={25} />
        </span>
        <div>
          <small>CATALOG PREVIEW</small>
          <h3>{form.title || "Your form"}</h3>
          <p>{form.description || "Your form description"}</p>
        </div>
      </div>
    </section>
  );
}
export function ThemePicker({
  preferences,
  busy,
  onChange,
}: {
  preferences: Preferences;
  busy: boolean;
  onChange: (theme: Preferences["theme"]) => void;
}) {
  return (
    <label className="actionstack-theme-picker">
      Theme
      <select
        aria-label="Theme"
        value={preferences.theme}
        disabled={busy}
        onChange={(e) => onChange(e.target.value as Preferences["theme"])}
      >
        <option value="dark">Dark</option>
        <option value="light">Light</option>
        <option value="system">Use system</option>
      </select>
    </label>
  );
}
