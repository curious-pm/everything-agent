export function RobotFigure() {
  return (
    <svg viewBox="0 0 520 400" className="robot-figure" role="img" aria-label="Reachy">
      <defs>
        <radialGradient id="pool" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="var(--state)" stopOpacity="0.45" />
          <stop offset="100%" stopColor="var(--state)" stopOpacity="0" />
        </radialGradient>
      </defs>
      <ellipse cx="260" cy="356" rx="240" ry="56" fill="url(#pool)" />
      <ellipse cx="260" cy="358" rx="104" ry="14" fill="var(--ink)" fillOpacity="0.16" />
      <path d="M226 104 C214 68 196 46 206 12" stroke="var(--ink-soft)" strokeWidth="5" fill="none" strokeLinecap="round" />
      <path d="M294 104 C306 68 324 46 314 12" stroke="var(--ink-soft)" strokeWidth="5" fill="none" strokeLinecap="round" />
      <circle cx="206" cy="12" r="7" fill="#fff" stroke="#c9cccb" strokeWidth="2" />
      <circle cx="314" cy="12" r="7" fill="#fff" stroke="#c9cccb" strokeWidth="2" />
      <path d="M164 356 C164 276 196 236 260 236 C324 236 356 276 356 356 Z" fill="#e2e4e3" />
      <path d="M196 356 C196 284 220 250 260 250 C300 250 324 284 324 356 Z" fill="#fff" />
      <rect x="232" y="210" width="56" height="40" rx="10" fill="#3a4049" />
      <rect x="160" y="94" width="200" height="136" rx="64" fill="#fff" stroke="#e1e3e2" strokeWidth="2" />
      <rect x="184" y="120" width="152" height="84" rx="42" fill="#1d2127" />
      <circle cx="226" cy="162" r="24" fill="#0f1216" stroke="#3a4049" strokeWidth="5" />
      <circle cx="294" cy="162" r="24" fill="#0f1216" stroke="#3a4049" strokeWidth="5" />
      <circle cx="226" cy="162" r="9" fill="var(--state)" />
      <circle cx="294" cy="162" r="9" fill="var(--state)" />
    </svg>
  );
}
