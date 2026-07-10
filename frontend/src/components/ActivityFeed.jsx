import React from "react";
import { relativeTime } from "@/lib/format";
import {
  PaperPlaneTilt,
  ChatCircleText,
  Scales,
} from "@phosphor-icons/react";

function RungBadge({ rung }) {
  const label =
    rung === 3
      ? "Rung 3 · Statutory"
      : rung === 2
      ? "Rung 2 · Firm"
      : rung === 1
      ? "Rung 1 · Friendly"
      : "Reply";
  const cls = rung >= 1 && rung <= 3 ? `rung-${rung}` : "rung-0";
  return (
    <span
      className={`font-mono-data text-[10px] uppercase tracking-wider px-2 py-0.5 ${cls}`}
    >
      {label}
    </span>
  );
}

function IntentBadge({ intent }) {
  const map = {
    promise_to_pay: { label: "Promise", cls: "rung-2" },
    dispute: { label: "Dispute", cls: "rung-3" },
    claims_paid: { label: "Claims Paid", cls: "rung-1" },
    request_info: { label: "Info Request", cls: "rung-0" },
    hostile: { label: "Hostile", cls: "rung-3" },
    unclear: { label: "Unclear", cls: "rung-0" },
  };
  const m = map[intent] || map.unclear;
  return (
    <span
      className={`font-mono-data text-[10px] uppercase tracking-wider px-2 py-0.5 ${m.cls}`}
    >
      {m.label}
    </span>
  );
}

export default function ActivityFeed({ items, onOpenInvoice }) {
  return (
    <div
      data-testid="activity-feed-widget"
      className="bg-white border border-ink/10 p-6 flex flex-col h-full"
    >
      <div className="flex items-baseline justify-between mb-4">
        <div>
          <div className="font-mono-data text-xs uppercase tracking-widest text-ink/60">
            Live Activity
          </div>
          <h2 className="font-serif-display text-2xl mt-1 text-ink">
            What the agent is doing
          </h2>
        </div>
        <div
          className="font-mono-data text-[10px] uppercase tracking-widest text-ink/50"
          data-testid="activity-count"
        >
          {items?.length || 0} events
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 pr-2 max-h-[560px]">
        {!items || items.length === 0 ? (
          <div className="text-center py-12 font-mono-data text-xs uppercase tracking-widest text-ink/40">
            No activity yet · Run the agent tick to begin
          </div>
        ) : (
          items.map((it) => (
            <div
              key={it.id}
              className="fade-in border-l-2 pl-3 py-1"
              style={{
                borderColor: it.type === "inbound" ? "#D97706" : "#0A1128",
              }}
              data-testid={`activity-item-${it.id}`}
            >
              <div className="flex items-center gap-2 mb-1">
                {it.type === "outbound" ? (
                  it.rung === 3 ? (
                    <Scales size={13} weight="fill" className="text-terracotta" />
                  ) : (
                    <PaperPlaneTilt size={13} weight="fill" className="text-ink" />
                  )
                ) : (
                  <ChatCircleText size={13} weight="fill" className="text-marigold" />
                )}
                {it.type === "outbound" ? (
                  <RungBadge rung={it.rung} />
                ) : (
                  <IntentBadge intent={it.intent} />
                )}
                <button
                  className="font-mono-data text-[10px] uppercase tracking-wider text-ink hover:underline"
                  onClick={() => onOpenInvoice && onOpenInvoice(it.invoice_id)}
                  data-testid={`activity-open-${it.invoice_id}`}
                >
                  {it.invoice_number}
                </button>
                {it.type === "outbound" && it.channel && (
                  <span
                    className={`font-mono-data text-[9px] uppercase tracking-wider px-1.5 py-0.5 border ${
                      it.delivered
                        ? "text-forest border-forest/30 bg-forest/5"
                        : it.channel === "demo"
                        ? "text-ink/50 border-ink/15 bg-ink/5"
                        : "text-terracotta border-terracotta/30 bg-terracotta/5"
                    }`}
                    title={it.delivery_error || (it.delivered ? "delivered" : "not delivered")}
                  >
                    {it.delivered ? "✓" : "!"} {it.channel}
                  </span>
                )}
                <span className="font-mono-data text-[10px] text-ink/50 ml-auto">
                  {relativeTime(it.at)}
                </span>
              </div>
              <div className="text-sm text-ink/85 leading-snug line-clamp-3">
                {it.text}
              </div>
              {it.debtor_name && (
                <div className="mt-1 font-mono-data text-[10px] uppercase tracking-wider text-ink/50">
                  {it.debtor_name} · {it.debtor_company}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
