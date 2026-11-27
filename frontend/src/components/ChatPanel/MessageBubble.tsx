import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Terminal, User as UserIcon } from 'lucide-react';
import { ChatMessage } from '../../types';

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isAssistant = message.role === 'assistant';
  const isWarningOrError = isAssistant && (message.content.includes('⚠️') || message.content.toLowerCase().includes('pitwall error'));

  return (
    <div
      className={`flex flex-col space-y-1.5 ${
        isAssistant ? 'items-start' : 'items-end'
      }`}
    >
      {/* Header bar: role icon, label, and timestamp */}
      <div className="flex items-center space-x-1.5 text-[11px] font-mono text-[#94A3B8]">
        {isAssistant ? (
          <>
            <Terminal className={`h-3 w-3 ${isWarningOrError ? 'text-amber-400' : 'text-[#E10600]'}`} />
            <span className={`font-semibold ${isWarningOrError ? 'text-amber-400' : 'text-[#E10600]'}`}>
              {isWarningOrError ? 'PITWALL WARNING / NOTICE' : 'PITWALL ENGINEER'}
            </span>
          </>
        ) : (
          <>
            <UserIcon className="h-3 w-3 text-[#38BDF8]" />
            <span className="font-semibold text-[#38BDF8]">YOU</span>
          </>
        )}
        <span>•</span>
        <span>{message.timestamp}</span>
      </div>

      {/* Message content bubble */}
      <div
        className={`max-w-[92%] rounded-lg px-4 py-3 text-sm leading-relaxed ${
          isAssistant
            ? isWarningOrError
              ? 'border border-amber-500/40 bg-[#161214] text-[#FDE68A] shadow-md'
              : 'border border-[#1E293B] bg-[#121824] text-[#E2E8F0] shadow-sm'
            : 'border border-[#38BDF8]/20 bg-[#1E293B] text-white'
        }`}
      >
        {isAssistant ? (
          <div className="markdown-container">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children }) => (
                  <p className="mb-2 last:mb-0 leading-relaxed font-sans">{children}</p>
                ),
                strong: ({ children }) => (
                  <strong className="font-bold text-[#F8FAFC]">{children}</strong>
                ),
                em: ({ children }) => (
                  <em className="italic text-[#E2E8F0]">{children}</em>
                ),
                ul: ({ children }) => (
                  <ul className="my-1.5 ml-4 list-disc space-y-0.5 text-xs text-[#E2E8F0]">
                    {children}
                  </ul>
                ),
                ol: ({ children }) => (
                  <ol className="my-1.5 ml-4 list-decimal space-y-0.5 text-xs text-[#E2E8F0]">
                    {children}
                  </ol>
                ),
                li: ({ children }) => (
                  <li className="leading-relaxed">{children}</li>
                ),
                code: ({ className, children, ...props }: any) => {
                  const isMultiLine = String(children).includes('\n');
                  if (!isMultiLine && !className) {
                    return (
                      <code
                        className="rounded border border-[#1E293B] bg-[#0B0F17] px-1.5 py-0.5 font-mono text-[11px] text-[#38BDF8]"
                        {...props}
                      >
                        {children}
                      </code>
                    );
                  }
                  return (
                    <pre className="my-2 overflow-x-auto rounded border border-[#1E293B] bg-[#0B0F17] p-2.5 font-mono text-xs text-[#38BDF8]">
                      <code {...props}>{children}</code>
                    </pre>
                  );
                },
                table: ({ children }) => (
                  <div className="my-2 overflow-x-auto rounded border border-[#1E293B]">
                    <table className="min-w-full divide-y divide-[#1E293B] text-xs font-mono">
                      {children}
                    </table>
                  </div>
                ),
                thead: ({ children }) => (
                  <thead className="bg-[#1E293B]/60 text-[#94A3B8]">
                    {children}
                  </thead>
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
                  <td className="px-3 py-1.5 text-[#E2E8F0]">
                    {children}
                  </td>
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
                  <blockquote className="border-l-2 border-[#E10600] pl-3 italic text-[#94A3B8] my-1.5 text-xs">
                    {children}
                  </blockquote>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
            {message.isStreaming && (
              <span
                className="inline-block w-1.5 h-3.5 ml-1 bg-[#E10600] animate-pulse align-middle"
                title="Race engineer streaming..."
              />
            )}
          </div>
        ) : (
          <p className="whitespace-pre-wrap font-sans">{message.content}</p>
        )}
      </div>
    </div>
  );
}
