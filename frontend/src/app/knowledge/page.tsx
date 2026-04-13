"use client";

import { useState }  from "react";
import { BookOpen, Search, ChevronDown, ChevronRight, Tag, AlertTriangle, Loader2 } from "lucide-react";
import toast          from "react-hot-toast";
import clsx           from "clsx";
import { api }        from "@/lib/api";

interface RuleMatch {
  id:             string;
  domain:         string;
  keywords?:      string[];
  facts:          string[];
  recommendation?: string;
  severity?:      string;
  source?:        string;
}

interface KnowledgeResult {
  rules:   RuleMatch[];
  facts:   string[];
  sources: string[];
}

const DOMAINS = ["", "cardiology", "diabetes", "hypertension", "oncology", "medication"];

const SEVERITY_CLS: Record<string, string> = {
  high:   "badge-red",
  medium: "badge-yellow",
  low:    "badge-green",
};

export default function KnowledgePage() {
  const [query,   setQuery]   = useState("");
  const [domain,  setDomain]  = useState("");
  const [result,  setResult]  = useState<KnowledgeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const search = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      // Call the knowledge service via the analytics endpoint proxy
      // (In a full build, you'd add a /api/v1/knowledge endpoint to the gateway)
      const resp = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/v1/knowledge`,
        {
          method:  "POST",
          headers: {
            "Content-Type":  "application/json",
            Authorization: `Bearer ${localStorage.getItem("hai_token") ?? ""}`,
          },
          body: JSON.stringify({
            query,
            tenant_id: "tenant-demo",
            domains:   domain ? [domain] : [],
          }),
        }
      );
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data: KnowledgeResult = await resp.json();
      setResult(data);
    } catch (err: any) {
      toast.error(err?.message ?? "Knowledge lookup failed");
    } finally {
      setLoading(false);
    }
  };

  const toggle = (id: string) =>
    setExpanded((s) => {
      const next = new Set(s);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  return (
    <div className="p-8 max-w-4xl space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-display font-semibold text-slate-100">
            Clinical Knowledge Base
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Query domain rules and clinical guidelines by keyword or free text.
          </p>
        </div>
        <div className="p-2.5 rounded-xl bg-violet-500/10">
          <BookOpen className="w-5 h-5 text-violet-400" />
        </div>
      </div>

      {/* Search bar */}
      <div className="card p-4 space-y-3">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input
              className="input pl-9"
              placeholder="e.g. chest pain, HbA1c, blood pressure…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && search()}
            />
          </div>

          {/* Domain filter */}
          <select
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            className="input w-44 bg-surface-800"
          >
            {DOMAINS.map((d) => (
              <option key={d} value={d}>{d || "All domains"}</option>
            ))}
          </select>

          <button
            onClick={search}
            disabled={loading || !query.trim()}
            className="btn-primary flex items-center gap-2 shrink-0"
          >
            {loading
              ? <Loader2 size={14} className="animate-spin" />
              : <Search size={14} />}
            {loading ? "Searching…" : "Search"}
          </button>
        </div>

        {/* Quick chips */}
        <div className="flex flex-wrap gap-2">
          {["chest pain", "hypertension", "HbA1c > 7", "drug interaction", "arrhythmia"].map((ex) => (
            <button
              key={ex}
              onClick={() => { setQuery(ex); }}
              className="text-xs px-2.5 py-1 rounded-full bg-surface-800 text-slate-400 hover:text-slate-200 hover:bg-surface-700 transition-colors"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-4 animate-slide-up">
          {/* Summary bar */}
          <div className="flex items-center gap-4 text-sm">
            <span className="text-slate-400">
              <span className="text-slate-100 font-semibold">{result.rules.length}</span> rule
              {result.rules.length !== 1 ? "s" : ""} matched
            </span>
            {result.sources.length > 0 && (
              <span className="text-slate-500">
                Sources: {result.sources.join(", ")}
              </span>
            )}
          </div>

          {/* Consolidated facts */}
          {result.facts.length > 0 && (
            <div className="card p-4 border-brand-700/30 bg-brand-950/30">
              <p className="text-xs font-semibold text-brand-400 uppercase tracking-wider mb-2">
                Key Clinical Facts
              </p>
              <ul className="space-y-1.5">
                {result.facts.map((f, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-300">
                    <span className="text-brand-500 mt-0.5 shrink-0">•</span>
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Rule cards */}
          {result.rules.length === 0 && (
            <div className="card p-8 text-center text-slate-500">
              <BookOpen size={32} className="mx-auto mb-3 opacity-30" />
              <p>No rules matched your query.</p>
              <p className="text-xs mt-1">Try different keywords or remove the domain filter.</p>
            </div>
          )}

          {result.rules.map((rule) => {
            const open = expanded.has(rule.id);
            return (
              <div key={rule.id} className="card overflow-hidden">
                {/* Rule header */}
                <button
                  onClick={() => toggle(rule.id)}
                  className="w-full flex items-center gap-3 px-5 py-3.5 hover:bg-surface-800 transition-colors text-left"
                >
                  {open
                    ? <ChevronDown size={14} className="text-slate-400 shrink-0" />
                    : <ChevronRight size={14} className="text-slate-400 shrink-0" />}

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-slate-200 font-mono">{rule.id}</span>
                      <span className="badge badge-blue text-[10px]">{rule.domain}</span>
                      {rule.severity && (
                        <span className={clsx("badge text-[10px]", SEVERITY_CLS[rule.severity] ?? "badge-blue")}>
                          {rule.severity}
                        </span>
                      )}
                    </div>
                    {!open && rule.facts[0] && (
                      <p className="text-xs text-slate-500 mt-0.5 truncate">{rule.facts[0]}</p>
                    )}
                  </div>

                  {rule.source && (
                    <span className="text-xs text-slate-500 shrink-0 hidden sm:block">{rule.source}</span>
                  )}
                </button>

                {/* Expanded body */}
                {open && (
                  <div className="px-5 pb-5 space-y-4 border-t border-surface-800 pt-4 animate-fade-in">

                    {/* Keywords */}
                    {rule.keywords && rule.keywords.length > 0 && (
                      <div>
                        <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                          <Tag size={10} /> Keywords
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {rule.keywords.map((kw) => (
                            <span key={kw} className="text-xs px-2 py-0.5 rounded-full bg-surface-700 text-slate-300">
                              {kw}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Facts */}
                    <div>
                      <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1.5">Clinical Facts</p>
                      <ul className="space-y-1">
                        {rule.facts.map((f, i) => (
                          <li key={i} className="text-sm text-slate-300 flex gap-2">
                            <span className="text-emerald-500 shrink-0 mt-0.5">✓</span> {f}
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Recommendation */}
                    {rule.recommendation && (
                      <div className="flex gap-2.5 p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
                        <AlertTriangle size={14} className="text-amber-400 shrink-0 mt-0.5" />
                        <div>
                          <p className="text-[10px] text-amber-500 uppercase tracking-wider mb-0.5">Recommendation</p>
                          <p className="text-sm text-slate-300">{rule.recommendation}</p>
                        </div>
                      </div>
                    )}

                    {/* Source */}
                    {rule.source && (
                      <p className="text-xs text-slate-500">
                        Source: <span className="text-slate-400">{rule.source}</span>
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
