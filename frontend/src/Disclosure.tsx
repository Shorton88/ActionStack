import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";

export function Disclosure({
  title,
  children,
  initiallyOpen = false,
}: {
  title: string;
  children: ReactNode;
  initiallyOpen?: boolean;
}) {
  const [open, setOpen] = useState(initiallyOpen);
  return (
    <details
      className="actionstack-disclosure"
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>
        {title}
        <ChevronDown size={15} aria-hidden="true" />
      </summary>
      <div className="actionstack-disclosure-content">{children}</div>
    </details>
  );
}
