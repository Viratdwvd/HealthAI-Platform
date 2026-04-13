"use client";

import { Suspense } from "react";
import { ChatInterface } from "@/components/chat/ChatInterface";

export default function ChatPage() {
  return (
    <Suspense fallback={<div className="flex-1 flex items-center justify-center text-slate-500">Loading…</div>}>
      <ChatInterface />
    </Suspense>
  );
}
