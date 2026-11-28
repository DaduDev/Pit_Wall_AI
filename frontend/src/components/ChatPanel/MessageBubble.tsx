import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Terminal, User as UserIcon } from 'lucide-react';
import { ChatMessage } from '../../types';

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isAssistant = message.role === 'assistant';
  const isWarningOrError =
    isAssistant &&
    (message.content.includes('⚠️') ||
      message.content.toLowerCase().includes('pitwall error'));

  if (!isAssistant) {
    return (
      <div className="flex max-w-2xl flex-col items-end space-y-1">
        <div className="flex items-center space-x-1.5 text-[11px] font-mono text-[#94A3B8]">
          <UserIcon className="h-3 w-3 text-[#38BDF8]" />
          <span className="font-semibold text-[#38BDF8]">YOU</span>
          <span>•</span>
          <span>{message.timestamp}</span>
        </div>
        <div className="rounded-2xl border border-[#38BDF8]/25 bg-[#1E293B] px-4 py-2.5 text-sm leading-relaxed text-white shadow-sm">
          <p className="whitespace-pre-wrap font-sans">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full space-y-1.5">
      {/* Header bar: role icon, label, and timestamp */}
      <div className="flex items-center space-x-1.5 text-[11px] font-mono text-[#94A3B8]">
        <Terminal
          className={`h-3 w-3 ${isWarningOrError ? 'text-amber-400' : 'text-[#E10600]'}`}
        />
        <span
          className={`font-semibold ${
            isWarningOrError ? 'text-amber-400' : 'text-[#E10600]'
          }`}
        >
          {isWarningOrError ? 'PITWALL WARNING / NOTICE' : 'PITWALL ENGINEER'}
        </span>
        <span>•</span>
        <span>{message.timestamp}</span>
      </div>

      {/* Full-width readable Race Engineer prose card */}
      <div
        className={`w-full rounded-xl px-5 py-4 text-sm leading-relaxed ${
          isWarningOrError
            ? 'border border-amber-500/40 bg-[#161214] text-[#FDE68A] shadow-md'
            : 'border border-[#1E293B] bg-[#121824]/90 text-[#E2E8F0] shadow-sm'
        }`}
      >
        <div className="markdown-container">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children }) => (
                <p className="mb-2.5 last:mb-0 leading-relaxed font-sans">{children}</p>
              ),
              strong: ({ children }) => (
                <strong className="font-bold text-[#F8FAFC]">{children}</strong>
              ),
              em: ({ children }) => (
                <em className="italic text-[#E2E8F0]">{children}</em>
              ),
              ul: ({ children }) => (
                <ul className="my-2 ml-5 list-disc space-y-1 text-sm text-[#E2E8F0]">
                  {children}
                </ul>
              ),
              ol: ({ children }) => (
                <ol className="my-2 ml-5 list-decimal space-y-1 text-sm text-[#E2E8F0]">
                  {children}
                </ol>
              ),
              li: ({ children }) => <li className="leading-relaxed">{children}</li>,
              code: ({ className, children, ...props }: any) => {
                const isMultiLine = String(children).includes('\n');
                if (!isMultiLine && !className) {
                  return (
                    <code
                      className="rounded border border-[#1E293B] bg-[#0B0F17] px-1.5 py-0.5 font-mono text-xs text-[#38BDF8]"
                      {...props}
                    >
                      {children}
                    </code>
                  );
                }
                return (
                  <pre className="my-2.5 overflow-x-auto rounded-lg border border-[#1E293B] bg-[#0B0F17] p-3 font-mono text-xs text-[#38BDF8]">
                    <code {...props}>{children}</code>
                  </pre>
                );
              },
              table: ({ children }) => (
                <div className="my-2.5 overflow-x-auto rounded-lg border border-[#1E293B]">
                  <table className="min-w-full divide-y divide-[#1E293B] text-xs font-mono">
                    {children}
                  </table>
                </div>
              ),
              thead: ({ children }) => (
                <thead className="bg-[#1E293B]/60 text-[#94A3B8]">{children}</thead>
              ),
              th: ({ children }) => (
                <th className="px-3 py-1.5 text-left font-semibold text-[#94A3B8]">
                  {children}
                </th>
              ),
              tbody: ({ children }) => (
                <tbody className="divide-y divide-[#1E293B]/40 bg-[#0B0F17]/40">
                  {children}
                </tbody>
              ),
              td: ({ children }) => (
                <td className="px-3 py-1.5 text-[#E2E8F0]">{children}</td>
              ),
              h1: ({ children }) => (
                <h1 className="text-base font-bold text-white mb-2">{children}</h1>
              ),
              h2: ({ children }) => (
                <h2 className="text-sm font-bold text-white mb-1.5">{children}</h2>
              ),
              h3: ({ children }) => (
                <h3 className="text-xs font-bold text-white mb-1">{children}</h3>
              ),
              blockquote: ({ children }) => (
                <blockquote className="border-l-2 border-[#E10600] pl-3 italic text-[#94A3B8] my-2 text-xs">
                  {children}
                </blockquote>
              ),
            }}
          >
            {message.content}
          </ReactMarkdown>
          {message.isStreaming && (
            <span
              className="inline-block w-1.5 h-4 ml-1 bg-[#E10600] animate-pulse align-middle"
              title="Race engineer streaming..."
            />
          )}
        </div>
      </div>
    </div>
  );
}
