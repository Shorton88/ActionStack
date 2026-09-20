import { useEffect, useState } from "react";
import { api } from "./api";
import type { Context, Workspace } from "./types";

const emptyWorkspace: Workspace = {
  id: "",
  name: "",
  description: "",
  state: "active",
  revision: 0,
  roles: [],
};
const levels = ["viewer", "user", "admin"] as const;
export function WorkspaceEditor({
  ctx,
  initial,
  onSaved,
  onCancel,
}: {
  ctx: Context;
  initial?: Workspace;
  onSaved: (w: Workspace) => void;
  onCancel?: () => void;
}) {
  const [edit, setEdit] = useState<Workspace>(initial || emptyWorkspace);
  const [createRoles, setCreateRoles] = useState(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const patch = (p: Partial<Workspace>) => setEdit((x) => ({ ...x, ...p }));
  const groups = edit.role_groups || { viewer: [], user: [], admin: [] };
  const names = levels.map(
    (level) => `as_${(edit.id || "namespace").replaceAll("-", "_")}_${level}`,
  );
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (!createRoles && !edit.revision && !groups.admin.length)
        throw new Error(
          "Choose an existing admin role or enable Create roles in Splunk.",
        );
      const workspace = {
        id: edit.id,
        name: edit.name,
        description: edit.description,
        state: edit.state,
        roles: edit.roles,
        ...(!createRoles && (edit.role_groups || !edit.revision)
          ? { role_groups: groups }
          : {}),
      };
      const result = await api<Workspace>("/admin/workspaces/save", {
        workspace,
        expected_revision: edit.revision,
        create_roles: createRoles,
      });
      setEdit(result);
      setCreateRoles(false);
      onSaved(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="config-panel" onSubmit={save}>
      <h2>{edit.revision ? "Edit workspace" : "Create your workspace"}</h2>
      <p className="muted">Give your team a home for forms and submissions.</p>
      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}
      <label className="field">
        Workspace name
        <input
          required
          maxLength={80}
          value={edit.name}
          onChange={(e) =>
            patch({
              name: e.target.value,
              ...(!edit.revision
                ? {
                    id: e.target.value
                      .toLowerCase()
                      .replace(/[^a-z0-9]+/g, "-")
                      .replace(/^-|-$/g, "")
                      .slice(0, 64),
                  }
                : {}),
            })
          }
        />
      </label>
      <label className="field">
        Namespace ID
        <input
          required
          disabled={!!edit.revision}
          pattern="[a-z][a-z0-9-]{0,63}"
          maxLength={64}
          value={edit.id}
          onChange={(e) => patch({ id: e.target.value })}
        />
        <small>
          Used in the workspace role names. Cannot change after creation.
        </small>
      </label>
      <label className="field">
        Description
        <textarea
          maxLength={500}
          value={edit.description}
          onChange={(e) => patch({ description: e.target.value })}
        />
      </label>
      {!edit.revision && (
        <>
          <label className="toggle-row actionstack-automation-toggle">
            <div>
              <b>Create roles in Splunk</b>
              <small>
                Create viewer, user and admin roles for this namespace.
              </small>
            </div>
            <input
              type="checkbox"
              checked={createRoles}
              disabled={!ctx.can_create_roles}
              onChange={(e) => setCreateRoles(e.target.checked)}
            />
          </label>
          {!ctx.can_create_roles && (
            <p className="muted">
              Your account needs Splunk role-management permissions to create
              roles. Select existing roles below.
            </p>
          )}
        </>
      )}
      <div className="actionstack-workspace-permissions">
        {levels.map((level, i) => (
          <section key={level}>
            <h3>
              {level === "admin"
                ? "Workspace admin"
                : level === "user"
                  ? "User"
                  : "Viewer"}
            </h3>
            <p>
              {level === "viewer"
                ? "View forms and all workspace submissions."
                : level === "user"
                  ? "View all submissions and submit automations."
                  : "View, submit, edit and publish workspace forms."}
            </p>
            {createRoles ? (
              <code>{names[i]}</code>
            ) : (
              <div className="role-choices">
                {ctx.roles_available.map((role) => (
                  <label className="choice" key={role}>
                    <input
                      type="checkbox"
                      checked={groups[level].includes(role)}
                      onChange={(e) =>
                        patch({
                          role_groups: {
                            ...groups,
                            [level]: e.target.checked
                              ? [...groups[level], role]
                              : groups[level].filter((r) => r !== role),
                          },
                        })
                      }
                    />
                    {role}
                  </label>
                ))}
              </div>
            )}
          </section>
        ))}
      </div>
      <p className="muted">
        These become the defaults for new forms. Existing forms keep their
        permissions. Workspace admins do not receive app-wide administration.
        Assign the roles to users or identity-provider groups in Splunk.
      </p>
      {!createRoles && (
        <p className="muted">
          Existing roles also need the corresponding app capabilities: use and
          read_team; submit for users; edit and publish for admins.
        </p>
      )}
      {!!edit.revision && (
        <label className="field">
          State
          <select
            value={edit.state}
            disabled={edit.id === "security"}
            onChange={(e) => patch({ state: e.target.value })}
          >
            <option value="active">Active</option>
            <option value="archived">Archived</option>
          </select>
        </label>
      )}
      {!!edit.roles.length && !!edit.revision && (
        <details className="actionstack-legacy-members">
          <summary>Additional workspace membership</summary>
          <p>
            These existing roles grant workspace access. Form permissions still
            apply.
          </p>
          <div className="role-choices">
            {ctx.roles_available.map((role) => (
              <label className="choice" key={role}>
                <input
                  type="checkbox"
                  checked={edit.roles.includes(role)}
                  onChange={(e) =>
                    patch({
                      roles: e.target.checked
                        ? [...edit.roles, role]
                        : edit.roles.filter((r) => r !== role),
                    })
                  }
                />
                {role}
              </label>
            ))}
          </div>
        </details>
      )}
      <div className="button-row actionstack-manager-actions">
        {onCancel && (
          <button
            type="button"
            className="button"
            disabled={busy}
            onClick={onCancel}
          >
            Cancel
          </button>
        )}
        <button className="button primary" disabled={busy}>
          {busy
            ? "Saving…"
            : edit.revision
              ? "Save workspace"
              : "Create workspace"}
        </button>
      </div>
    </form>
  );
}

export function Management({
  ctx,
  onSaved,
}: {
  kind: "workspaces";
  ctx: Context;
  onSaved: () => void;
}) {
  const [items, setItems] = useState<Workspace[]>([]),
    [edit, setEdit] = useState<Workspace | null>(null),
    [error, setError] = useState("");
  const load = () => api<Workspace[]>("/admin/workspaces").then(setItems);
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  return (
    <>
      <div className="page-heading compact">
        <div>
          <div className="eyebrow">ADMINISTRATION</div>
          <h1>Team workspaces</h1>
          <p>Organize forms and set each team's default access.</p>
        </div>
        <button
          className="button primary"
          onClick={() => setEdit({ ...emptyWorkspace })}
        >
          Add workspace
        </button>
      </div>
      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}
      <div className="actionstack-management">
        <div className="config-panel">
          <h3>Workspaces</h3>
          {!items.length && <p>Create your first workspace to get started.</p>}
          {items.map((w) => (
            <button
              className="actionstack-record"
              key={w.id}
              onClick={() => setEdit(w)}
            >
              <b>{w.name}</b>
              <small>
                {w.state} · revision {w.revision}
              </small>
            </button>
          ))}
        </div>
        {edit ? (
          <WorkspaceEditor
            key={edit.id + ":" + edit.revision}
            initial={edit}
            ctx={ctx}
            onCancel={() => setEdit(null)}
            onSaved={(w) => {
              setEdit(w);
              void load();
              onSaved();
            }}
          />
        ) : (
          <div className="config-panel">
            <h2>A workspace for every team</h2>
            <p>Select a workspace to manage it, or add one for another team.</p>
          </div>
        )}
      </div>
    </>
  );
}
