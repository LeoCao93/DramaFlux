type Props = {
  label: string;
  className?: string;
};

export default function OrbitGraphic({ label, className = "" }: Props) {
  return (
    <svg
      aria-label={label}
      className={`orbit-graphic ${className}`.trim()}
      role="img"
      viewBox="0 0 520 250"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <radialGradient id="orbit-glow">
          <stop stopColor="#723cff" stopOpacity=".8" />
          <stop offset="1" stopColor="#3018b5" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="orbit-line" x1="0" x2="1">
          <stop stopColor="#246dff" stopOpacity=".1" />
          <stop offset=".55" stopColor="#8954ff" />
          <stop offset="1" stopColor="#24d7ff" stopOpacity=".25" />
        </linearGradient>
      </defs>
      <ellipse cx="278" cy="132" rx="178" ry="72" fill="url(#orbit-glow)" opacity=".35" />
      <g fill="none" stroke="url(#orbit-line)">
        <ellipse cx="278" cy="132" rx="202" ry="48" transform="rotate(-9 278 132)" />
        <ellipse cx="278" cy="132" rx="154" ry="72" transform="rotate(12 278 132)" />
        <ellipse cx="278" cy="132" rx="118" ry="91" transform="rotate(58 278 132)" opacity=".65" />
      </g>
      <circle cx="106" cy="113" r="4" fill="#477dff" />
      <circle cx="416" cy="77" r="5" fill="#9b67ff" />
      <circle cx="454" cy="151" r="4" fill="#35d6ff" />
      <g transform="translate(238 92)">
        <path d="M40 0 78 22v44L40 88 2 66V22L40 0Z" fill="#4c36ff" opacity=".45" />
        <path d="M40 8 70 26v36L40 80 10 62V26L40 8Z" fill="#267dff" stroke="#77d5ff" strokeWidth="2" />
        <path d="m40 23 17 10v20L40 63 23 53V33l17-10Z" fill="#0c1a50" stroke="#835cff" strokeWidth="2" />
        <path d="m40 31 10 6v12l-10 6-10-6V37l10-6Z" fill="#385cff" />
      </g>
    </svg>
  );
}
