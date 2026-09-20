import {
  randomId,
  cloneDefinition,
  submissionFingerprint,
} from "./browser-compat.js";
import React, { useEffect, useState, useRef } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUpRight,
  ArrowRight,
  ArrowLeft,
  Plus,
  Search,
  Layers,
  LayoutGrid,
  FileText,
  Settings2,
  ShieldCheck,
  Workflow,
  Globe,
  Zap,
  ChevronRight,
  ChevronDown,
  Check,
  CheckCircle2,
  Circle,
  Clock3,
  AlertCircle,
  X,
  GripVertical,
  Trash2,
  Copy,
  Eye,
  Save,
  Send,
  Link2,
  Braces,
  LockKeyhole,
  MoreHorizontal,
  RefreshCw,
  ArrowUp,
  ArrowDown,
  SlidersHorizontal,
  ExternalLink,
  Sparkles,
  PanelLeftClose,
} from "lucide-react";
import { api, ApiError, can, cleanForm } from "./api";
import type {
  Form,
  Field,
  Context,
  Submission,
  Settings,
  Workspace,
  Preferences,
} from "./types";
import "./styles.css";
import { Management, WorkspaceEditor } from "./Management";
import { LookupField, LookupSettings, defaultLookup } from "./LookupField";
import { FieldValidation } from "./FieldValidation";
import { MultiInput } from "./MultiInput";
import { Catalog } from "./Catalog";
import { formIcon } from "./FormIcons";
import { FormAppearance, ThemePicker } from "./Appearance";
import { FormSections } from "./FormSections";
import { cloneForm } from "./clone-form.js";
import { ApprovalRules } from "./ApprovalRules";
import { AutomationActivity } from "./AutomationActivity";
import { approvalRequired } from "./approval.js";
import { version as appVersion } from "../../package.json";
import { connectionSettingsPayload } from "./connection-settings.js";

const statusLabels: Record<string, string> = {
  pending: "Pending delivery",
  submitting: "Submitting",
  submitted: "Submitted to SOAR",
  failed: "Delivery failed",
  needs_attention: "Needs attention",
};
const fieldTypes = [
  ["lookup", "Lookup · single value"],
  ["lookup_multi", "Lookup · multiple values"],
  ["text_list", "Text · multiple values"],
  ["text", "Short text"],
  ["textarea", "Long text"],
  ["select", "Dropdown"],
  ["multiselect", "Multiple choice"],
  ["radio", "Radio buttons"],
  ["checkbox", "Checkbox"],
  ["number", "Number"],
  ["email", "Email"],
  ["url", "URL"],
  ["date", "Date"],
  ["datetime", "Date & time"],
  ["section", "Section"],
];
function formatDate(date: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(date));
}
function Badge({
  status,
  children,
}: {
  status?: string;
  children?: React.ReactNode;
}) {
  return (
    <span className={"badge " + (status || "")}>
      {status === "submitted" ? (
        <CheckCircle2 size={12} />
      ) : (
        <span className="status-dot" />
      )}
      {children || statusLabels[status || ""] || status}
    </span>
  );
}
function Button({
  children,
  onClick,
  primary = false,
  disabled = false,
  className = "",
  type = "button",
  title,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  primary?: boolean;
  disabled?: boolean;
  className?: string;
  type?: "button" | "submit";
  title?: string;
}) {
  return (
    <button
      title={title}
      type={type}
      className={`button ${primary ? "primary" : ""} ${className}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
function Empty({
  title,
  body,
  children,
}: {
  title: string;
  body: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <Layers size={32} />
      <h3>{title}</h3>
      <p>{body}</p>
      {children}
    </div>
  );
}
function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    d?.showModal();
    return () => d?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={wide ? "wide" : ""}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-head">
        <h2>{title}</h2>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
function ErrorBox({ error }: { error: string }) {
  return error ? (
    <div className="notice error" role="alert">
      <AlertCircle size={17} />
      <span>{error}</span>
    </div>
  ) : null;
}

// Keep unparsed editing text so commas, spaces and newlines survive each keystroke.
function BufferedText({
  value,
  onCommit,
  multiline = false,
  ...props
}: {
  value: string;
  onCommit: (value: string) => void;
  multiline?: boolean;
  className?: string;
  rows?: number;
}) {
  const [text, setText] = useState(value);
  const focused = useRef(false);
  useEffect(() => {
    if (!focused.current) setText(value);
  }, [value]);
  const events = {
    onFocus: () => {
      focused.current = true;
    },
    onBlur: () => {
      focused.current = false;
      onCommit(text);
    },
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setText(e.target.value),
  };
  return multiline ? (
    <textarea {...props} {...events} value={text} />
  ) : (
    <input {...props} {...events} value={text} />
  );
}

function FormFields({
  form,
  values,
  setValues,
  errors = {},
  preview = false,
}: {
  form: Form;
  values: Record<string, unknown>;
  setValues: (v: Record<string, unknown>) => void;
  errors?: Record<string, string>;
  preview?: boolean;
}) {
  function change(field: Field, value: unknown) {
    const next = { ...values, [field.key]: value };
    for (const f of form.fields)
      if (f.show_when && next[f.show_when.field] !== f.show_when.equals)
        delete next[f.key];
    setValues(next);
  }
  const renderField = (f: Field) => {
    if (f.show_when && values[f.show_when.field] !== f.show_when.equals)
      return null;
    if (f.type === "section")
      return (
        <div className="form-section" key={f.key}>
          <h3>{f.label}</h3>
          {f.help && <p>{f.help}</p>}
        </div>
      );
    const id = "input-" + f.key;
    const error = errors[f.key];
    const raw =
      values[f.key] ??
      f.default ??
      (f.type === "checkbox" ? false : f.type === "multiselect" ? [] : "");
    const props = {
      id,
      "aria-invalid": !!error,
      "aria-describedby": id + "-help",
      required:
        f.required ||
        f.required_when?.some((c) => values[c.field] === c.equals),
      disabled: false,
    };
    let input;
    if (["lookup", "lookup_multi"].includes(f.type))
      input = (
        <LookupField
          form={form}
          field={{ ...f, required: props.required }}
          value={
            f.type === "lookup_multi"
              ? Array.isArray(raw)
                ? (raw as string[])
                : []
              : String(raw)
          }
          onChange={(v) => change(f, v)}
          preview={preview}
        />
      );
    else if (f.type === "text_list")
      input = (
        <MultiInput
          field={{ ...f, required: props.required }}
          value={Array.isArray(raw) ? (raw as string[]) : []}
          onChange={(v) => change(f, v)}
        />
      );
    else if (f.type === "textarea")
      input = (
        <textarea
          {...props}
          placeholder={f.placeholder}
          rows={4}
          value={String(raw)}
          maxLength={f.max_length}
          onChange={(e) => change(f, e.target.value)}
        />
      );
    else if (f.type === "select")
      input = (
        <div className="select-wrap">
          <select
            {...props}
            value={String(raw)}
            onChange={(e) => change(f, e.target.value)}
          >
            <option value="">Select an option</option>
            {f.options?.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <ChevronDown size={15} />
        </div>
      );
    else if (f.type === "radio" || f.type === "multiselect")
      input = (
        <div
          role="group"
          aria-labelledby={id + "-label"}
          className="choice-group"
        >
          {f.options?.map((o) => (
            <label className="choice" key={o.value}>
              <input
                type={f.type === "radio" ? "radio" : "checkbox"}
                name={f.key}
                checked={
                  f.type === "radio"
                    ? raw === o.value
                    : Array.isArray(raw) && raw.includes(o.value)
                }
                onChange={(e) =>
                  change(
                    f,
                    f.type === "radio"
                      ? o.value
                      : e.target.checked
                        ? [...(Array.isArray(raw) ? raw : []), o.value]
                        : (Array.isArray(raw) ? raw : []).filter(
                            (v) => v !== o.value,
                          ),
                  )
                }
              />
              {o.label}
            </label>
          ))}
        </div>
      );
    else if (f.type === "checkbox")
      input = (
        <label className="choice">
          <input
            {...props}
            type="checkbox"
            checked={Boolean(raw)}
            onChange={(e) => change(f, e.target.checked)}
          />
          {f.placeholder || "Yes"}
        </label>
      );
    else
      input = (
        <input
          {...props}
          type={
            f.type === "datetime"
              ? "datetime-local"
              : ["number", "email", "url", "date"].includes(f.type)
                ? f.type
                : "text"
          }
          value={String(raw)}
          placeholder={f.placeholder}
          maxLength={f.max_length}
          minLength={f.min_length}
          min={f.min}
          max={f.max}
          onChange={(e) =>
            change(
              f,
              f.type === "number" && e.target.value !== ""
                ? Number(e.target.value)
                : e.target.value,
            )
          }
        />
      );
    return (
      <div className={"field " + (error ? "has-error" : "")} key={f.key}>
        <label id={id + "-label"} htmlFor={id}>
          {f.label}
          {props.required && <span className="required">*</span>}
          {!props.required && <span className="optional">Optional</span>}
        </label>
        {input}
        <div id={id + "-help"} className={error ? "field-error" : "field-help"}>
          {error || f.help}
        </div>
      </div>
    );
  };
  return (
    <FormSections
      fields={form.fields}
      values={values}
      errors={errors}
      renderField={renderField}
    />
  );
}
function defaults(form: Form) {
  const v: Record<string, unknown> = {};
  for (const f of form.fields)
    if (
      (f.default !== undefined || f.type === "checkbox") &&
      (!f.show_when || v[f.show_when.field] === f.show_when.equals)
    )
      v[f.key] = f.default ?? false;
  return v;
}

function App() {
  const [preferences, setPreferences] = useState<Preferences>({
    theme: "dark",
    revision: 0,
  });
  const [themeBusy, setThemeBusy] = useState(false);
  const [systemLight, setSystemLight] = useState(
    window.matchMedia("(prefers-color-scheme: light)").matches,
  );
  const [mine, setMine] = useState(false),
    [submissionRefresh, setSubmissionRefresh] = useState(0);
  const setupOpened = useRef(false);
  const resolvedTheme =
    preferences.theme === "system"
      ? systemLight
        ? "light"
        : "dark"
      : preferences.theme;
  useEffect(() => {
    const query = window.matchMedia("(prefers-color-scheme: light)");
    const changed = () => setSystemLight(query.matches);
    query.addEventListener("change", changed);
    return () => query.removeEventListener("change", changed);
  }, []);
  const [ctx, setCtx] = useState<Context | null>(null),
    [allForms, setForms] = useState<Form[]>([]),
    [favorites, setFavorites] = useState<string[]>([]),
    [favoriteBusy, setFavoriteBusy] = useState(false),
    [workspaces, setWorkspaces] = useState<Workspace[]>([]),
    [workspaceId, setWorkspaceId] = useState("security"),
    [allSubmissions, setSubmissions] = useState<Submission[]>([]),
    [page, setPage] = useState("catalog"),
    [selected, setSelected] = useState<Form | null>(null),
    [editor, setEditor] = useState<Form | null>(null),
    [detail, setDetail] = useState<Submission | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [toast, setToast] = useState("");
  const forms = allForms.filter(
    (f) =>
      workspaceId === "*" || (f.workspace_id || "security") === workspaceId,
  );
  const submissions = allSubmissions.filter(
    (s) =>
      (workspaceId === "*" ||
        (s.form.workspace_id || "security") === workspaceId) &&
      (!mine || s.submitted_by === ctx?.username),
  );
  useEffect(() => {
    if (!ctx) return;
    let stale = false;
    setSubmissions([]);
    api<Submission[]>("/submissions/list", { workspace_id: workspaceId, mine })
      .then((rows) => {
        if (!stale) setSubmissions(rows);
      })
      .catch((e) => {
        if (!stale) setError(e.message);
      });
    return () => {
      stale = true;
    };
  }, [workspaceId, mine, submissionRefresh, ctx?.username]);
  const refresh = async () => {
    const [c, f, w, stars, prefs] = await Promise.all([
      api<Context>("/context"),
      api<Form[]>("/forms"),
      api<Workspace[]>("/workspaces"),
      api<string[]>("/favorites"),
      api<Preferences>("/preferences"),
    ]);
    setCtx(c);
    setForms(f);
    setSubmissionRefresh((n) => n + 1);
    setWorkspaces(w);
    setFavorites(stars);
    setPreferences(prefs);
    if (!setupOpened.current) {
      setupOpened.current = true;
      if (c.setup_required && can(c, "admin")) {
        setPage("setup");
        setSelected(null);
      }
    }
    let saved = "";
    try {
      saved = localStorage.getItem("actionstack-workspace:" + c.username) || "";
    } catch {}
    setWorkspaceId((current) =>
      (saved || current) === "*" || w.some((x) => x.id === (saved || current))
        ? saved || current
        : w[0]?.id || "*",
    );
  };
  useEffect(() => {
    refresh()
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(""), 4500);
      return () => clearTimeout(t);
    }
  }, [toast]);
  useEffect(() => {
    const match = window.location.hash.match(/^#form\/([a-z0-9-]+)$/);
    if (match && allForms.length) {
      const f = allForms.find((x) => x.id === match[1]);
      if (f) {
        setSelected(f);
        setWorkspaceId(f.workspace_id || "security");
      }
    }
  }, [allForms]);
  function navigate(to: string) {
    setPage(to);
    setSelected(null);
    setEditor(null);
    setError("");
    window.history.replaceState(null, "", window.location.pathname);
  }
  function openForm(f: Form) {
    setSelected(f);
    window.history.replaceState(null, "", "#form/" + f.id);
  }
  if (!ctx)
    return (
      <div className="actionstack-app">
        <div className="startup">
          <div className="brand-mark">
            <Layers size={24} />
          </div>
          <h1>ActionStack</h1>
          {loading ? (
            <p>Opening your workspace…</p>
          ) : (
            <>
              <ErrorBox error={error} />
              <Button onClick={() => window.location.reload()}>
                Try again
              </Button>
            </>
          )}
        </div>
      </div>
    );
  return (
    <div className="actionstack-app" data-theme={resolvedTheme}>
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate("catalog");
          }}
        >
          <span className="brand-mark">
            <Layers size={22} />
          </span>
          <span>
            Action<span className="brand-dot">Stack</span>
          </span>
        </a>
        <div className="workspace">
          {" "}
          <select
            className="actionstack-workspace-select"
            aria-label="Switch workspace"
            value={workspaceId}
            onChange={(e) => {
              setWorkspaceId(e.target.value);
              try {
                localStorage.setItem(
                  "actionstack-workspace:" + ctx.username,
                  e.target.value,
                );
              } catch {}
              navigate("catalog");
            }}
          >
            <option value="*">All workspaces</option>
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
                {w.state === "archived" ? " (archived)" : ""}
              </option>
            ))}
          </select>
          <ChevronDown size={14} aria-hidden="true" />
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav>
          {[
            ["catalog", LayoutGrid, "Automations"],
            ["submissions", FileText, "Submissions"],
            ...(can(ctx, "edit")
              ? [["builder", SlidersHorizontal, "Form builder"]]
              : []),
          ].map(([key, Icon, label]) => {
            const I = Icon as React.ElementType;
            return (
              <button
                key={String(key)}
                className={page === key ? "active" : ""}
                onClick={() => navigate(String(key))}
              >
                <I size={18} />
                {String(label)}
                {key === "submissions" && submissions.length > 0 && (
                  <span className="nav-count">{submissions.length}</span>
                )}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="connected">
            <span
              className={
                "status-dot " + (ctx.connection_ready ? "green" : "amber")
              }
            />
            <div>
              {ctx.demo
                ? "Demo workspace"
                : ctx.connection_ready
                  ? "SOAR configured"
                  : "Connect your SOAR"}
              <small>
                {ctx.demo
                  ? "Local preview · simulated delivery"
                  : "Splunk SOAR"}
              </small>
            </div>
          </div>
          {can(ctx, "admin") && (
            <button
              className={
                "settings-nav " + (page === "workspaces" ? "active" : "")
              }
              onClick={() => navigate("workspaces")}
              aria-label="Team workspaces"
            >
              <Layers size={18} />
              Team workspaces
            </button>
          )}
          {can(ctx, "admin") && (
            <button
              className={
                "settings-nav " + (page === "settings" ? "active" : "")
              }
              onClick={() => navigate("settings")}
              aria-label="Settings"
            >
              <Settings2 size={18} />
              Settings
            </button>
          )}
          {can(ctx, "admin") && (
            <button className="settings-nav" onClick={() => navigate("setup")}>
              <Sparkles size={18} />
              Setup wizard
            </button>
          )}
          <ThemePicker
            preferences={preferences}
            busy={themeBusy}
            onChange={async (theme) => {
              const previous = preferences;
              setPreferences({ ...preferences, theme });
              setThemeBusy(true);
              setError("");
              try {
                setPreferences(
                  await api<Preferences>("/preferences", {
                    theme,
                    revision: preferences.revision,
                  }),
                );
              } catch (e) {
                setPreferences(previous);
                setError((e as Error).message);
                try {
                  setPreferences(await api<Preferences>("/preferences"));
                } catch {}
              } finally {
                setThemeBusy(false);
              }
            }}
          />
          <div className="profile">
            <span>{ctx.username.slice(0, 2).toUpperCase()}</span>
            <div>
              {ctx.display_name || ctx.username}
              <small>{ctx.roles.join(" · ")}</small>
            </div>
            <LockKeyhole size={14} />
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <select
              className="actionstack-workspace-select"
              aria-label="Current workspace"
              value={workspaceId}
              onChange={(e) => {
                setWorkspaceId(e.target.value);
                try {
                  localStorage.setItem(
                    "actionstack-workspace:" + ctx.username,
                    e.target.value,
                  );
                } catch {}
                navigate("catalog");
              }}
            >
              <option value="*">All workspaces</option>
              {workspaces.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                  {w.state === "archived" ? " (archived)" : ""}
                </option>
              ))}
            </select>
            <ChevronRight size={13} />
            <b>
              {page === "catalog"
                ? "Automations"
                : page === "submissions"
                  ? "Submissions"
                  : page === "builder"
                    ? "Form builder"
                    : page === "workspaces"
                      ? "Team workspaces"
                      : page === "setup"
                        ? "Setup wizard"
                        : "Settings"}
            </b>
            {selected && (
              <>
                <ChevronRight size={13} />
                <span>{selected.title}</span>
              </>
            )}
          </div>
          <div className="topbar-right">
            {ctx.demo && <span className="demo-pill">DEMO MODE</span>}
            <span className="platform-version">ActionStack v{appVersion}</span>
            <span className="top-avatar">
              {ctx.username.slice(0, 1).toUpperCase()}
            </span>
          </div>
        </header>
        <main>
          <ErrorBox error={error} />
          {page === "catalog" && !selected && (
            <Catalog
              key={workspaceId}
              forms={forms}
              workspaces={workspaces}
              favorites={favorites}
              busy={favoriteBusy}
              onOpen={openForm}
              onCreate={
                can(ctx, "edit") ? () => navigate("builder") : undefined
              }
              onFavorite={async (f) => {
                setFavoriteBusy(true);
                setError("");
                try {
                  setFavorites(
                    await api<string[]>("/favorites", {
                      form_id: f.id,
                      favorite: !favorites.includes(f.id),
                    }),
                  );
                } catch (e) {
                  setError((e as Error).message);
                } finally {
                  setFavoriteBusy(false);
                }
              }}
            />
          )}
          {page === "catalog" && selected && (
            <RequestForm
              form={selected}
              ctx={ctx}
              onBack={() => {
                setSelected(null);
                window.history.replaceState(null, "", window.location.pathname);
              }}
              onComplete={(r) => {
                setDetail(r);
                refresh();
                setSelected(null);
                setPage("submissions");
                window.history.replaceState(null, "", window.location.pathname);
              }}
            />
          )}
          {page === "submissions" && (
            <>
              <div className="page-heading compact">
                <div>
                  <div className="eyebrow">EVERY REQUEST, IN ONE PLACE</div>
                  <h1>Submissions</h1>
                  <p>
                    Follow workspace requests from submission to SOAR delivery.
                  </p>
                </div>
                <Button
                  onClick={() => refresh().catch((e) => setError(e.message))}
                >
                  <RefreshCw size={15} />
                  Refresh
                </Button>
              </div>
              <div className="filter-tabs" aria-label="Submission ownership">
                <button
                  className={!mine ? "selected" : ""}
                  onClick={() => setMine(false)}
                >
                  Workspace submissions
                </button>
                <button
                  className={mine ? "selected" : ""}
                  onClick={() => setMine(true)}
                >
                  My submissions
                </button>
              </div>
              <p className="muted actionstack-submission-note">
                Showing up to 200 recent submissions you have permission to
                view.
              </p>
              <div className="stat-row">
                <div>
                  <span>Total submissions</span>
                  <strong>{submissions.length}</strong>
                </div>
                <div>
                  <span>Delivered to SOAR</span>
                  <strong>
                    {submissions.filter((s) => s.status === "submitted").length}
                    <CheckCircle2 size={21} />
                  </strong>
                </div>
                <div>
                  <span>Need attention</span>
                  <strong>
                    {
                      submissions.filter((s) =>
                        ["failed", "needs_attention"].includes(s.status),
                      ).length
                    }
                  </strong>
                </div>
              </div>
              {!submissions.length ? (
                <Empty
                  title="Your next workflow starts here"
                  body="Submit an automation form and your delivery receipt will appear here."
                >
                  <Button primary onClick={() => navigate("catalog")}>
                    Browse automations
                    <ArrowRight size={16} />
                  </Button>
                </Empty>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Automation</th>
                        <th>Status</th>
                        <th>Submitted</th>
                        <th>Submitted by</th>
                        <th>SOAR event</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {submissions.map((s) => (
                        <tr key={s.id} onClick={() => setDetail(s)}>
                          <td>
                            <button
                              className="table-title"
                              onClick={() => setDetail(s)}
                            >
                              {s.form_title}
                            </button>
                            <small>
                              {s.id.slice(0, 8)} · v{s.form_version}
                            </small>
                          </td>
                          <td>
                            <Badge status={s.status} />
                          </td>
                          <td>{formatDate(s.submitted_at)}</td>
                          <td>{s.submitted_by}</td>
                          <td className="mono">
                            {s.container_id ? "#" + s.container_id : "—"}
                          </td>
                          <td>
                            <ChevronRight size={16} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
          {page === "workspaces" && can(ctx, "admin") && (
            <Management
              key={page}
              kind="workspaces"
              ctx={ctx}
              onSaved={() => {
                void refresh();
                setToast("Saved successfully");
              }}
            />
          )}
          {page === "builder" && (
            <Builder
              workspaceId={workspaceId}
              workspaces={workspaces}
              ctx={ctx}
              editor={editor}
              setEditor={setEditor}
              onSaved={(message) => {
                refresh();
                setToast(message || "Form saved successfully");
              }}
            />
          )}
          {page === "settings" && (
            <ConnectionSettings
              onSaved={() => {
                refresh();
                setToast("Connection settings saved");
              }}
            />
          )}
          {page === "setup" && can(ctx, "admin") && (
            <SetupWizard
              ctx={ctx}
              workspaces={workspaces}
              onRefresh={refresh}
              onComplete={(id) => {
                setWorkspaceId(id);
                try {
                  localStorage.setItem(
                    "actionstack-workspace:" + ctx.username,
                    id,
                  );
                } catch {}
                navigate("catalog");
                setToast(
                  "Workspace ready. Create your first form in Form builder.",
                );
              }}
            />
          )}
        </main>
        <footer className="app-footer">
          <span>
            <Layers size={13} />
            ActionStack
          </span>
          <span>Human input. Automated possibilities.</span>
        </footer>
      </div>
      {detail && (
        <Receipt
          submission={detail}
          onClose={() => setDetail(null)}
          onRetry={async () => {
            const r = await api<Submission>(
              "/submissions/" + detail.id + "/retry",
              {},
            );
            setDetail(r);
            refresh();
          }}
        />
      )}
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 size={17} />
          {toast}
        </div>
      )}
    </div>
  );
}
function RequestForm({
  form,
  ctx,
  onBack,
  onComplete,
}: {
  form: Form;
  ctx: Context;
  onBack: () => void;
  onComplete: (s: Submission) => void;
}) {
  const [values, setValues] = useState<Record<string, unknown>>(() =>
      defaults(form),
    ),
    [errors, setErrors] = useState<Record<string, string>>({}),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [review, setReview] = useState(false);
  const Icon = formIcon(form.icon);
  const maySubmit =
    can(ctx, "submit") &&
    (can(ctx, "admin") ||
      !form.access.submit_roles.length ||
      form.access.submit_roles.some((role) => ctx.roles.includes(role)));
  const needsApproval = approvalRequired(form, values);
  async function submit() {
    setBusy(true);
    setError("");
    setErrors({});
    try {
      const fingerprint = await submissionFingerprint(
        JSON.stringify({
          user: ctx.username,
          form: form.id,
          version: form.version,
          values,
        }),
        async (value) =>
          (
            await api<{ fingerprint: string }>("/submission-fingerprint", {
              value,
            })
          ).fingerprint,
      );
      const storageKey = "actionstack.pending." + fingerprint;
      let key = sessionStorage.getItem(storageKey);
      if (!key) {
        key = randomId();
        sessionStorage.setItem(storageKey, key);
      }
      const result = await api<Submission>("/submissions", {
        form_id: form.id,
        form_version: form.version,
        inputs: values,
        idempotency_key: key,
      });
      sessionStorage.removeItem(storageKey);
      onComplete(result);
    } catch (e) {
      const ex = e as ApiError;
      setError(ex.message);
      setErrors(ex.fields || {});
      setReview(false);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button className="back-link" onClick={onBack}>
        <ArrowLeft size={15} />
        All automations
      </button>
      <div className="request-layout">
        <section className="request-panel">
          <div className={"request-header " + form.accent}>
            <span className="automation-icon">
              <Icon size={26} />
            </span>
            <div>
              <span className="card-category">{form.category}</span>
              <h1>{form.title}</h1>
              <p>{form.intro || form.description}</p>
            </div>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setReview(true);
            }}
          >
            <div className="form-body">
              <ErrorBox error={error} />
              <FormFields
                form={form}
                values={values}
                setValues={(v) => {
                  setValues(v);
                  setErrors({});
                }}
                errors={errors}
              />
              {needsApproval && (
                <div className="notice">
                  <LockKeyhole size={17} />
                  <span>
                    <b>Approval required</b>This request meets the form’s
                    approval rules. Your SOAR playbook handles the approval.
                  </span>
                </div>
              )}
            </div>
            <div className="actionstack-request-actions">
              <span>
                <LockKeyhole size={14} />
                {maySubmit
                  ? `Submitted as ${ctx.username}`
                  : "View-only access"}
              </span>
              <Button primary type="submit" disabled={!maySubmit}>
                Review request
                <ArrowRight size={16} />
              </Button>
            </div>
          </form>
        </section>
        <aside className="request-aside">
          <div className="aside-card">
            <h3>What happens next</h3>
            <ol className="steps">
              <li>
                <span>1</span>
                <div>
                  <b>Complete the form</b>
                  <p>Provide the details your workflow needs.</p>
                </div>
              </li>
              <li>
                <span>2</span>
                <div>
                  <b>Review and submit</b>
                  <p>Your request is validated and recorded.</p>
                </div>
              </li>
              <li>
                <span>3</span>
                <div>
                  <b>Delivered to SOAR</b>
                  <p>Your event is ready for your team's playbooks.</p>
                </div>
              </li>
            </ol>
          </div>
          <div className="aside-info">
            <ShieldCheck size={19} />
            <div>
              <b>Workspace access</b>
              <p>
                Managed by your organization.
                <br />
                Access through your Splunk roles.
              </p>
            </div>
          </div>
          <div className="form-meta">
            <span>FORM VERSION</span>
            <b>{String(form.version).padStart(2, "0")}</b>
            <span>DESTINATION</span>
            <b>Splunk SOAR</b>
          </div>
        </aside>
      </div>
      {review && (
        <Modal
          title="Review your request"
          onClose={() => !busy && setReview(false)}
        >
          <div className="modal-body">
            <p className="muted">
              {form.title} · Version {form.version}
            </p>
            <div className="summary-list">
              {form.fields
                .filter(
                  (f) =>
                    f.type !== "section" &&
                    values[f.key] !== undefined &&
                    (!f.show_when ||
                      values[f.show_when.field] === f.show_when.equals),
                )
                .map((f) => (
                  <div key={f.key}>
                    <span>{f.label}</span>
                    <b>
                      {Array.isArray(values[f.key])
                        ? (values[f.key] as string[]).join(", ")
                        : f.options?.find((o) => o.value === values[f.key])
                            ?.label || String(values[f.key])}
                    </b>
                  </div>
                ))}
            </div>
            {needsApproval && (
              <div className="notice">
                <LockKeyhole size={16} />
                This request requires downstream approval in SOAR.
              </div>
            )}
            {ctx.demo && (
              <div className="notice">
                Demo mode uses simulated SOAR delivery.
              </div>
            )}
          </div>
          <div className="modal-actions">
            <Button onClick={() => setReview(false)} disabled={busy}>
              Back to form
            </Button>
            <Button primary disabled={busy} onClick={submit}>
              {busy ? (
                <RefreshCw className="spin" size={16} />
              ) : (
                <Send size={16} />
              )}{" "}
              {busy ? "Submitting…" : "Submit request"}
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}
function Receipt({
  submission: s,
  onClose,
  onRetry,
}: {
  submission: Submission;
  onClose: () => void;
  onRetry: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [raw, setRaw] = useState(false);
  return (
    <Modal title="Submission details" onClose={onClose}>
      <div className="modal-body">
        <Badge status={s.status} />
        <h2 className="receipt-title">{s.form_title}</h2>
        <p className="muted">
          {s.status === "submitted"
            ? "Your event and form fields are available in SOAR."
            : "Your request has been recorded. Delivery still needs confirmation."}
        </p>
        <ErrorBox error={error || s.error || ""} />
        {s.demo && (
          <div className="notice">
            Simulated delivery · local demo workspace
          </div>
        )}
        <div className="summary-list">
          <div>
            <span>Submission ID</span>
            <b className="mono">{s.id}</b>
          </div>
          <div>
            <span>Submitted by</span>
            <b>{s.submitted_by}</b>
          </div>
          <div>
            <span>Submitted</span>
            <b>{formatDate(s.submitted_at)}</b>
          </div>
          <div>
            <span>Form version</span>
            <b>{s.form_version}</b>
          </div>
          <div>
            <span>SOAR label</span>
            <b>{s.form.mapping.label}</b>
          </div>
          <div>
            <span>SOAR event</span>
            <b>{s.container_id ? "#" + s.container_id : "Pending"}</b>
          </div>
          <div>
            <span>Artifact</span>
            <b>{s.artifact_id ? "#" + s.artifact_id : "Pending"}</b>
          </div>
          <div>
            <span>Delivery attempts</span>
            <b>{s.attempts}</b>
          </div>
        </div>
        <div className="notice">
          <LockKeyhole size={16} />
          {(s.approval?.approval_required ?? approvalRequired(s.form, s.inputs))
            ? "Approval required by this request’s published rules. The approval decision is managed in SOAR."
            : "No approval required by this request’s published rules."}
        </div>
        <AutomationActivity
          key={s.id}
          id={s.id}
          containerId={s.container_id}
          enabled={s.form.mapping.run_automation}
        />
        <button className="text-button" onClick={() => setRaw(!raw)}>
          <Braces size={15} />
          {raw ? "Hide" : "Show"} submitted fields
          <ChevronDown size={14} />
        </button>
        {raw && <pre>{JSON.stringify(s.inputs, null, 2)}</pre>}
      </div>
      <div className="modal-actions">
        <Button onClick={onClose}>Close</Button>
        {s.event_url && (
          <a
            className="button"
            href={s.event_url}
            target="_blank"
            rel="noreferrer"
          >
            Open in SOAR
            <ExternalLink size={15} />
          </a>
        )}
        {s.status !== "submitted" && (
          <Button
            primary
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await onRetry();
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <RefreshCw size={15} className={busy ? "spin" : ""} />
            Retry delivery
          </Button>
        )}
      </div>
    </Modal>
  );
}

function Builder({
  workspaceId,
  workspaces,
  ctx,
  editor,
  setEditor,
  onSaved,
}: {
  workspaceId: string;
  workspaces: Workspace[];
  ctx: Context;
  editor: Form | null;
  setEditor: (f: Form | null) => void;
  onSaved: (message?: string) => void;
}) {
  const [automaticId, setAutomaticId] = useState(false);
  const [labels, setLabels] = useState<{ prefix: string; labels: string[] }>({
    prefix: "",
    labels: [],
  });
  const [labelError, setLabelError] = useState("");
  const [previewErrors, setPreviewErrors] = useState<Record<string, string>>(
    {},
  );
  const [previewMessage, setPreviewMessage] = useState("");
  const [previewValid, setPreviewValid] = useState(false),
    [previewBusy, setPreviewBusy] = useState(false);
  async function loadLabels() {
    setLabelError("");
    try {
      setLabels(await api("/admin/soar-labels"));
    } catch (e) {
      setLabelError((e as Error).message);
    }
  }
  const [items, setItems] = useState<Form[]>([]),
    [tab, setTab] = useState("Build"),
    [selected, setSelected] = useState(0),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [preview, setPreview] = useState(false),
    [previewValues, setPreviewValues] = useState<Record<string, unknown>>({}),
    [versions, setVersions] = useState<Form[]>([]),
    [notice, setNotice] = useState(""),
    [trash, setTrash] = useState(false),
    [deleteTarget, setDeleteTarget] = useState<Form | null>(null),
    [drag, setDrag] = useState<number | null>(null);
  async function load() {
    setItems(await api<Form[]>("/admin/forms"));
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
    void loadLabels();
  }, []);
  async function changeFormState(f: Form, restore = false) {
    setBusy(true);
    setError("");
    try {
      await api("/admin/forms/" + f.id + (restore ? "/restore" : "/delete"), {
        expected_revision: f.revision,
      });
      setDeleteTarget(null);
      setEditor(null);
      await load();
      onSaved(
        restore
          ? "Form restored. Publish it when ready."
          : "Form moved to Trash.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const deleteDialog = deleteTarget && (
    <Modal title="Delete form?" onClose={() => !busy && setDeleteTarget(null)}>
      <div className="modal-body">
        <p>
          <b>{deleteTarget.title}</b> will move to Trash and stop accepting
          requests. Existing submissions will remain available.
        </p>
        <ErrorBox error={error} />
      </div>
      <div className="modal-actions">
        <Button disabled={busy} onClick={() => setDeleteTarget(null)}>
          Cancel
        </Button>
        <Button disabled={busy} onClick={() => changeFormState(deleteTarget)}>
          Delete form
        </Button>
      </div>
    </Modal>
  );
  function start(f: Form) {
    setAutomaticId(false);
    setEditor(cloneDefinition(f));
    setSelected(0);
    setTab("Build");
    setError("");
    setNotice("");
  }
  function create() {
    const id = "untitled-automation-" + randomId().slice(0, 4);
    const workspace =
      workspaceId === "*"
        ? workspaces.find(
            (w) =>
              w.state === "active" &&
              (!w.role_groups ||
                can(ctx, "admin") ||
                w.role_groups.admin.some((r) => ctx.roles.includes(r))),
          )
        : workspaces.find((w) => w.id === workspaceId && w.state === "active");
    if (!workspace) {
      setError("Create an active workspace before adding a form.");
      return;
    }
    if (
      workspace.role_groups &&
      !can(ctx, "admin") &&
      !workspace.role_groups.admin.some((r) => ctx.roles.includes(r))
    ) {
      setError("Only workspace admins can create forms in this workspace.");
      return;
    }
    start({
      workspace_id: workspace.id,
      id,
      title: "Untitled automation",
      description: "A new form for your team.",
      category: "General",
      icon: "workflow",
      accent: "cyan",
      intro: "",
      fields: [
        {
          key: "details",
          type: "textarea",
          label: "Request details",
          required: true,
        },
      ],
      mapping: {
        label: labels.labels[0] || "",
        tags: ["source:splunk_actionstack"],
        severity: "low",
        sensitivity: "amber",
        run_automation: false,
        title_prefix: "Form submission",
      },
      access: workspace.default_access
        ? cloneDefinition(workspace.default_access)
        : {
            view_roles: [],
            submit_roles: [],
            edit_roles: ctx.roles,
            team_roles: [],
          },
      revision: 0,
      version: 0,
      state: "draft",
    });
    setAutomaticId(true);
  }
  function cloneExisting(source: Form) {
    start(cloneForm(source, randomId().slice(0, 4)));
    setAutomaticId(true);
    setNotice(
      "Cloned as a new draft. Review the settings, then save or publish.",
    );
  }
  function update(patch: Partial<Form>) {
    if (
      editor &&
      !editor.revision &&
      automaticId &&
      patch.title !== undefined
    ) {
      const slug =
        patch.title
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-|-$/g, "")
          .replace(/^[^a-z]+/, "")
          .slice(0, 48)
          .replace(/-$/g, "") || "form";
      patch = { ...patch, id: slug + "-" + editor.id.slice(-4) };
    }
    if (editor) setEditor({ ...editor, ...patch });
    setNotice("");
  }
  function fieldUpdate(patch: Partial<Field>) {
    if (!editor) return;
    update({
      fields: editor.fields.map((f, i) =>
        i === selected ? { ...f, ...patch } : f,
      ),
    });
  }
  async function save(publish: boolean) {
    if (!editor) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<Form>(
        "/admin/forms/" + (publish ? "publish" : "save"),
        { form: cleanForm(editor), expected_revision: editor.revision },
      );
      setEditor(result);
      await load();
      onSaved();
      setNotice(
        publish
          ? "Published. Your form is available to its assigned roles."
          : "Draft saved. Published forms continue to use their existing version.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function move(from: number, to: number) {
    if (!editor || to < 0 || to >= editor.fields.length) return;
    const fields = [...editor.fields];
    const [f] = fields.splice(from, 1);
    fields.splice(to, 0, f);
    update({ fields });
    setSelected(to);
  }
  function add(type: string) {
    if (!editor) return;
    const k = type + "_" + randomId().slice(0, 6);
    update({
      fields: [
        ...editor.fields,
        {
          key: k,
          type,
          ...(["lookup", "lookup_multi"].includes(type)
            ? { lookup: { ...defaultLookup } }
            : {}),
          label: fieldTypes.find((t) => t[0] === type)?.[1] || "Field",
          required: false,
          ...(["select", "radio", "multiselect"].includes(type)
            ? {
                options: [
                  { value: "option_1", label: "Option 1" },
                  { value: "option_2", label: "Option 2" },
                ],
              }
            : {}),
        },
      ],
    });
    setSelected(editor.fields.length);
  }
  if (!editor)
    return (
      <>
        <div className="page-heading compact">
          <div>
            <div className="eyebrow">DESIGNED BY YOU</div>
            <h1>Form builder</h1>
            <p>Turn a team's request into a repeatable starting point.</p>
          </div>
          <Button primary onClick={create}>
            <Plus size={16} />
            Create form
          </Button>
        </div>
        <ErrorBox error={error} />
        <div className="filter-tabs">
          <button
            className={!trash ? "selected" : ""}
            onClick={() => setTrash(false)}
          >
            Forms
          </button>
          <button
            className={trash ? "selected" : ""}
            onClick={() => setTrash(true)}
          >
            Trash
          </button>
        </div>
        <div className="builder-intro">
          <div className="automation-icon cyan">
            <SlidersHorizontal size={24} />
          </div>
          <div>
            <h3>A form for every workflow.</h3>
            <p>
              Build your fields, set access, and choose where the event lands in
              SOAR.
            </p>
          </div>
          <span className="badge">No code required</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Form</th>
                <th>Latest change</th>
                <th>Version</th>
                <th>Updated</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items
                .filter(
                  (f) =>
                    (f.state === "deleted") === trash &&
                    (workspaceId === "*" ||
                      (f.workspace_id || "security") === workspaceId),
                )
                .map((f) => (
                  <tr key={f.id}>
                    <td>
                      <button
                        className="table-title"
                        disabled={trash}
                        onClick={() => start(f)}
                      >
                        {f.title}
                      </button>
                      <small>
                        {f.fields.length} fields · {f.category}
                      </small>
                    </td>
                    <td>
                      <Badge status={f.state} />
                    </td>
                    <td>v{f.version}</td>
                    <td>{f.updated_at ? formatDate(f.updated_at) : "—"}</td>
                    <td>
                      {!trash && (
                        <Button
                          disabled={busy}
                          onClick={() => cloneExisting(f)}
                          aria-label={"Clone " + f.title}
                        >
                          <Copy size={14} />
                          Clone
                        </Button>
                      )}
                      {can(ctx, "publish") && (
                        <Button
                          disabled={busy}
                          onClick={() =>
                            trash
                              ? changeFormState(f, true)
                              : setDeleteTarget(f)
                          }
                        >
                          {trash ? "Restore" : "Delete"}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        {!items.some(
          (f) =>
            (f.state === "deleted") === trash &&
            (workspaceId === "*" ||
              (f.workspace_id || "security") === workspaceId),
        ) && (
          <Empty
            title={trash ? "Trash is empty" : "Make your first form"}
            body={
              trash
                ? "Deleted forms appear here and can be restored."
                : "Add fields, choose a SOAR label, and publish when you are ready."
            }
          />
        )}
        {deleteDialog}
      </>
    );
  const field = editor.fields[selected];
  return (
    <>
      <button className="back-link" onClick={() => setEditor(null)}>
        <ArrowLeft size={15} />
        All forms
      </button>
      {deleteDialog}
      <div className="editor-heading">
        <div>
          <span className="eyebrow">FORM EDITOR</span>
          <h1>
            {editor.title}
            <Badge status={editor.state} />
          </h1>
        </div>
        <div className="button-row">
          {editor.revision > 0 && (
            <Button disabled={busy} onClick={() => cloneExisting(editor)}>
              <Copy size={15} />
              Clone form
            </Button>
          )}
          {editor.revision > 0 && can(ctx, "publish") && (
            <Button disabled={busy} onClick={() => setDeleteTarget(editor)}>
              <Trash2 size={15} />
              Delete
            </Button>
          )}
          <Button
            onClick={() => {
              setPreviewValues(defaults(editor));
              setPreviewErrors({});
              setPreviewMessage("");
              setPreviewValid(false);
              setPreview(true);
            }}
          >
            <Eye size={15} />
            Preview
          </Button>
          <Button disabled={busy} onClick={() => save(false)}>
            <Save size={15} />
            Save draft
          </Button>
          {can(ctx, "publish") && (
            <Button primary disabled={busy} onClick={() => save(true)}>
              {busy ? (
                <RefreshCw size={15} className="spin" />
              ) : (
                <ArrowUpRight size={15} />
              )}
              Publish
            </Button>
          )}
        </div>
      </div>
      <ErrorBox error={error} />
      {notice && (
        <div className="notice success" role="status">
          <CheckCircle2 size={16} />
          {notice}
        </div>
      )}
      <label className="field actionstack-workspace-assignment">
        Workspace
        <select
          value={editor.workspace_id || "security"}
          disabled={editor.revision > 0 && !can(ctx, "admin")}
          onChange={(e) => {
            const w = workspaces.find((w) => w.id === e.target.value);
            update({
              workspace_id: e.target.value,
              ...(!editor.revision && w?.default_access
                ? { access: cloneDefinition(w.default_access) }
                : {}),
            });
          }}
        >
          {workspaces
            .filter((w) => w.state === "active")
            .map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
        </select>
      </label>
      <div className="editor-tabs">
        {["Build", "SOAR mapping", "Approvals", "Settings", "Versions"].map(
          (t) => (
            <button
              key={t}
              className={tab === t ? "selected" : ""}
              onClick={async () => {
                setTab(t);
                if (t === "Versions" && editor.revision)
                  try {
                    setVersions(
                      await api<Form[]>(
                        "/admin/forms/" + editor.id + "/versions",
                      ),
                    );
                  } catch (e) {
                    setError((e as Error).message);
                  }
              }}
            >
              {t === "Build" ? (
                <LayoutGrid size={15} />
              ) : t === "SOAR mapping" ? (
                <Workflow size={15} />
              ) : t === "Settings" || t === "Approvals" ? (
                <LockKeyhole size={15} />
              ) : (
                <Clock3 size={15} />
              )}{" "}
              {t}
            </button>
          ),
        )}
      </div>
      {tab === "Build" && (
        <div className="editor-grid">
          <aside className="palette">
            <h3>Add a field</h3>
            <p>The building blocks of your form.</p>
            <div className="palette-grid">
              {fieldTypes.map(([type, label]) => (
                <button key={type} onClick={() => add(type)}>
                  <span>
                    {
                      (
                        {
                          lookup: "⌕",
                          lookup_multi: "⌕+",
                          text_list: "T+",
                          text: "T",
                          textarea: "☰",
                          select: "⌄",
                          number: "#",
                          email: "@",
                          url: "↗",
                          date: "▦",
                          datetime: "◷",
                          section: "▬",
                          checkbox: "☑",
                          radio: "◉",
                          multiselect: "☷",
                        } as Record<string, string>
                      )[type]
                    }
                  </span>
                  {label}
                  <Plus size={12} />
                </button>
              ))}
            </div>
            <div className="palette-note">
              <GripVertical size={16} />
              <p>Drag fields to reorder, or use the arrow controls.</p>
            </div>
          </aside>
          <section className="canvas">
            <div className="canvas-caption">
              <span>
                <Circle size={8} /> LIVE STRUCTURE
              </span>
              <span>{editor.fields.length} FIELDS</span>
            </div>
            <div className="canvas-form">
              <input
                className="title-input"
                aria-label="Form title"
                value={editor.title}
                onChange={(e) => update({ title: e.target.value })}
              />
              <textarea
                className="description-input"
                aria-label="Form description"
                value={editor.description}
                onChange={(e) => update({ description: e.target.value })}
                rows={2}
              />
              {editor.fields.map((f, i) => (
                <div
                  key={f.key + "-" + i}
                  className={
                    "canvas-field " + (selected === i ? "selected" : "")
                  }
                  draggable
                  tabIndex={0}
                  role="group"
                  aria-label={"Edit field: " + f.label}
                  onKeyDown={(e) => {
                    if (
                      e.target === e.currentTarget &&
                      ["Enter", " "].includes(e.key)
                    ) {
                      e.preventDefault();
                      setSelected(i);
                    }
                  }}
                  onDragStart={() => setDrag(i)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    if (drag !== null) move(drag, i);
                    setDrag(null);
                  }}
                  onClick={() => setSelected(i)}
                >
                  <div className="canvas-field-label">
                    <GripVertical size={14} />
                    <b>
                      {f.label}
                      {f.required && <span className="required">*</span>}
                    </b>
                    <div className="field-controls">
                      <button
                        aria-label={"Move " + f.label + " up"}
                        disabled={i === 0}
                        onClick={(e) => {
                          e.stopPropagation();
                          move(i, i - 1);
                        }}
                      >
                        <ArrowUp size={12} />
                      </button>
                      <button
                        aria-label={"Move " + f.label + " down"}
                        disabled={i === editor.fields.length - 1}
                        onClick={(e) => {
                          e.stopPropagation();
                          move(i, i + 1);
                        }}
                      >
                        <ArrowDown size={12} />
                      </button>
                      <button
                        aria-label={"Duplicate " + f.label}
                        onClick={(e) => {
                          e.stopPropagation();
                          update({
                            fields: [
                              ...editor.fields,
                              {
                                ...cloneDefinition(f),
                                key:
                                  f.key.slice(0, 50) +
                                  "_" +
                                  randomId().slice(0, 6),
                              },
                            ],
                          });
                          setSelected(editor.fields.length);
                        }}
                      >
                        <Copy size={12} />
                      </button>
                    </div>
                  </div>
                  {f.type !== "section" && (
                    <div
                      className={
                        "canvas-placeholder " +
                        (f.type === "textarea" ? "tall" : "")
                      }
                    >
                      {f.placeholder ||
                        (f.type === "select"
                          ? "Select an option"
                          : f.type === "checkbox"
                            ? "☐ Yes"
                            : "Enter " + f.label.toLowerCase())}
                      {f.type === "select" && <ChevronDown size={14} />}
                    </div>
                  )}
                  {f.show_when && (
                    <small className="condition-indicator">
                      <Workflow size={11} />
                      Shown when {f.show_when.field} ={" "}
                      {String(f.show_when.equals)}
                    </small>
                  )}
                </div>
              ))}
              <button className="add-inline" onClick={() => add("text")}>
                <Plus size={15} />
                Add a field
              </button>
              <div className="canvas-submit">
                Submit request
                <ArrowRight size={14} />
              </div>
            </div>
          </section>
          <aside className="properties">
            <div className="property-heading">
              <h3>Field properties</h3>
              {field && (
                <button
                  className="icon-button danger"
                  aria-label="Delete selected field"
                  disabled={editor.fields.length < 2}
                  onClick={() => {
                    update({
                      fields: editor.fields.filter((_, i) => i !== selected),
                    });
                    setSelected(Math.max(0, selected - 1));
                  }}
                >
                  <Trash2 size={15} />
                </button>
              )}
            </div>
            {field && (
              <>
                <label className="field">
                  Label
                  <input
                    value={field.label}
                    onChange={(e) => fieldUpdate({ label: e.target.value })}
                  />
                </label>
                <label className="field">
                  Field key
                  <input
                    className="mono"
                    value={field.key}
                    onChange={(e) => fieldUpdate({ key: e.target.value })}
                  />
                  <small>Stable identifier used in SOAR.</small>
                </label>
                <label className="field">
                  Field type
                  <select
                    value={field.type}
                    onChange={(e) =>
                      fieldUpdate({
                        type: e.target.value,
                        default: undefined,
                        collapsed:
                          e.target.value === "section" ? false : undefined,
                        validation:
                          e.target.value === "section" ? [] : field.validation,
                        lookup: ["lookup", "lookup_multi"].includes(
                          e.target.value,
                        )
                          ? field.lookup || { ...defaultLookup }
                          : undefined,
                        ...(["select", "radio", "multiselect"].includes(
                          e.target.value,
                        ) && !field.options
                          ? {
                              options: [
                                { value: "option_1", label: "Option 1" },
                              ],
                            }
                          : {}),
                      })
                    }
                  >
                    {fieldTypes.map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                </label>
                {field.type === "section" && (
                  <label className="toggle-row">
                    <div>
                      <b>Collapsed by default</b>
                      <small>
                        Groups the fields below until the next section. Users
                        can expand it; validation still applies.
                      </small>
                    </div>
                    <input
                      type="checkbox"
                      checked={!!field.collapsed}
                      onChange={(e) =>
                        fieldUpdate({ collapsed: e.target.checked })
                      }
                    />
                  </label>
                )}
                {["lookup", "lookup_multi"].includes(field.type) && (
                  <LookupSettings field={field} onChange={fieldUpdate} />
                )}
                {field.type !== "section" && (
                  <label className="toggle-row">
                    <div>
                      <b>Required field</b>
                      <small>A response is needed to submit.</small>
                    </div>
                    <input
                      type="checkbox"
                      checked={!!field.required}
                      onChange={(e) =>
                        fieldUpdate({ required: e.target.checked })
                      }
                    />
                  </label>
                )}
                {field.required_when?.map((condition, i) => (
                  <div className="notice" key={i}>
                    <span>
                      Required when {condition.field} ={" "}
                      {String(condition.equals)}
                    </span>
                    <button
                      type="button"
                      className="button"
                      onClick={() =>
                        fieldUpdate({
                          required_when: field.required_when?.filter(
                            (_, n) => n !== i,
                          ),
                        })
                      }
                    >
                      Remove condition
                    </button>
                  </div>
                ))}
                <label className="field">
                  Placeholder
                  <input
                    value={field.placeholder || ""}
                    onChange={(e) =>
                      fieldUpdate({ placeholder: e.target.value })
                    }
                  />
                </label>
                <label className="field">
                  Helper text
                  <textarea
                    rows={2}
                    value={field.help || ""}
                    onChange={(e) => fieldUpdate({ help: e.target.value })}
                  />
                </label>
                {["select", "radio", "multiselect"].includes(field.type) && (
                  <label className="field">
                    Options
                    <BufferedText
                      key={selected + "-options"}
                      multiline
                      className="mono"
                      rows={5}
                      value={(field.options || [])
                        .map((o) => o.value + " | " + o.label)
                        .join("\n")}
                      onCommit={(value) =>
                        fieldUpdate({
                          options: value
                            .split("\n")
                            .filter((line) => line.trim())
                            .map((line) => {
                              const [value, ...label] = line.split("|");
                              return {
                                value: value.trim(),
                                label: label.join("|").trim() || value.trim(),
                              };
                            }),
                        })
                      }
                    />
                    <small>One value | label per line.</small>
                  </label>
                )}
                {["text", "textarea", "email", "url"].includes(field.type) && (
                  <label className="field">
                    Maximum length
                    <input
                      type="number"
                      value={field.max_length ?? ""}
                      onChange={(e) =>
                        fieldUpdate({
                          max_length: e.target.value
                            ? Number(e.target.value)
                            : undefined,
                        })
                      }
                    />
                  </label>
                )}
                {field.type === "number" && (
                  <div className="two-column">
                    {(["min", "max"] as const).map((k) => (
                      <label className="field" key={k}>
                        {k === "min" ? "Minimum" : "Maximum"}
                        <input
                          type="number"
                          value={field[k] ?? ""}
                          onChange={(e) =>
                            fieldUpdate({
                              [k]: e.target.value
                                ? Number(e.target.value)
                                : undefined,
                            })
                          }
                        />
                      </label>
                    ))}
                  </div>
                )}
                {![
                  "multiselect",
                  "section",
                  "text_list",
                  "lookup_multi",
                ].includes(field.type) && (
                  <label className="field">
                    Default value
                    <input
                      value={
                        field.default === undefined ? "" : String(field.default)
                      }
                      onChange={(e) =>
                        fieldUpdate({
                          default:
                            e.target.value === ""
                              ? undefined
                              : field.type === "number"
                                ? Number(e.target.value)
                                : field.type === "checkbox"
                                  ? e.target.value === "true"
                                  : e.target.value,
                        })
                      }
                    />
                    <small>
                      {field.type === "checkbox"
                        ? "Use true or false."
                        : "Optional initial value."}
                    </small>
                  </label>
                )}
                <FieldValidation field={field} onChange={fieldUpdate} />
                <div className="property-divider" />
                <label className="field">
                  Show condition
                  <select
                    value={field.show_when?.field || ""}
                    onChange={(e) =>
                      fieldUpdate({
                        show_when: e.target.value
                          ? { field: e.target.value, equals: "" }
                          : undefined,
                      })
                    }
                  >
                    <option value="">Always show</option>
                    {editor.fields
                      .slice(0, selected)
                      .filter((f) => f.type !== "section")
                      .map((f) => (
                        <option key={f.key} value={f.key}>
                          {f.label}
                        </option>
                      ))}
                  </select>
                </label>
                {field.show_when && (
                  <label className="field">
                    Equals
                    <input
                      value={String(field.show_when.equals)}
                      onChange={(e) => {
                        const controller = editor.fields.find(
                          (f) => f.key === field.show_when!.field,
                        );
                        fieldUpdate({
                          show_when: {
                            field: field.show_when!.field,
                            equals:
                              controller?.type === "checkbox"
                                ? e.target.value === "true"
                                : controller?.type === "number"
                                  ? Number(e.target.value)
                                  : e.target.value,
                          },
                        });
                      }}
                    />
                  </label>
                )}
                <label className="field">
                  Optional CEF mapping
                  <input
                    className="mono"
                    placeholder="e.g. destinationAddress"
                    value={field.cef_key || ""}
                    onChange={(e) => fieldUpdate({ cef_key: e.target.value })}
                  />
                </label>
              </>
            )}
          </aside>
        </div>
      )}
      {tab === "Approvals" && (
        <ApprovalRules
          form={editor}
          onChange={(approval) =>
            update({ mapping: { ...editor.mapping, approval } })
          }
        />
      )}
      {tab === "SOAR mapping" && (
        <div className="config-panel">
          <div className="config-heading">
            <Workflow size={23} />
            <div>
              <h2>Where your form lands</h2>
              <p>Configure the event your SOAR playbooks receive.</p>
            </div>
          </div>
          <div className="two-column">
            <label className="field">
              SOAR event label
              <select
                value={editor.mapping.label}
                onChange={(e) =>
                  update({
                    mapping: { ...editor.mapping, label: e.target.value },
                  })
                }
              >
                <option value="" disabled>
                  Choose an available label
                </option>
                {editor.mapping.label &&
                  !labels.labels.includes(editor.mapping.label) && (
                    <option value={editor.mapping.label} disabled>
                      {editor.mapping.label} (current · outside available
                      choices)
                    </option>
                  )}
                {labels.labels.map((label) => (
                  <option key={label} value={label}>
                    {label}
                  </option>
                ))}
              </select>
              <small>
                {labels.prefix
                  ? `Labels beginning with “${labels.prefix}”. `
                  : "All available labels. "}
                Applied to the event and submission artifact. Create additional
                labels in SOAR.
              </small>
            </label>
            <label className="field">
              Event title prefix
              <input
                value={editor.mapping.title_prefix}
                onChange={(e) =>
                  update({
                    mapping: {
                      ...editor.mapping,
                      title_prefix: e.target.value,
                    },
                  })
                }
              />
            </label>
          </div>
          <ErrorBox error={labelError} />
          {!labelError && !labels.labels.length && (
            <p className="notice">
              No labels match the configured prefix. Create a matching label in
              SOAR or update the connection settings.
            </p>
          )}
          <Button onClick={loadLabels}>
            <RefreshCw size={14} />
            Refresh labels
          </Button>
          <label className="field">
            Event tags
            <BufferedText
              value={editor.mapping.tags.join(", ")}
              onCommit={(value) =>
                update({
                  mapping: {
                    ...editor.mapping,
                    tags: value
                      .split(",")
                      .map((t) => t.trim())
                      .filter(Boolean),
                  },
                })
              }
            />
            <small>Comma-separated tags for downstream routing.</small>
          </label>
          <div className="two-column">
            <label className="field">
              Severity
              <select
                value={editor.mapping.severity}
                onChange={(e) =>
                  update({
                    mapping: { ...editor.mapping, severity: e.target.value },
                  })
                }
              >
                {["low", "medium", "high"].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <label className="field">
              Sensitivity
              <select
                value={editor.mapping.sensitivity}
                onChange={(e) =>
                  update({
                    mapping: { ...editor.mapping, sensitivity: e.target.value },
                  })
                }
              >
                {["white", "green", "amber", "red"].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
          </div>
          <label
            className={
              "toggle-row actionstack-automation-toggle " +
              (editor.mapping.run_automation ? "enabled" : "")
            }
          >
            <div>
              <span className="eyebrow">
                PLAYBOOK EXECUTION ·{" "}
                {editor.mapping.run_automation ? "ON" : "OFF"}
              </span>
              <b>Allow SOAR automation on delivery</b>
              <small>
                SOAR may run active playbooks after all form fields have
                arrived.
              </small>
            </div>
            <input
              type="checkbox"
              checked={editor.mapping.run_automation}
              onChange={(e) =>
                update({
                  mapping: {
                    ...editor.mapping,
                    run_automation: e.target.checked,
                  },
                })
              }
            />
          </label>
          <div className="notice">
            <Braces size={17} />
            All accepted fields are preserved in the event, together with
            trusted submission details.
          </div>
        </div>
      )}
      {tab === "Settings" && (
        <div className="config-panel">
          <FormAppearance form={editor} onChange={update} />
          <div className="config-heading">
            <LockKeyhole size={23} />
            <div>
              <h2>Access through Splunk roles</h2>
              <p>Assign this form to the right people in your workspace.</p>
            </div>
          </div>
          <div className="two-column">
            {(["view", "submit", "edit", "team"] as const).map((kind) => (
              <div className="field" key={kind}>
                <label>
                  {
                    {
                      view: "Who can view",
                      submit: "Who can submit",
                      edit: "Who can edit",
                      team: "Who can read team submissions",
                    }[kind]
                  }
                </label>
                <div className="role-choices">
                  {ctx.roles_available.map((role) => (
                    <label className="choice" key={role}>
                      <input
                        type="checkbox"
                        checked={editor.access[
                          (kind + "_roles") as keyof Form["access"]
                        ].includes(role)}
                        onChange={(e) => {
                          const key = (kind + "_roles") as keyof Form["access"];
                          update({
                            access: {
                              ...editor.access,
                              [key]: e.target.checked
                                ? [...editor.access[key], role]
                                : editor.access[key].filter((r) => r !== role),
                            },
                          });
                        }}
                      />
                      {role}
                    </label>
                  ))}
                </div>
                <small>
                  {kind === "team"
                    ? "Empty grants no team access. Also requires the team-read capability."
                    : "Empty allows any user with the required app capability."}
                </small>
              </div>
            ))}
          </div>
          <div className="two-column">
            <label className="field">
              Form ID
              <input
                value={editor.id}
                disabled={editor.revision > 0}
                onChange={(e) => {
                  setAutomaticId(false);
                  update({ id: e.target.value });
                }}
              />
              <small>
                Generated from the form title with a four-character suffix.
                Fixed after the first save.
              </small>
            </label>
            <label className="field">
              Category
              <input
                value={editor.category}
                onChange={(e) => update({ category: e.target.value })}
              />
            </label>
          </div>
        </div>
      )}
      {tab === "Versions" && (
        <div className="config-panel">
          <h2>Version history</h2>
          <p className="muted">
            Restore an earlier definition into the editor, then save or publish
            it as a new revision.
          </p>
          {versions
            .slice()
            .reverse()
            .map((v) => (
              <div className="version-row" key={v.revision}>
                <span className="version-icon">
                  <Clock3 size={17} />
                </span>
                <div>
                  <b>
                    Revision {v.revision} · {v.state}
                  </b>
                  <small>
                    {v.updated_at ? formatDate(v.updated_at) : ""} ·{" "}
                    {v.updated_by}
                  </small>
                </div>
                <Button
                  onClick={() => {
                    setEditor({
                      ...cloneDefinition(v),
                      revision: editor.revision,
                      state: "draft",
                    });
                    setTab("Build");
                    setSelected(0);
                    setNotice(
                      "Earlier definition loaded. Save or publish to create a new revision.",
                    );
                  }}
                >
                  Restore
                </Button>
              </div>
            ))}
          {!versions.length && (
            <p>Save your first draft to begin version history.</p>
          )}
          {editor.revision > 0 && can(ctx, "publish") && (
            <div className="archive-row">
              <div>
                <b>Archive this form</b>
                <p>
                  Removes it from the catalog. Submission history is retained.
                </p>
              </div>
              <Button
                disabled={busy}
                onClick={async () => {
                  if (
                    !window.confirm(
                      "Archive this form and remove it from the catalog?",
                    )
                  )
                    return;
                  setBusy(true);
                  try {
                    await api("/admin/forms/" + editor.id + "/archive", {
                      expected_revision: editor.revision,
                    });
                    await load();
                    setEditor(null);
                    onSaved();
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Archive form
              </Button>
            </div>
          )}
        </div>
      )}
      {preview && (
        <Modal title="Form preview" onClose={() => setPreview(false)}>
          <div className="modal-body">
            <div className="notice">
              <Eye size={16} />
              Preview only · no event will be sent.
            </div>
            <h2>{editor.title}</h2>
            <p className="muted">{editor.description}</p>
            {previewMessage && (
              <div
                className={"notice " + (previewValid ? "success" : "error")}
                role="status"
              >
                {previewMessage}
              </div>
            )}
            <FormFields
              preview
              form={editor}
              values={previewValues}
              setValues={(v) => {
                setPreviewValues(v);
                setPreviewErrors({});
                setPreviewMessage("");
              }}
              errors={previewErrors}
            />
          </div>
          <div className="modal-actions">
            <Button onClick={() => setPreview(false)}>Close preview</Button>
            <Button
              primary
              disabled={previewBusy}
              onClick={async () => {
                setPreviewBusy(true);
                setPreviewErrors({});
                setPreviewMessage("");
                setPreviewValid(false);
                try {
                  const r = await api<{ message: string }>(
                    "/admin/forms/validate",
                    { form: cleanForm(editor), inputs: previewValues },
                  );
                  setPreviewValid(true);
                  setPreviewMessage(r.message);
                } catch (e) {
                  const ex = e as ApiError;
                  setPreviewMessage(ex.message);
                  setPreviewErrors(ex.fields || {});
                } finally {
                  setPreviewBusy(false);
                }
              }}
            >
              {previewBusy ? "Checking…" : "Test validation"}
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}

function SetupWizard({
  ctx,
  workspaces,
  onRefresh,
  onComplete,
}: {
  ctx: Context;
  workspaces: Workspace[];
  onRefresh: () => Promise<void>;
  onComplete: (id: string) => void;
}) {
  const [step, setStep] = useState(1),
    [workspace, setWorkspace] = useState<Workspace | null>(null),
    [existing, setExisting] = useState(
      workspaces.find((w) => w.state === "active")?.id || "",
    ),
    [connection, setConnection] = useState<Settings | null>(null),
    [labels, setLabels] = useState<string[]>([]);
  return (
    <section className="actionstack-setup">
      <div className="page-heading compact">
        <div>
          <div className="eyebrow">WELCOME TO ACTIONSTACK</div>
          <h1>Set up your team</h1>
          <p>A workspace, the right access, and a connection to SOAR.</p>
        </div>
      </div>
      <ol className="actionstack-setup-steps">
        {["Workspace & roles", "SOAR connection", "Ready to build"].map(
          (name, i) => (
            <li
              key={name}
              className={
                step === i + 1 ? "current" : step > i + 1 ? "complete" : ""
              }
            >
              <span>{step > i + 1 ? "✓" : i + 1}</span>
              {name}
            </li>
          ),
        )}
      </ol>
      {step === 1 && (
        <>
          {workspaces.some((w) => w.state === "active") && (
            <div className="config-panel actionstack-existing-workspace">
              <h2>Use an existing workspace</h2>
              <label className="field">
                Workspace
                <select
                  value={existing}
                  onChange={(e) => setExisting(e.target.value)}
                >
                  {workspaces
                    .filter((w) => w.state === "active")
                    .map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name}
                      </option>
                    ))}
                </select>
              </label>
              <Button
                onClick={() => {
                  const w = workspaces.find((w) => w.id === existing);
                  if (w) {
                    setWorkspace(w);
                    setStep(2);
                  }
                }}
              >
                Use this workspace
                <ArrowRight size={15} />
              </Button>
            </div>
          )}
          <WorkspaceEditor
            ctx={ctx}
            onSaved={(w) => {
              setWorkspace(w);
              void onRefresh();
              setStep(2);
            }}
          />
        </>
      )}
      {step === 2 && (
        <>
          <button className="back-link" onClick={() => setStep(1)}>
            <ArrowLeft size={15} />
            Workspace & roles
          </button>
          <ConnectionSettings
            onSaved={() => {
              void onRefresh();
            }}
            onVerified={(settings, available) => {
              setConnection(settings);
              setLabels(available);
              setStep(3);
            }}
          />
        </>
      )}
      {step === 3 && workspace && (
        <div className="config-panel actionstack-setup-complete">
          <CheckCircle2 size={36} />
          <h2>{workspace.name} is ready</h2>
          <p>
            SOAR read access verified. New forms will use your workspace's
            default permissions.
          </p>
          {workspace.role_groups && (
            <>
              <h3>Assign your team in Splunk</h3>
              {Object.entries(workspace.role_groups).map(([level, roles]) => (
                <p key={level}>
                  <b>{level}:</b> {roles.join(", ") || "No roles assigned"}
                </p>
              ))}
              <p className="muted">
                Assign these roles to users or identity-provider groups using
                Splunk access controls.
              </p>
            </>
          )}
          <h3>Event label prefix</h3>
          <p>{connection?.label_prefix || "No prefix · all labels"}</p>
          <p className="muted">
            Available labels:{" "}
            {labels
              .filter((l) => l.startsWith(connection?.label_prefix || ""))
              .join(", ") ||
              "None yet. Create a matching label in SOAR, then refresh labels in Form builder."}
          </p>
          <div className="button-row">
            <Button onClick={() => setStep(2)}>Back to connection</Button>
            <Button primary onClick={() => onComplete(workspace.id)}>
              Open workspace
              <ArrowRight size={15} />
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}

function ConnectionSettings({
  onSaved,
  onVerified,
}: {
  onSaved: () => void;
  onVerified?: (settings: Settings, labels: string[]) => void;
}) {
  const [dirty, setDirty] = useState(false);
  const [settings, setSettings] = useState<Settings | null>(null),
    [token, setToken] = useState(""),
    [error, setError] = useState(""),
    [result, setResult] = useState(""),
    [busy, setBusy] = useState(false);
  function changeSettings(s: Settings) {
    setSettings(s);
    setDirty(true);
    setResult("");
  }
  useEffect(() => {
    api<Settings>("/settings")
      .then(setSettings)
      .catch((e) => setError(e.message));
  }, []);
  async function save() {
    if (!settings) return;
    setBusy(true);
    setError("");
    setResult("");
    try {
      setSettings(
        await api<Settings>(
          "/settings",
          connectionSettingsPayload(settings, token),
        ),
      );
      setToken("");
      setDirty(false);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading compact">
        <div>
          <div className="eyebrow">WORKSPACE SETTINGS</div>
          <h1>Connect your workflows</h1>
          <p>A secure connection from Splunk Enterprise to Splunk SOAR.</p>
        </div>
      </div>
      <ErrorBox error={error} />
      {settings && (
        <div className="settings-layout">
          <section className="config-panel">
            <div className="config-heading">
              <span className="automation-icon cyan">
                <Workflow size={23} />
              </span>
              <div>
                <h2>Splunk SOAR</h2>
                <p>On-premises connection</p>
              </div>
              <Badge
                status={
                  settings.demo
                    ? "draft"
                    : settings.token_configured
                      ? "submitted"
                      : "pending"
                }
              >
                {settings.demo
                  ? "Demo"
                  : settings.token_configured
                    ? "Configured"
                    : "Setup needed"}
              </Badge>
            </div>
            {settings.demo && (
              <div className="notice">
                This workspace simulates SOAR. Saving settings never connects to
                a live system.
              </div>
            )}
            <label className="field">
              SOAR URL
              <input
                placeholder="https://soar.example.com"
                value={settings.soar_url}
                onChange={(e) =>
                  changeSettings({ ...settings, soar_url: e.target.value })
                }
              />
            </label>
            <label className="field">
              Event label prefix
              <input
                maxLength={64}
                placeholder="actionstack_"
                value={settings.label_prefix}
                onChange={(e) =>
                  changeSettings({ ...settings, label_prefix: e.target.value })
                }
              />
              <small>
                Form builders can select available SOAR labels starting with
                this prefix. Leave empty to list all labels. Labels must already
                exist in SOAR.
              </small>
            </label>
            <label className="field">
              Automation token
              <input
                type="password"
                autoComplete="new-password"
                placeholder={
                  settings.token_configured
                    ? "Saved securely · enter to replace"
                    : "Enter SOAR automation token"
                }
                value={token}
                onChange={(e) => {
                  setToken(e.target.value);
                  setDirty(true);
                  setResult("");
                }}
              />
              <small>
                Stored in Splunk's encrypted credential store. Never returned to
                the browser.
              </small>
            </label>
            <div className="two-column">
              <label className="field">
                Source instance name
                <input
                  value={settings.instance_name}
                  onChange={(e) =>
                    changeSettings({
                      ...settings,
                      instance_name: e.target.value,
                    })
                  }
                />
              </label>
              <label className="field">
                Source asset ID <span className="optional">Optional</span>
                <input
                  type="number"
                  min="1"
                  placeholder="SOAR source asset ID"
                  value={settings.asset_id ?? ""}
                  onChange={(e) =>
                    changeSettings({
                      ...settings,
                      asset_id: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                />
              </label>
            </div>
            <label className="toggle-row actionstack-automation-toggle">
              <div>
                <b>Ignore certificate validation</b>
                <small>
                  Allow self-signed or untrusted SOAR certificates. HTTPS stays
                  encrypted, but the server's identity will not be verified.
                </small>
              </div>
              <input
                type="checkbox"
                checked={settings.ignore_certificate_errors ?? false}
                onChange={(e) =>
                  changeSettings({
                    ...settings,
                    ignore_certificate_errors: e.target.checked,
                  })
                }
              />
            </label>
            <p className="muted">
              {settings.ignore_certificate_errors
                ? "Certificate validation is disabled for this SOAR connection."
                : settings.ca_pem
                  ? "Certificate validation is enabled using your previously saved CA certificate."
                  : "Certificate validation is enabled using the system trust store."}
            </p>
            <label className="field">
              Request timeout
              <select
                value={settings.request_timeout}
                onChange={(e) =>
                  changeSettings({
                    ...settings,
                    request_timeout: Number(e.target.value),
                  })
                }
              >
                {[5, 10, 15, 20, 30].map((v) => (
                  <option key={v} value={v}>
                    {v} seconds
                  </option>
                ))}
              </select>
            </label>
            {result && (
              <div className="notice success">
                <CheckCircle2 size={16} />
                {result}
              </div>
            )}
            <div className="button-row settings-actions">
              <Button
                disabled={
                  busy ||
                  dirty ||
                  (!settings.token_configured && !settings.demo)
                }
                onClick={async () => {
                  setBusy(true);
                  setError("");
                  setResult("");
                  try {
                    const r = await api<{ message: string; labels: string[] }>(
                      "/settings/test",
                      {},
                    );
                    setResult(
                      r.message + " Available labels: " + r.labels.join(", "),
                    );
                    onVerified?.(settings, r.labels);
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <RefreshCw size={15} />
                {onVerified
                  ? "Test saved connection & continue"
                  : "Test saved connection"}
              </Button>
              <Button primary disabled={busy} onClick={save}>
                <Save size={15} />
                Save connection
              </Button>
            </div>
            {dirty && (
              <p className="muted">
                Save your changes before testing the connection.
              </p>
            )}
          </section>
          <aside className="aside-card">
            <LockKeyhole size={23} />
            <h3>Built around your access</h3>
            <p>
              Splunk authenticates your users. A dedicated SOAR automation
              identity delivers their requests.
            </p>
            <div className="property-divider" />
            <h3>Search head cluster</h3>
            <p>
              Forms, submission receipts and delivery locks use shared KV Store
              collections. Deploy the same app bundle to every member.
            </p>
            <div className="property-divider" />
            <h3>Intake, ready for automation</h3>
            <p>
              Your SOAR playbooks handle approvals and security actions after
              receiving the event.
            </p>
          </aside>
        </div>
      )}
    </>
  );
}

const mount = () => {
  const root = document.getElementById("actionstack-root");
  if (root && !root.dataset.mounted) {
    root.dataset.mounted = "true";
    document.body.classList.add("actionstack-host");
    createRoot(root).render(<App />);
  }
};
if (document.readyState === "loading")
  document.addEventListener("DOMContentLoaded", mount);
else mount();
