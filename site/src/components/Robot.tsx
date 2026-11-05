import { useId } from "react";

export function Robot() {
  const pool = useId();
  return (
    <svg className="robot" viewBox="0 0 520 400" aria-hidden="true">
      <defs>
        <radialGradient id={pool} cx="50%" cy="50%" r="50%">
          <stop offset="0%" className="pool-in" />
          <stop offset="100%" className="pool-out" />
        </radialGradient>
      </defs>
      <ellipse cx="260" cy="356" rx="240" ry="56" fill={`url(#${pool})`} />
      <ellipse cx="260" cy="358" rx="104" ry="14" className="shadow" />
      <path d="M164 356 C164 276 196 236 260 236 C324 236 356 276 356 356 Z" className="body-back" />
      <path d="M196 356 C196 284 220 250 260 250 C300 250 324 284 324 356 Z" className="body" />
      <rect x="232" y="210" width="56" height="40" rx="10" className="neck" />
      <g className="head">
        <path d="M226 104 C214 68 196 46 206 12" className="antenna" />
        <path d="M294 104 C306 68 324 46 314 12" className="antenna" />
        <circle cx="206" cy="12" r="7" className="tip" />
        <circle cx="314" cy="12" r="7" className="tip" />
        <rect x="160" y="94" width="200" height="136" rx="64" className="shell" />
        <rect x="184" y="120" width="152" height="84" rx="42" className="visor" />
        <circle cx="226" cy="162" r="24" className="socket" />
        <circle cx="294" cy="162" r="24" className="socket" />
        <circle cx="226" cy="162" r="9" className="eye" />
        <circle cx="294" cy="162" r="9" className="eye" />
      </g>
    </svg>
  );
}
