export type PlatformIconName =
  | "book"
  | "calendar"
  | "calendar-month"
  | "calendar-week"
  | "cart"
  | "code"
  | "crown"
  | "diamond"
  | "document"
  | "key"
  | "layers"
  | "lightning"
  | "search"
  | "shield"
  | "star"
  | "trophy";

type Props = {
  name: PlatformIconName;
  className?: string;
};

const drawings: Record<PlatformIconName, React.ReactNode> = {
  book: (
    <>
      <path d="M6 7.5c3-1 6-.5 9 1.5v18c-3-2-6-2.5-9-1.5z" />
      <path d="M30 7.5c-3-1-6-.5-9 1.5v18c3-2 6-2.5 9-1.5z" />
      <path d="M18 10v18" />
    </>
  ),
  calendar: (
    <>
      <rect x="7" y="8" width="22" height="21" rx="3" />
      <path d="M12 5v6M24 5v6M7 15h22" />
      <path d="M12 20h3M20 20h3M12 25h3M20 25h3" />
    </>
  ),
  "calendar-week": (
    <>
      <rect x="7" y="8" width="22" height="21" rx="3" />
      <path d="M12 5v6M24 5v6M7 15h22" />
      <path d="M10 20h4M16 20h4M22 20h3M10 25h4M16 25h4M22 25h3" />
    </>
  ),
  "calendar-month": (
    <>
      <rect x="7" y="8" width="22" height="21" rx="3" />
      <path d="M12 5v6M24 5v6M7 15h22" />
      <path d="M11 20h4M17 20h4M11 25h4M17 25h4" />
      <path d="M23 20h2M23 25h2" />
    </>
  ),
  cart: (
    <>
      <path d="M5 7h4l3 15h14l4-10H11" />
      <circle cx="15" cy="28" r="2" />
      <circle cx="26" cy="28" r="2" />
    </>
  ),
  code: (
    <>
      <path d="m13 10-7 8 7 8M23 10l7 8-7 8M21 6l-6 24" />
    </>
  ),
  crown: (
    <>
      <path d="m5 12 7 5 6-10 6 10 7-5-3 16H8L5 12Z" />
      <path d="M10 31h16" />
    </>
  ),
  diamond: (
    <>
      <path d="m5 13 6-7h14l6 7-13 18L5 13Z" />
      <path d="m11 6 7 25 7-25M5 13h26" />
    </>
  ),
  document: (
    <>
      <path d="M10 5h12l6 6v20H10z" />
      <path d="M22 5v7h6M14 18h10M14 23h10" />
    </>
  ),
  key: (
    <>
      <circle cx="12" cy="13" r="6" />
      <path d="m16 17 14 14M24 25l4-4M20 21l4-4" />
    </>
  ),
  layers: (
    <>
      <path d="m18 5 14 8-14 8L4 13l14-8Z" />
      <path d="m6 20 12 7 12-7M6 27l12 7 12-7" />
    </>
  ),
  lightning: <path d="M21 3 8 20h10l-3 14 13-18H18l3-13Z" />,
  search: (
    <>
      <circle cx="16" cy="16" r="10" />
      <path d="m24 24 8 8" />
    </>
  ),
  shield: (
    <>
      <path d="m18 4 12 5v8c0 8-5 13-12 17C11 30 6 25 6 17V9l12-5Z" />
      <path d="m13 18 3 3 7-8" />
    </>
  ),
  star: <path d="m18 4 4 9 10 1-7 7 2 10-9-5-9 5 2-10-7-7 10-1 4-9Z" />,
  trophy: (
    <>
      <path d="M11 6h14v7c0 7-4 11-7 11s-7-4-7-11V6Z" />
      <path d="M11 9H6v4c0 4 3 6 7 6M25 9h5v4c0 4-3 6-7 6M18 24v6M12 32h12" />
    </>
  ),
};

export default function PlatformIcon({ name, className = "" }: Props) {
  return (
    <svg
      aria-hidden="true"
      className={`platform-icon ${className}`.trim()}
      data-icon={name}
      data-testid="platform-icon"
      fill="none"
      viewBox="0 0 36 36"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.2"
      >
        {drawings[name]}
      </g>
    </svg>
  );
}
