export type Field = {
  tone?: "text" | "info" | "warning";
  collapsed?: boolean;
  lookup?: LookupConfig;
  validation?: Omit<ValidationRule, "field">[];
  key: string;
  type: string;
  label: string;
  required?: boolean;
  required_when?: { field: string; equals: string | number | boolean }[];
  default?: unknown;
  placeholder?: string;
  help?: string;
  options?: { value: string; label: string }[];
  show_when?: { field: string; equals: string | boolean | number };
  min?: number;
  max?: number;
  min_length?: number;
  max_length?: number;
  cef_key?: string;
};
export type ApprovalRule = {
  mode: "never" | "always" | "conditional";
  policy: "soar_playbook";
  conditions: { field: string; equals: string | boolean }[];
};
export type Form = {
  workspace_id?: string;
  validation_policy_id?: string;
  validation_policy?: Pick<
    ValidationPolicy,
    "id" | "name" | "revision" | "rules"
  >;
  id: string;
  title: string;
  description: string;
  category: string;
  icon: string;
  accent: string;
  intro: string;
  fields: Field[];
  mapping: {
    label: string;
    tags: string[];
    severity: string;
    sensitivity: string;
    run_automation: boolean;
    policy?: string;
    enrichment?: string;
    title_prefix: string;
    approval?: ApprovalRule;
  };
  access: {
    view_roles: string[];
    submit_roles: string[];
    edit_roles: string[];
    team_roles: string[];
  };
  revision: number;
  version: number;
  state: string;
  updated_at?: string;
  updated_by?: string;
};
export type Context = {
  username: string;
  display_name: string;
  roles: string[];
  capabilities: string[];
  roles_available: string[];
  demo: boolean;
  connection_ready: boolean;
  setup_required: boolean;
  can_create_roles: boolean;
};
export type Submission = {
  approval?: { approval_required: boolean; approval_policy: string };
  id: string;
  form_id: string;
  form_title: string;
  form_version: number;
  form: Form;
  inputs: Record<string, unknown>;
  submitted_by: string;
  submitted_at: string;
  updated_at: string;
  status: string;
  container_id: number | null;
  artifact_id: number | null;
  event_url: string | null;
  attempts: number;
  error: string | null;
  demo: boolean;
};
export type Settings = {
  label_prefix: string;
  soar_url: string;
  instance_name: string;
  asset_id: number | null;
  ca_pem: string;
  ignore_certificate_errors: boolean;
  request_timeout: number;
  revision: number;
  token_configured: boolean;
  demo: boolean;
};
export type Activity = {
  checked_at: string;
  automation_enabled: boolean;
  demo: boolean;
  playbooks: RunGroup;
  actions: RunGroup;
  blocks?: RunGroup;
};
export type RunGroup = {
  counts?: Record<string, number> | null;
  notice?: string;
  summary_error?: string;
  summary_truncated?: boolean;
  items: {
    id: number | string;
    name: string;
    action?: string;
    block_type?: string;
    status: string;
    summaries?: {
      app_run_id: number;
      status: string;
      summary?: unknown;
      data?: unknown;
      data_truncated?: boolean;
    }[];
    playbook_run_id: number | null;
    updated_at: string | null;
  }[];
  total: number | null;
  truncated: boolean;
  error: string | null;
};
export type Workspace = {
  role_groups?: { viewer: string[]; user: string[]; admin: string[] };
  default_access?: Form["access"];
  id: string;
  name: string;
  description: string;
  roles: string[];
  state: string;
  revision: number;
};
export type Preferences = {
  theme: "dark" | "light" | "system";
  revision: number;
};
export type ValidationRule = {
  field: string;
  operator: string;
  value?: string | number | boolean;
  message: string;
  when?: { field: string; equals: string | number | boolean };
};
export type ValidationPolicy = {
  enrichment?: "none" | "block_object";
  id: string;
  name: string;
  description: string;
  state: string;
  revision: number;
  rules: ValidationRule[];
};
export type LookupConfig = {
  value_field?: string;
  label_field?: string;
  search: string;
  app: string;
  min_chars: number;
  debounce_ms: number;
};
