// Icon paths carried over from the approved A/Desk prototype.
const iconPaths = {
  overview: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  transactions: "M4 6h16 M4 12h16 M4 18h16 M8 3v18",
  inbox: "M4 4h16l2 11v5H2v-5z M2 15h6l2 3h4l2-3h6",
  recurring: "M20 8a8 8 0 0 0-14-3L3 8 M3 3v5h5 M4 16a8 8 0 0 0 14 3l3-3 M16 16h5v5",
  plus: "M12 5v14 M5 12h14",
  arrow: "M5 12h14 M14 7l5 5-5 5",
  settings: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2",
  lock: "M7 10V7a5 5 0 0 1 10 0v3 M5 10h14v11H5z M12 14v3",
  upload: "M12 16V4 M7 9l5-5 5 5 M4 20h16",
  close: "M6 6l12 12 M18 6L6 18",
  bank: "M3 10h18 M5 10v8 M9 10v8 M15 10v8 M19 10v8 M3 21h18 M12 3l9 5H3z",
} as const;

export type IconName = keyof typeof iconPaths;

export function Icon({ name }: { name: IconName }) {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d={iconPaths[name]} />
    </svg>
  );
}
