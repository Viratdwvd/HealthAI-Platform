"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity, Bot, BarChart3, Upload, Settings,
  HeartPulse, LogOut, ChevronRight
} from "lucide-react";
import clsx from "clsx";
import { useAuthStore } from "@/hooks/useAuthStore";

const NAV = [
  { href: "/",         label: "Dashboard",  icon: Activity },
  { href: "/chat",     label: "AI Query",   icon: Bot },
  { href: "/upload",   label: "Ingest Data",icon: Upload },
  { href: "/analytics",label: "Analytics",  icon: BarChart3 },
];

export function Sidebar() {
  const path    = usePathname();
  const { user, logout } = useAuthStore();

  return (
    <aside className="w-60 shrink-0 bg-surface-900 border-r border-surface-800 flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-surface-800">
        <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
          <HeartPulse size={16} className="text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-100 leading-none">HealthAI</p>
          <p className="text-[10px] text-slate-500 mt-0.5">Platform v1.0</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = path === href || (href !== "/" && path.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group",
                active
                  ? "bg-brand-600/15 text-brand-400"
                  : "text-slate-400 hover:text-slate-100 hover:bg-surface-800"
              )}
            >
              <Icon size={16} />
              <span className="flex-1">{label}</span>
              {active && <ChevronRight size={12} className="text-brand-400" />}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-surface-800 px-3 py-3 space-y-0.5">
        <Link href="/settings" className="btn-ghost flex items-center gap-3 text-sm w-full">
          <Settings size={15} />
          Settings
        </Link>
        <button
          onClick={logout}
          className="btn-ghost flex items-center gap-3 text-sm w-full text-left"
        >
          <LogOut size={15} />
          Sign out
        </button>
        {user && (
          <div className="flex items-center gap-2 px-3 py-2 mt-1">
            <div className="w-7 h-7 rounded-full bg-brand-700 flex items-center justify-center text-xs font-semibold text-brand-200">
              {user.username[0].toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium text-slate-300 truncate">{user.username}</p>
              <p className="text-[10px] text-slate-500 truncate">{user.tenant_id}</p>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
