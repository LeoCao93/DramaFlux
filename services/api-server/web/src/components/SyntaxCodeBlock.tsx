type Props = {
  lines: string[];
  label: string;
  compact?: boolean;
};

type Token = {
  value: string;
  className?: string;
};

const TOKEN_PATTERN =
  /("(?:[^"\\]|\\.)*"|https?:\/\/\S+|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b|true|false|null)/g;

function tokenize(line: string): Token[] {
  const tokens: Token[] = [];
  let lastIndex = 0;

  for (const match of line.matchAll(TOKEN_PATTERN)) {
    const index = match.index ?? 0;
    if (index > lastIndex) {
      tokens.push({ value: line.slice(lastIndex, index) });
    }

    const value = match[0];
    let className = "syntax-value";
    if (value.startsWith("http")) {
      className = "syntax-url";
    } else if (value.startsWith('"')) {
      className = line.slice(index + value.length).trimStart().startsWith(":")
        ? "syntax-key"
        : "syntax-string";
    } else if (/^(true|false|null)$/.test(value)) {
      className = "syntax-value";
    }

    tokens.push({ value, className });
    lastIndex = index + value.length;
  }

  if (lastIndex < line.length) {
    tokens.push({ value: line.slice(lastIndex) });
  }

  return tokens;
}

export default function SyntaxCodeBlock({
  lines,
  label,
  compact = false,
}: Props) {
  return (
    <div
      aria-label={label}
      className={`syntax-code${compact ? " is-compact" : ""}`}
      role="region"
    >
      {lines.map((line, index) => (
        <div className="syntax-line" key={`${line}-${index}`}>
          <span className="line-number">{index + 1}</span>
          <code>
            {tokenize(line).map((token, tokenIndex) => (
              <span className={token.className} key={`${token.value}-${tokenIndex}`}>
                {token.value}
              </span>
            ))}
          </code>
        </div>
      ))}
    </div>
  );
}
