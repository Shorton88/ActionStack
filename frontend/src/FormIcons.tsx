import {
  FileText,
  createLucideIcon,
  Server,
  UserRound,
  Globe,
  Search,
  ShieldCheck,
  Workflow,
  Zap,
} from "lucide-react";

const ScanPulse = createLucideIcon("ScanPulse", [
  ["circle", { cx: "12", cy: "12", r: "8", key: "reticle" }],
  ["path", { d: "M12 2v3M12 19v3M2 12h3M19 12h3", key: "crosshairs" }],
  ["path", { d: "M6 12h2l2-4 3 8 2-4h3", key: "pulse" }],
]);

export const formIcons = {
  scan: { label: "Scan", Icon: ScanPulse },
  server: { label: "Server", Icon: Server },
  user: { label: "User", Icon: UserRound },
  shield: { label: "Shield", Icon: ShieldCheck },
  workflow: { label: "Workflow", Icon: Workflow },
  search: { label: "Search", Icon: Search },
  file: { label: "Document", Icon: FileText },
  globe: { label: "Globe", Icon: Globe },
  zap: { label: "Lightning", Icon: Zap },
};

export function formIcon(key: string) {
  return formIcons[key as keyof typeof formIcons]?.Icon || Workflow;
}

export function FormIconPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <fieldset className="actionstack-form-icon-picker">
      <legend>Form icon</legend>
      <p>Shown in the catalog and at the top of your form.</p>
      <div className="actionstack-form-icon-options">
        {Object.entries(formIcons).map(([key, { label, Icon }]) => (
          <label key={key} className={value === key ? "selected" : ""}>
            <input
              type="radio"
              name="form-icon"
              value={key}
              checked={value === key}
              onChange={() => onChange(key)}
            />
            <Icon size={19} aria-hidden="true" />
            <span>{label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
