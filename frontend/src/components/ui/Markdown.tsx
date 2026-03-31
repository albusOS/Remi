"use client";

import { useState, useCallback, type ComponentProps } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [text]);

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 px-2 py-0.5 rounded-md text-[10px] font-medium bg-border hover:bg-fg-ghost text-fg-muted transition-colors opacity-0 group-hover:opacity-100"
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function CodeBlock({ children, className, ...rest }: ComponentProps<"code"> & { node?: unknown }) {
  const { node: _, ...props } = rest;
  const match = /language-(\w+)/.exec(className || "");
  const isInline = !match && typeof children === "string" && !children.includes("\n");

  if (isInline) {
    return (
      <code className="px-1.5 py-0.5 rounded-md bg-code-inline-bg text-code-inline-fg text-[13px] font-mono" {...props}>
        {children}
      </code>
    );
  }

  const codeText = String(children).replace(/\n$/, "");

  return (
    <div className="group relative rounded-xl overflow-hidden my-3 bg-code-bg border border-code-border">
      {match && (
        <div className="flex items-center px-3 py-1.5 border-b border-code-border bg-surface-sunken">
          <span className="text-[10px] text-fg-faint font-mono">{match[1]}</span>
        </div>
      )}
      <CopyButton text={codeText} />
      <pre className="overflow-x-auto p-3 text-[13px] leading-relaxed">
        <code className={`font-mono text-code-fg ${className || ""}`} {...props}>
          {children}
        </code>
      </pre>
    </div>
  );
}

export function Markdown({ content, className }: { content: string; className?: string }) {
  return (
    <div className={`prose-remi ${className || ""}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code: CodeBlock,
          p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>,
          h1: ({ children }) => <h1 className="text-lg font-bold text-fg mt-5 mb-2 first:mt-0">{children}</h1>,
          h2: ({ children }) => <h2 className="text-base font-semibold text-fg mt-4 mb-2 first:mt-0">{children}</h2>,
          h3: ({ children }) => <h3 className="text-sm font-semibold text-fg-secondary mt-3 mb-1.5 first:mt-0">{children}</h3>,
          ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="text-fg-secondary leading-relaxed">{children}</li>,
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-fg underline underline-offset-2 decoration-fg-ghost hover:decoration-fg-faint">
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-border pl-3 my-3 text-fg-muted italic">{children}</blockquote>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto my-3 rounded-xl border border-border">
              <table className="w-full text-sm">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-surface-raised text-fg-muted">{children}</thead>,
          th: ({ children }) => <th className="text-left px-3 py-2 text-[11px] font-semibold uppercase tracking-wider">{children}</th>,
          td: ({ children }) => <td className="px-3 py-2 border-t border-border-subtle text-fg-secondary">{children}</td>,
          hr: () => <hr className="my-4 border-border" />,
          strong: ({ children }) => <strong className="font-semibold text-fg">{children}</strong>,
          em: ({ children }) => <em className="italic text-fg-muted">{children}</em>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
