import type { ReactNode } from "react";

type CodeBlockProps = {
  children: ReactNode;
  language?: string;
  label?: string;
};

export default function CodeBlock({
  children,
  language = "text",
  label = "代码示例",
}: CodeBlockProps) {
  return (
    <pre className="code-block" aria-label={label} tabIndex={0}>
      <code className={`language-${language}`}>{children}</code>
    </pre>
  );
}
