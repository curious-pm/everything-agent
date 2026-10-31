export function ReachyMark({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" role="img" aria-label="Reachy">
      <path d="M11 8 L9 2 M21 8 L23 2" stroke="var(--ink)" strokeWidth="2" strokeLinecap="round" />
      <rect x="3" y="8" width="26" height="19" rx="9.5" fill="var(--ink)" />
      <circle cx="11.5" cy="17.5" r="3.5" fill="var(--state)" />
      <circle cx="20.5" cy="17.5" r="3.5" fill="var(--state)" />
    </svg>
  );
}
