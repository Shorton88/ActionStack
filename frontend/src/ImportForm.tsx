import { useState } from "react";
import { api } from "./api";
import type { Form, Workspace } from "./types";
import { MAX_FORM_FILE_BYTES, parseFormFile } from "./form-transfer.js";

export function ImportForm({
  workspaces,
  workspaceId,
  onImported,
  onCancel,
}: {
  workspaces: Workspace[];
  workspaceId: string;
  onImported: (form: Form) => void;
  onCancel: () => void;
}) {
  const [destination, setDestination] = useState(
    workspaces.some((w) => w.id === workspaceId)
      ? workspaceId
      : workspaces[0]?.id || "",
  );
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        if (!file || !destination) return;
        setBusy(true);
        setError("");
        try {
          if (file.size > MAX_FORM_FILE_BYTES)
            throw new Error(
              "Choose an ActionStack form JSON file under 200 KB.",
            );
          const document = parseFormFile(await file.text());
          const form = await api<Form>("/admin/forms/import", {
            document,
            workspace_id: destination,
          });
          onImported(form);
        } catch (err) {
          setError((err as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <div className="modal-body">
        <p className="muted">
          Open an exported form as a new draft. Review its settings, then save
          or publish.
        </p>
        <label className="field">
          Form JSON file
          <input
            type="file"
            accept=".json,application/json"
            required
            disabled={busy}
            onChange={(e) => {
              setFile(e.target.files?.[0] || null);
              setError("");
            }}
          />
          <small>One ActionStack form export, up to 200 KB.</small>
        </label>
        <label className="field">
          Destination workspace
          <select
            required
            value={destination}
            disabled={busy}
            onChange={(e) => setDestination(e.target.value)}
          >
            {!workspaces.length && (
              <option value="">No workspace available</option>
            )}
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </label>
        <p className="muted">
          The workspace’s default access applies. SOAR mapping and lookup
          searches are included; check that their labels, apps, and lookups
          exist here. Existing forms are kept.
        </p>
        {error && (
          <div className="notice error" role="alert">
            {error}
          </div>
        )}
      </div>
      <div className="modal-actions">
        <button
          type="button"
          className="button"
          disabled={busy}
          onClick={onCancel}
        >
          Cancel
        </button>
        <button
          type="submit"
          className="button primary"
          disabled={busy || !file || !destination}
        >
          {busy ? "Checking form…" : "Open imported draft"}
        </button>
      </div>
    </form>
  );
}
