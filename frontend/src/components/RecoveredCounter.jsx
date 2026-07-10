import React from "react";
import { formatINR } from "@/lib/format";
import { TrendUp } from "@phosphor-icons/react";

export default function RecoveredCounter({ summary }) {
  if (!summary) return null;
  return (
    <div
      data-testid="recovered-counter-widget"
      className="bg-ink text-parchment p-6 flex flex-col justify-between min-h-[280px] border border-ink"
    >
      <div>
        <div className="flex items-center gap-2 font-mono-data text-xs uppercase tracking-widest text-parchment/60">
          <TrendUp size={14} weight="bold" />
          Recovered · Last 7 days
        </div>
      </div>
      <div>
        <div
          data-testid="recovered-amount"
          className="font-serif-display text-6xl lg:text-7xl leading-none text-parchment"
        >
          {formatINR(summary.recovered_this_week)}
        </div>
        <div className="mt-3 flex items-center gap-6 pt-4 border-t border-parchment/15">
          <div>
            <div className="font-mono-data text-[10px] uppercase tracking-widest text-parchment/50">
              All-time recovered
            </div>
            <div className="font-mono-data text-sm mt-0.5">
              {formatINR(summary.recovered_all_time)}
            </div>
          </div>
          <div>
            <div className="font-mono-data text-[10px] uppercase tracking-widest text-parchment/50">
              DSO
            </div>
            <div className="font-mono-data text-sm mt-0.5">
              {summary.dso_days} days
            </div>
          </div>
          <div>
            <div className="font-mono-data text-[10px] uppercase tracking-widest text-parchment/50">
              Outstanding
            </div>
            <div className="font-mono-data text-sm mt-0.5">
              {formatINR(summary.total_outstanding)}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
