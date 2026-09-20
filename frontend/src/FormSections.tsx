import { useEffect, useState, type ReactNode } from "react";
import type { Field } from "./types";

function Section({
  section,
  invalid,
  children,
}: {
  section: Field;
  invalid: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(!section.collapsed || invalid);
  useEffect(() => {
    if (invalid) setOpen(true);
  }, [invalid]);
  return (
    <details
      className="actionstack-form-section"
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
      onInvalidCapture={(e) => {
        e.currentTarget.open = true;
        setOpen(true);
      }}
    >
      <summary>
        <span>{section.label}</span>
        {section.help && <small>{section.help}</small>}
      </summary>
      <div className="actionstack-section-fields">{children}</div>
    </details>
  );
}

export function FormSections({
  fields,
  values,
  errors,
  renderField,
}: {
  fields: Field[];
  values: Record<string, unknown>;
  errors: Record<string, string>;
  renderField: (f: Field) => ReactNode;
}) {
  const groups: { section?: Field; fields: Field[] }[] = [{ fields: [] }];
  for (const field of fields) {
    if (field.type === "section") groups.push({ section: field, fields: [] });
    else groups[groups.length - 1].fields.push(field);
  }
  return (
    <>
      {groups.map((g, i) => {
        const content = g.fields.map(renderField),
          section = g.section;
        if (
          !section ||
          (section.show_when &&
            values[section.show_when.field] !== section.show_when.equals)
        )
          return <div key={section?.key || i}>{content}</div>;
        return (
          <Section
            key={section.key}
            section={section}
            invalid={g.fields.some((f) => !!errors[f.key])}
          >
            {content}
          </Section>
        );
      })}
    </>
  );
}
