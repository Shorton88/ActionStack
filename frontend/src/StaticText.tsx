import { Info, TriangleAlert } from "lucide-react";
import type { Field } from "./types";

/** Plain text only: form authors cannot inject HTML into a submission page. */
export function StaticText({ field }: { field: Field }) {
  const tone = field.tone || "text";
  return (
    <div
      className={"actionstack-static-text " + tone}
      role={tone === "warning" ? "alert" : undefined}
    >
      {tone === "info" && <Info size={20} aria-hidden="true" />}
      {tone === "warning" && <TriangleAlert size={20} aria-hidden="true" />}
      <div>
        <h3>{field.label}</h3>
        {field.help && <p>{field.help}</p>}
      </div>
    </div>
  );
}
