export default function BrandLogo() {
  return (
    <svg
      aria-hidden="true"
      className="brand-logo"
      data-testid="brand-logo"
      viewBox="0 0 64 64"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id="brand-a" x1="8" y1="8" x2="56" y2="56">
          <stop stopColor="#34d8ff" />
          <stop offset="1" stopColor="#7447ff" />
        </linearGradient>
        <linearGradient id="brand-b" x1="50" y1="8" x2="20" y2="58">
          <stop stopColor="#7751ff" />
          <stop offset="1" stopColor="#1b7cff" />
        </linearGradient>
      </defs>
      <path d="M32 3 57 17v30L32 61 7 47V17L32 3Z" fill="url(#brand-a)" />
      <path d="m32 12 17 10v20L32 52 15 42V22l17-10Z" fill="#07152f" />
      <path d="m32 12 17 10-17 10-17-10 17-10Z" fill="url(#brand-b)" />
      <path d="m15 22 17 10v20L15 42V22Z" fill="#2caeff" />
      <path d="m49 22-17 10v20l17-10V22Z" fill="#5439f5" />
      <path d="m32 23 8 5v9l-8 5-8-5v-9l8-5Z" fill="#07152f" />
    </svg>
  );
}
