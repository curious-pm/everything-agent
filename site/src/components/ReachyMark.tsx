export function ReachyMark({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className="mark">
      <path d="M11 8 L9 2 M21 8 L23 2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <rect x="3" y="8" width="26" height="19" rx="9.5" fill="currentColor" />
      <circle cx="11.5" cy="17.5" r="3.5" className="mark-eye" />
      <circle cx="20.5" cy="17.5" r="3.5" className="mark-eye" />
    </svg>
  );
}
