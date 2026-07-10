import React, { useState } from "react";
import { formatINR, statusColor } from "@/lib/format";

function Badge({ children, className = "", ...rest }) {
  return (
    <span
      className={`inline-flex font-mono-data text-[10px] uppercase tracking-wider px-2 py-0.5 border ${className}`}
      {...rest}
    >
      {children}
    </span>
  );
}

export default function InvoiceLedger({ invoices, onOpenInvoice }) {
  const [filter, setFilter] = useState("all");
  const filtered = (invoices || []).filter((i) => {
    if (filter === "all") return true;
    if (filter === "overdue") return i.days_overdue > 0 && i.status !== "paid";
    if (filter === "statutory") return i.selected_rung === 3;
    return i.status === filter;
  });

  const filters = [
    { key: "all", label: "All" },
    { key: "overdue", label: "Overdue" },
    { key: "statutory", label: "Statutory (Rung 3)" },
    { key: "promised", label: "Promised" },
    { key: "escalated_human", label: "Escalated" },
    { key: "paid", label: "Paid" },
  ];

  return (
    <div className="bg-white border border-ink/10 p-6" data-testid="invoice-ledger">
      <div className="flex items-baseline justify-between mb-4 flex-wrap gap-3">
        <div>
          <div className="font-mono-data text-xs uppercase tracking-widest text-ink/60">
            Invoice Ledger
          </div>
          <h2 className="font-serif-display text-2xl mt-1 text-ink">
            {filtered.length} invoices
          </h2>
        </div>
        <div className="flex gap-1 flex-wrap">
          {filters.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              data-testid={`filter-${f.key}`}
              className={`font-mono-data text-[10px] uppercase tracking-wider px-3 py-1.5 border transition-colors ${
                filter === f.key
                  ? "bg-ink text-parchment border-ink"
                  : "border-ink/15 text-ink/70 hover:bg-parchment-2"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-ink/20">
              <th className="text-left py-2 pr-3 font-mono-data text-[10px] uppercase tracking-widest text-ink/60 font-medium">Invoice</th>
              <th className="text-left py-2 pr-3 font-mono-data text-[10px] uppercase tracking-widest text-ink/60 font-medium">Debtor</th>
              <th className="text-right py-2 pr-3 font-mono-data text-[10px] uppercase tracking-widest text-ink/60 font-medium">Amount</th>
              <th className="text-left py-2 pr-3 font-mono-data text-[10px] uppercase tracking-widest text-ink/60 font-medium">Overdue</th>
              <th className="text-left py-2 pr-3 font-mono-data text-[10px] uppercase tracking-widest text-ink/60 font-medium">Udyam</th>
              <th className="text-left py-2 pr-3 font-mono-data text-[10px] uppercase tracking-widest text-ink/60 font-medium">Rung</th>
              <th className="text-left py-2 font-mono-data text-[10px] uppercase tracking-widest text-ink/60 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((inv, i) => {
              const overdueColor =
                inv.days_overdue > 45
                  ? "text-terracotta"
                  : inv.days_overdue > 15
                  ? "text-marigold"
                  : inv.days_overdue > 0
                  ? "text-ink"
                  : "text-ink/40";
              const catCls = ["micro", "small"].includes(inv.supplier_udyam_category)
                ? "cat-micro"
                : "cat-medium";
              const rungCls = `rung-${inv.selected_rung}`;
              return (
                <tr
                  key={inv.id}
                  className={`row-hover cursor-pointer border-b border-ink/5 ${i % 2 === 1 ? "bg-parchment/40" : ""}`}
                  onClick={() => onOpenInvoice && onOpenInvoice(inv.id)}
                  data-testid={`invoice-row-${inv.invoice_number}`}
                >
                  <td className="py-3 pr-3 font-mono-data text-sm">
                    {inv.invoice_number}
                  </td>
                  <td className="py-3 pr-3">
                    <div className="text-sm text-ink">{inv.debtor?.name}</div>
                    <div className="text-[11px] text-ink/50">{inv.debtor?.company}</div>
                  </td>
                  <td className="py-3 pr-3 text-right font-mono-data text-sm">
                    {formatINR(inv.amount_inr)}
                  </td>
                  <td className={`py-3 pr-3 font-mono-data text-sm ${overdueColor}`}>
                    {inv.days_overdue > 0 ? `${inv.days_overdue}d` : "—"}
                  </td>
                  <td className="py-3 pr-3">
                    <Badge className={catCls}>{inv.supplier_udyam_category}</Badge>
                  </td>
                  <td className="py-3 pr-3">
                    {inv.selected_rung > 0 && (
                      <Badge className={rungCls}>R{inv.selected_rung}</Badge>
                    )}
                    {inv.selected_rung === 3 && !inv.statutory_eligible && (
                      <span className="ml-1 font-mono-data text-[9px] text-ink/50">
                        (gated)
                      </span>
                    )}
                  </td>
                  <td className="py-3">
                    <Badge className={statusColor(inv.status)}>{inv.status.replace("_", " ")}</Badge>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
