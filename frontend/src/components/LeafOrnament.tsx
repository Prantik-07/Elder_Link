export function LeafOrnament({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 120 160"
      fill="none"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M60 150C60 150 30 120 30 80C30 45 55 15 60 10C65 15 90 45 90 80C90 120 60 150 60 150Z"
        stroke="var(--color-teal)"
        strokeOpacity="0.35"
        strokeWidth="1.5"
      />
      <path d="M60 20V148" stroke="var(--color-teal)" strokeOpacity="0.3" strokeWidth="1.25" />
      <path d="M60 45C60 45 45 55 40 65" stroke="var(--color-teal)" strokeOpacity="0.28" strokeWidth="1.1" />
      <path d="M60 45C60 45 75 55 80 65" stroke="var(--color-teal)" strokeOpacity="0.28" strokeWidth="1.1" />
      <path d="M60 80C60 80 42 92 36 105" stroke="var(--color-teal)" strokeOpacity="0.28" strokeWidth="1.1" />
      <path d="M60 80C60 80 78 92 84 105" stroke="var(--color-teal)" strokeOpacity="0.28" strokeWidth="1.1" />
      <path d="M60 112C60 112 47 122 43 132" stroke="var(--color-teal)" strokeOpacity="0.28" strokeWidth="1.1" />
      <path d="M60 112C60 112 73 122 77 132" stroke="var(--color-teal)" strokeOpacity="0.28" strokeWidth="1.1" />
    </svg>
  );
}
