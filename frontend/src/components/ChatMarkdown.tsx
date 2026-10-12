import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

const components: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0 leading-snug">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => <ul className="list-disc list-outside pl-4 mb-2 space-y-0.5">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal list-outside pl-4 mb-2 space-y-0.5">{children}</ol>,
  li: ({ children }) => <li className="leading-snug">{children}</li>,
  h1: ({ children }) => <h1 className="text-sm font-semibold mt-2 mb-1">{children}</h1>,
  h2: ({ children }) => <h2 className="text-sm font-semibold mt-2 mb-1">{children}</h2>,
  h3: ({ children }) => <h3 className="text-xs font-semibold uppercase tracking-wide mt-2 mb-1" style={{ color: "var(--dsa-muted)" }}>{children}</h3>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="underline" style={{ color: "var(--dsa-accent)" }}>
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 pl-2 my-1.5 italic" style={{ borderColor: "var(--dsa-accent)", color: "var(--dsa-muted)" }}>
      {children}
    </blockquote>
  ),
  code: ({ children, className }) => {
    const isBlock = /language-/.test(className || "");
    if (isBlock) {
      return (
        <pre
          className="rounded-md p-2 my-1.5 overflow-x-auto text-[11px]"
          style={{ background: "var(--dsa-bg)", border: "1px solid var(--dsa-border)" }}
        >
          <code>{children}</code>
        </pre>
      );
    }
    return (
      <code className="rounded px-1 py-0.5 text-[11px]" style={{ background: "var(--dsa-bg)" }}>
        {children}
      </code>
    );
  },
  table: ({ children }) => (
    <div className="overflow-x-auto my-1.5">
      <table className="text-xs border-collapse w-full">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead>{children}</thead>,
  th: ({ children }) => (
    <th className="border px-1.5 py-1 text-left font-medium" style={{ borderColor: "var(--dsa-border)" }}>
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border px-1.5 py-1 align-top" style={{ borderColor: "var(--dsa-border)" }}>
      {children}
    </td>
  ),
  hr: () => <hr className="my-2" style={{ borderColor: "var(--dsa-border)" }} />,
};

export default function ChatMarkdown({ content }: { content: string }) {
  return (
    <div className="text-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
