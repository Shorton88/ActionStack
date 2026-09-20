import { createTransport } from "./transport.js";
export { ApiError } from "./transport.js";

const request = createTransport({
  pathname: window.location.pathname,
  port: window.location.port,
  protocol: window.location.protocol,
  cookie: () => document.cookie,
  fetch: (input, init) => fetch(input, init),
});

export async function api<T>(path: string, body?: unknown): Promise<T> {
  return request(path, body) as Promise<T>;
}

export function cleanForm(form: import("./types").Form) {
  const {
    workspace_id,
    id,
    title,
    description,
    category,
    icon,
    accent,
    intro,
    fields,
    mapping,
    access,
  } = form;
  return {
    workspace_id,
    id,
    title,
    description,
    category,
    icon,
    accent,
    intro,
    fields,
    mapping,
    access,
  };
}
export function can(context: import("./types").Context, cap: string) {
  return (
    context.capabilities.includes("actionstack_admin") ||
    context.capabilities.includes("actionstack_" + cap)
  );
}
