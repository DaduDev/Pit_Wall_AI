import { Globe, ExternalLink, ShieldCheck, Sparkles, CheckCircle2 } from 'lucide-react';
import { WebIntelligenceCardData } from '../../types';

interface WebIntelligenceCardProps {
  card?: WebIntelligenceCardData | null;
}

export function WebIntelligenceCard({ card }: WebIntelligenceCardProps) {
  if (!card) {
    return null;
  }

  const isGrounded = card.grounded === true;
  const sources = Array.isArray(card.sources) ? card.sources : [];
  const bullets = Array.isArray(card.bullets)
    ? card.bullets
        .flatMap((b) => (typeof b === 'string' ? b.split(/\r?\n/) : []))
        .map((line) => {
          let s = line.replace(/[\u200B\uFEFF]/g, '').trim();
          while (s) {
            const next = s.replace(/^(?:[-•*–—]+|\d+[.)]+)\s*/, '').trim();
            if (next === s) break;
            s = next;
          }
          return s.replace(/\s+/g, ' ').trim();
        })
        .filter((s) => s.length > 0 && !/^[-•*–—.\s]+$/.test(s))
    : [];

  const cleanSummary = typeof card.summary === 'string'
    ? card.summary
        .split(/\r?\n/)
        .filter((line) => !/^\s*[-•*–—]+\s*$/.test(line))
        .join('\n')
        .trim()
    : '';

  return (
    <div className="rounded-lg border border-[#1E293B] bg-[#0E1420] p-6 shadow-xl space-y-6">
      {/* Header with Title and Grounding Badge */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#1E293B] pb-4">
        <div className="flex items-center space-x-3">
          <div className="rounded-md bg-[#1E293B] p-2 text-cyan-400">
            <Globe className="h-5 w-5" />
          </div>
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-cyan-400 block">
              RESEARCH AGENT • WEB INTELLIGENCE
            </span>
            <h2 className="text-lg font-bold text-white tracking-wide">
              {card.title || 'Web Intelligence & Grounded Sources'}
            </h2>
          </div>
        </div>

        {/* Provider Grounding / Fallback Badge */}
        <div className="flex items-center space-x-2">
          {card.provider === 'cache' || (isGrounded && card.provider === 'cache') ? (
            <div className="flex items-center space-x-1.5 rounded-full border border-cyan-500/30 bg-cyan-950/40 px-3 py-1 text-xs font-mono text-cyan-400">
              <Sparkles className="h-3 w-3 text-cyan-400" />
              <span>Cached Search Grounding</span>
            </div>
          ) : isGrounded ? (
            <div className="flex items-center space-x-1.5 rounded-full border border-emerald-500/30 bg-emerald-950/40 px-3 py-1 text-xs font-mono text-emerald-400">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <Sparkles className="h-3 w-3 text-emerald-400" />
              <span>Google Search Grounding</span>
            </div>
          ) : card.provider === 'groq_fallback' ? (
            <div className="flex items-center space-x-1.5 rounded-full border border-sky-500/30 bg-sky-950/40 px-3 py-1 text-xs font-mono text-sky-300">
              <ShieldCheck className="h-3 w-3 text-sky-400" />
              <span>Groq Cloud Fallback — No Live Search</span>
            </div>
          ) : card.provider === 'openrouter_fallback' ? (
            <div className="flex items-center space-x-1.5 rounded-full border border-indigo-500/30 bg-indigo-950/40 px-3 py-1 text-xs font-mono text-indigo-300">
              <ShieldCheck className="h-3 w-3 text-indigo-400" />
              <span>OpenRouter Free Fallback — No Live Search</span>
            </div>
          ) : (
            <div className="flex items-center space-x-1.5 rounded-full border border-amber-500/30 bg-amber-950/40 px-3 py-1 text-xs font-mono text-amber-400">
              <ShieldCheck className="h-3 w-3" />
              <span>Local Ollama Fallback — Offline Model</span>
            </div>
          )}
        </div>
      </div>

      {/* Main Summary Section */}
      <div className="rounded-lg border border-[#1E293B]/70 bg-[#0B0F17] p-4 text-sm leading-relaxed text-[#E2E8F0]">
        <p className="font-sans whitespace-pre-wrap">{cleanSummary}</p>
      </div>

      {/* Key Findings / Bullet Points */}
      {bullets.length > 0 && (
        <div className="space-y-2">
          <h3 className="font-mono text-xs uppercase tracking-wider text-[#94A3B8]">
            Key Takeaways & Regulatory Facts:
          </h3>
          <ul className="grid grid-cols-1 gap-2 list-none pl-0 m-0">
            {bullets.map((bullet, idx) => (
              <li
                key={idx}
                className="flex items-start space-x-2.5 rounded border border-[#1E293B]/50 bg-[#121824] p-3 text-xs text-[#CBD5E1]"
              >
                <CheckCircle2 className="h-4 w-4 text-cyan-400 shrink-0 mt-0.5" />
                <span className="leading-relaxed font-sans inline">{bullet}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Grounded Source Citations */}
      {sources.length > 0 && (
        <div className="space-y-2 pt-2 border-t border-[#1E293B]">
          <div className="flex items-center justify-between">
            <h3 className="font-mono text-xs uppercase tracking-wider text-[#94A3B8]">
              Verified Source Citations ({sources.length}):
            </h3>
            <span className="text-[10px] font-mono text-[#64748B]">
              VERIFIED EXTERNAL LINKS
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {sources.map((src, idx) => {
              const url = src.url || (src as any).uri || '#';
              let hostname = '';
              try {
                hostname = new URL(url).hostname.replace('www.', '');
              } catch {
                hostname = 'formula1.com';
              }

              return (
                <a
                  key={idx}
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between rounded border border-[#1E293B] bg-[#121824] px-3.5 py-2.5 text-xs text-[#94A3B8] hover:border-cyan-500/50 hover:bg-[#1A2234] hover:text-white transition-all group"
                >
                  <div className="flex items-center space-x-2 truncate">
                    <span className="rounded bg-[#1E293B] px-1.5 py-0.5 text-[10px] font-mono text-cyan-400 group-hover:bg-cyan-950/60">
                      {hostname}
                    </span>
                    <span className="truncate font-medium text-white group-hover:text-cyan-300">
                      {src.title || url}
                    </span>
                  </div>
                  <ExternalLink className="h-3.5 w-3.5 shrink-0 text-[#64748B] group-hover:text-cyan-400 transition-colors ml-2" />
                </a>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
