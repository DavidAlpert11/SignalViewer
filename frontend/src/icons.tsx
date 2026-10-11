import type { SVGProps } from "react";

const base = { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.7, strokeLinecap: "round", strokeLinejoin: "round" } as const;
type P = SVGProps<SVGSVGElement>;
const mk = (d: React.ReactNode) => (p: P) => <svg {...base} aria-hidden="true" {...p}>{d}</svg>;

export const Icon = {
  Replace: (p: P) => <svg {...base} {...p}><path d="M3 7h13l-3-3M21 17H8l3 3" /></svg>,
  Data: mk(<><ellipse cx="12" cy="5" rx="7" ry="2.5" /><path d="M5 5v14c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V5" /><path d="M5 12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5" /></>),
  Analysis: mk(<><path d="M4 19h16" /><path d="M5 15l4-6 4 4 6-8" /></>),
  Compare: mk(<><path d="M3 16c3-8 6-8 9 0s6 8 9 0" /><path d="M3 12c3-6 6-6 9 0s6 6 9 0" opacity=".5" /></>),
  Report: mk(<><path d="M7 3h7l5 5v13H7z" /><path d="M14 3v5h5" /><path d="M10 13h6M10 17h6" /></>),
  Log: mk(<><path d="M5 4v16" /><path d="M5 5h11l-2 3 2 3H5" /><path d="M9 15h10M9 19h7" /></>),
  Folder: mk(<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />),
  File: mk(<><path d="M7 3h7l5 5v13H7z" /><path d="M14 3v5h5" /></>),
  Plus: mk(<path d="M12 5v14M5 12h14" />),
  X: mk(<path d="M6 6l12 12M18 6L6 18" />),
  Search: mk(<><circle cx="11" cy="11" r="6" /><path d="M20 20l-4.3-4.3" /></>),
  Chevron: mk(<path d="M6 9l6 6 6-6" />),
  Cursor: mk(<><path d="M12 3v18" /><path d="M9 3h6" /></>),
  Dual: mk(<><path d="M8 3v18M16 3v18" /><path d="M8 12h8" strokeDasharray="2 2" /></>),
  Undo: mk(<><path d="M9 14L4 9l5-5" /><path d="M4 9h10a6 6 0 0 1 0 12h-3" /></>),
  Redo: mk(<><path d="M15 14l5-5-5-5" /><path d="M20 9H10a6 6 0 0 0 0 12h3" /></>),
  Sun: mk(<><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>),
  Moon: mk(<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z" />),
  Globe: mk(<><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18" /></>),
  Live: mk(<><circle cx="12" cy="12" r="2.5" /><path d="M7.5 7.5a6.4 6.4 0 0 0 0 9M16.5 7.5a6.4 6.4 0 0 1 0 9" /></>),
  Link: mk(<><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" /><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" /></>),
  Reset: mk(<><path d="M4 12a8 8 0 1 0 2.3-5.6L4 8.7" /><path d="M4 4v4.7h4.7" /></>),
  Reload: mk(<><path d="M20 12a8 8 0 1 1-2.3-5.6L20 8.7" /><path d="M20 4v4.7h-4.7" /></>),
  Trash: mk(<><path d="M4 7h16M10 11v6M14 11v6" /><path d="M6 7l1 13h10l1-13M9 7V4h6v3" /></>),
  Edit: mk(<><path d="M4 20h4L19 9l-4-4L4 16z" /></>),
  Layout: mk(<><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M12 4v16M3 12h18" /></>),
  Inspector: mk(<><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M15 4v16" /></>),
  Copy: mk(<><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3" /></>),
  Up: mk(<path d="M12 19V5M5 12l7-7 7 7" />),
  Home: mk(<path d="M4 11l8-7 8 7v9H4z" />),
  More: mk(<><circle cx="5" cy="12" r="1.3" /><circle cx="12" cy="12" r="1.3" /><circle cx="19" cy="12" r="1.3" /></>),
  Save: mk(<><path d="M5 3h11l3 3v15H5z" /><path d="M8 3v6h8V3M8 21v-7h8v7" /></>),
  Open: mk(<><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v1" /><path d="M3 7v11a2 2 0 0 0 2 2h13l3-9H7l-3 9" /></>),
  Image: mk(<><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="9" cy="10" r="1.6" /><path d="M21 16l-5-5-9 9" /></>),
  Table: mk(<><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 10h18M3 15h18M9 4v16" /></>),
  Keyboard: mk(<><rect x="2" y="6" width="20" height="12" rx="2" /><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10" /></>),
};

export function BrandMark(p: P) {
  return (
    <svg viewBox="0 0 24 24" className="brand-mark" aria-hidden="true" {...p}>
      <rect x="1" y="1" width="22" height="22" rx="6" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M4 15c2.5 0 3-7 5.5-7s2.5 9 5 9 2.5-5 5.5-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M14.5 4v16" stroke="var(--amber)" strokeWidth="1.6" />
    </svg>
  );
}
