import React from "react";
import { formatINR } from "@/lib/format";
import { Warning } from "@phosphor-icons/react";

export default function EscalationQueue({ items, onOpenInvoice }) {
  return (
    <div
      data-testid="escalation-queue-widget"
      className="bg-white border border-ink/10 p-6 flex flex-col h-full"
    >
      <div className="flex items-baseline justify-between mb-4">
        <div className="flex items-center gap-2">
          <Warning size={18} weight="fill" className="text-terracotta" />
          <div>
            <div className="font-mono-data text-xs uppercase tracking-widest text-ink/60">
              Needs You
            </div>
            <h2 className="font-serif-display text-2xl mt-1 text-ink">
              Human escalation queue
            </h2>
          </div>
        </div>
        <div
          className="font-mono-data text-[10px] uppercase tracking-widest text-ink/50"
          data-testid="escalation-count"
        >
          {items?.length || 0} open
        </div>
      </div>

      <div className="flex-1 overflow-y-auto max-h-[560px]">
        {!items || items.length === 0 ? (
          <div className="text-center py-12 font-mono-data text-xs uppercase tracking-widest text-ink/40">
            All clear · Agent has this handled
          </div>
        ) : (
          <table className="w-full">
            <tbody>
              {items.map((inv) => (
                <tr
                  key={inv.id}
                  className="row-hover cursor-pointer border-b border-ink/10"
                  onClick={() => onOpenInvoice && onOpenInvoice(inv.id)}
                  data-testid={`escalation-row-${inv.id}`}
                >
                  <td className="py-3 pr-3 align-top">
                    <div className="font-mono-data text-xs text-ink">
                      {inv.invoice_number}
                    </div>
                    <div className="font-mono-data text-[10px] uppercase text-ink/50 mt-0.5">
                      {inv.debtor?.name}
                    </div>
                  </td>
                  <td className="py-3 pr-3 align-top">
                    <div className="font-mono-data text-sm text-ink">
                      {formatINR(inv.amount_inr)}
                    </div>
                    <div className="font-mono-data text-[10px] text-terracotta mt-0.5">
                      {inv.days_overdue}d overdue
                    </div>
                  </td>
                  <td className="py-3 align-top">
                    {inv.last_inbound ? (
                      <div className="text-xs text-ink/80 line-clamp-2 italic">
                        &ldquo;{inv.last_inbound.raw_text}&rdquo;
                      </div>
                    ) : (
                      <div className="font-mono-data text-[10px] uppercase text-ink/40">
                        awaiting human
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
