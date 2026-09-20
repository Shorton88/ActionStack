import { useEffect, useState } from "react";
import { ArrowRight, Layers, Plus, Search, Star } from "lucide-react";
import type { Form, Workspace } from "./types";
import { formIcon } from "./FormIcons";
export function Catalog({
  forms,
  workspaces = [],
  favorites,
  busy,
  onFavorite,
  onOpen,
  onCreate,
}: {
  forms: Form[];
  workspaces?: Workspace[];
  favorites: string[];
  busy: boolean;
  onFavorite: (f: Form) => void;
  onOpen: (f: Form) => void;
  onCreate?: () => void;
}) {
  const [search, setSearch] = useState(""),
    [category, setCategory] = useState(""),
    [onlyFavorites, setOnlyFavorites] = useState(false),
    [page, setPage] = useState(0);
  const categories = Array.from(
    new Set(forms.map((f) => f.category || "General")),
  ).sort();
  const workspaceName = (form: Form) =>
    workspaces.find((w) => w.id === (form.workspace_id || "security"))?.name ||
    form.workspace_id ||
    "Workspace";
  const matches = forms.filter(
    (f) =>
      (!category || (f.category || "General") === category) &&
      (!onlyFavorites || favorites.includes(f.id)) &&
      [f.title, f.description, f.category, workspaceName(f)]
        .join(" ")
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  useEffect(() => setPage(0), [search, category, onlyFavorites, forms]);
  const pageCount = Math.max(1, Math.ceil(matches.length / 12)),
    current = Math.min(page, pageCount - 1);
  return (
    <div className="actionstack-catalog">
      <section className="actionstack-catalog-banner">
        <div>
          <div className="eyebrow">YOUR TEAM'S WORKFLOW LIBRARY</div>
          <h1>Automation catalog</h1>
          <p>Find a workflow, share the details, and follow its progress.</p>
        </div>
        <div className="actionstack-catalog-mark" aria-hidden="true">
          <Layers size={48} />
        </div>
        {onCreate && (
          <button className="button primary" onClick={onCreate}>
            <Plus size={16} />
            Create a form
          </button>
        )}
      </section>
      <div className="actionstack-catalog-layout">
        <aside className="actionstack-catalog-filters">
          <h3>Browse</h3>
          <button
            className={!onlyFavorites ? "selected" : ""}
            onClick={() => setOnlyFavorites(false)}
          >
            <Layers size={16} />
            All automations<span>{forms.length}</span>
          </button>
          <button
            className={onlyFavorites ? "selected" : ""}
            onClick={() => setOnlyFavorites(true)}
          >
            <Star size={16} />
            Favorites
            <span>{forms.filter((f) => favorites.includes(f.id)).length}</span>
          </button>
          <h3>Categories</h3>
          <button
            className={!category ? "selected" : ""}
            onClick={() => setCategory("")}
          >
            All categories
          </button>
          {categories.map((c) => (
            <button
              key={c}
              className={category === c ? "selected" : ""}
              onClick={() => setCategory(c)}
            >
              {c}
            </button>
          ))}
        </aside>
        <section>
          <div className="actionstack-catalog-toolbar">
            <div>
              <h2>
                {onlyFavorites
                  ? "Your favorites"
                  : category || "Explore workflows"}
              </h2>
              <small>
                {matches.length}{" "}
                {matches.length === 1 ? "automation" : "automations"}
              </small>
            </div>
            <label className="search-box">
              <Search size={16} />
              <input
                aria-label="Search catalog"
                placeholder="Search by name, team, or keyword…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
          </div>
          <div className="actionstack-catalog-grid">
            {matches.slice(current * 12, current * 12 + 12).map((f) => {
              const Icon = formIcon(f.icon);
              const favorite = favorites.includes(f.id);
              return (
                <article
                  className={"actionstack-catalog-card " + f.accent}
                  key={f.id}
                >
                  <div className="card-top">
                    <span className="automation-icon">
                      <Icon size={23} />
                    </span>
                    <button
                      className={
                        "actionstack-favorite " + (favorite ? "selected" : "")
                      }
                      disabled={busy}
                      aria-pressed={favorite}
                      aria-label={
                        (favorite ? "Remove favorite: " : "Favorite: ") +
                        f.title
                      }
                      title={favorite ? "Remove favorite" : "Add to favorites"}
                      onClick={() => onFavorite(f)}
                    >
                      <Star
                        size={19}
                        fill={favorite ? "currentColor" : "none"}
                      />
                    </button>
                  </div>
                  <span className="card-category">
                    {f.category || "General"}
                  </span>
                  <h3>
                    <button onClick={() => onOpen(f)}>{f.title}</button>
                  </h3>
                  <p>{f.description}</p>
                  <div className="actionstack-catalog-card-footer">
                    <span>{workspaceName(f)}</span>
                    <button
                      onClick={() => onOpen(f)}
                      aria-label={"Open " + f.title}
                    >
                      Open form
                      <ArrowRight size={15} />
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
          {!matches.length && (
            <div className="empty">
              <Star size={28} />
              <h3>
                {onlyFavorites
                  ? "No favorites here yet"
                  : "No matching workflows"}
              </h3>
              <p>
                {onlyFavorites
                  ? "Star an automation to keep it close at hand."
                  : "Try another search or category."}
              </p>
              <button
                className="button"
                onClick={() => {
                  setOnlyFavorites(false);
                  setCategory("");
                  setSearch("");
                }}
              >
                Browse all
              </button>
            </div>
          )}
          {pageCount > 1 && (
            <div className="actionstack-catalog-pagination">
              <button
                className="button"
                disabled={!current}
                onClick={() => setPage(current - 1)}
              >
                Previous
              </button>
              <span>
                Page {current + 1} of {pageCount}
              </span>
              <button
                className="button"
                disabled={current + 1 >= pageCount}
                onClick={() => setPage(current + 1)}
              >
                Next
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
