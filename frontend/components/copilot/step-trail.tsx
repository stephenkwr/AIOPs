"use client";

import { AlertTriangle, Search, ShoppingCart, Wrench } from "lucide-react";

import type { AgentStep } from "@/lib/api/agent";
import { cn } from "@/lib/utils";

const TOOL_META: Record<string, { label: string; icon: React.ComponentType<{ className?: string }> }> = {
  search_knowledge_base: { label: "Searched knowledge base", icon: Search },
  lookup_order: { label: "Looked up order", icon: ShoppingCart },
  create_escalation: { label: "Escalation", icon: AlertTriangle },
};

export function StepTrail({ steps }: { steps: AgentStep[] }) {
  if (steps.length === 0) return null;
  return (
    <div className="mb-2 flex flex-wrap gap-1.5">
      {steps.map((s, i) => {
        const meta = TOOL_META[s.name] ?? { label: s.name, icon: Wrench };
        const Icon = meta.icon;
        return (
          <span
            key={i}
            className={cn(
              "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px]",
              s.status === "error" || s.status === "rejected"
                ? "bg-red-100 text-red-700"
                : "bg-slate-100 text-slate-600",
            )}
          >
            <Icon className="h-3 w-3" />
            {meta.label}
            {s.status === "rejected" && " (declined)"}
          </span>
        );
      })}
    </div>
  );
}
