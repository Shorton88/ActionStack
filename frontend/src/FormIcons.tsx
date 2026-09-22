import {
  FileText,
  ScanLine,
  Server,
  UserRound,
  Globe,
  Search,
  ShieldCheck,
  Workflow,
  Zap,
} from "lucide-react";

export const formIcons = {
  scan: { label: "Scan", Icon: ScanLine },
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
