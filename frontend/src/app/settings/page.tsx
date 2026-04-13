"use client";

import { useState, useEffect }  from "react";
import { CheckCircle2, Save, Loader2, Eye, EyeOff, Activity } from "lucide-react";
import toast                     from "react-hot-toast";
import { api }                   from "@/lib/api";
import { useAuthStore }          from "@/hooks/useAuthStore";

interface ServiceStatus {
  name:   string;
  status: "ok" | "degraded" | "down" | "checking";
}

export default function SettingsPage() {
  const { username, tenantId, logout } = useAuthStore();
  const [health,     setHealth]    = useState<Record<string, string>>({});
  const [checking,   setChecking]  = useState(false);
  const [showToken,  setShowToken] = useState(false);
  const token = typeof window !== "undefined" ? localStorage.getItem("hai_token") ?? "" : "";

  const checkHealth = async () => {
    setChecking(true);
    try {
      const data = await api.health();
      setHealth(data.details ?? {});
    } catch {
      toast.error("Could not reach API Gateway");
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => { checkHealth(); }, []);

  const SERVICES = [
    "ingestion",
    "rag",
    "analytics",
    "knowledge",
    "agent",
    "llm",
    "session",
  ];

  return (
    <div className="p-8 max-w-3xl space-y-8 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-display font-semibold text-slate-100">Settings</h1>
        <p className="text-slate-400 text-sm mt-1">Platform configuration and diagnostics</p>
      </div>

      {/* Session */}
      <section className="card p-5 space-y-4">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
          Active Session
        </h2>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Username"  value={username  ?? "—"} />
          <Field label="Tenant ID" value={tenantId  ?? "—"} />
        </div>

        <div>
          <p className="text-xs text-slate-500 mb-1.5">JWT Token</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 input font-mono text-xs truncate">
              {showToken ? token : token.slice(0, 20) + "…"}
            </code>
            <button
              onClick={() => setShowToken((v) => !v)}
              className="btn-ghost p-2"
              title="Toggle token visibility"
            >
              {showToken ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>
        </div>

        <button
          onClick={() => { logout(); window.location.href = "/"; }}
          className="text-sm text-rose-400 hover:text-rose-300 transition-colors"
        >
          Sign out
        </button>
      </section>

      {/* Service health */}
      <section className="card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
            Service Health
          </h2>
          <button
            onClick={checkHealth}
            disabled={checking}
            className="btn-ghost text-xs flex items-center gap-1.5"
          >
            {checking
              ? <Loader2 size={12} className="animate-spin" />
              : <Activity size={12} />}
            {checking ? "Checking…" : "Refresh"}
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2">
          {SERVICES.map((svc) => {
            const status = health[svc];
            return (
              <div
                key={svc}
                className="flex items-center gap-2.5 bg-surface-800 rounded-lg px-3 py-2.5"
              >
                <StatusDot status={status} />
                <span className="text-sm text-slate-300 capitalize">{svc}</span>
                <span className={`ml-auto text-xs font-mono ${
                  status === "ok"       ? "text-emerald-400" :
                  status === "degraded" ? "text-amber-400"   :
                  status === "down"     ? "text-rose-400"    :
                                          "text-slate-500"
                }`}>
                  {status ?? (checking ? "…" : "—")}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      {/* Platform info */}
      <section className="card p-5 space-y-3">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
          Platform Info
        </h2>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Version"       value="1.0.0" />
          <Field label="Environment"   value={process.env.NODE_ENV ?? "development"} />
          <Field label="API Gateway"   value={process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"} />
          <Field label="Architecture"  value="Microservices + Event-driven" />
          <Field label="Vector DB"     value="Qdrant" />
          <Field label="Message Queue" value="Kafka" />
        </div>
      </section>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface-800 rounded-lg px-3 py-2.5">
      <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-0.5">{label}</p>
      <p className="text-sm text-slate-300 font-mono truncate">{value}</p>
    </div>
  );
}

function StatusDot({ status }: { status: string | undefined }) {
  const cls =
    status === "ok"       ? "bg-emerald-500" :
    status === "degraded" ? "bg-amber-400 animate-pulse" :
    status === "down"     ? "bg-rose-500" :
                            "bg-slate-600";
  return <span className={`w-2 h-2 rounded-full shrink-0 ${cls}`} />;
}
