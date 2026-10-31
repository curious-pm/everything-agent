import type { ReactNode } from "react";
import "./controls.css";

function RowText({ label, hint }: { label: string; hint?: string }) {
  return (
    <span className="row-text">
      <span>{label}</span>
      {hint && <span className="row-hint">{hint}</span>}
    </span>
  );
}

export function SwitchRow({ label, hint, checked, onChange, disabled }: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className="row-item switch-row">
      <RowText label={label} hint={hint} />
      <input type="checkbox" role="switch" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
    </label>
  );
}

export function Row({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="row-item">
      <RowText label={label} hint={hint} />
      <span className="row-control">{children}</span>
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warn"; children: ReactNode }) {
  return <div className={`notice ${tone}`} role={tone === "warn" ? "alert" : "status"}>{children}</div>;
}
