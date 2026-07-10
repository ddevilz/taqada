import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { formatINR, relativeTime } from "@/lib/format";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import { Scales, PaperPlaneTilt, ChatCircleText } from "@phosphor-icons/react";

function RungPill({ rung }) {
  if (rung === 0) return <span className="rung-0 font-mono-data text-[10px] uppercase tracking-wider px-2 py-0.5">Reply</span>;
  const cls = `rung-${rung}`;
  const label = rung === 1 ? "R1 Friendly" : rung === 2 ? "R2 Firm" : "R3 Statutory";
  return <span className={`${cls} font-mono-data text-[10px] uppercase tracking-wider px-2 py-0.5`}>{label}</span>;
}

export default function InvoiceDrawer({ invoiceId, open, onClose, onRefresh }) {
  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(false);
  const [previewRung, setPreviewRung] = useState(null);
  const [previewMessage, setPreviewMessage] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const load = async (id) => {
    setLoading(true);
    try {
      const inv = await api.invoice(id);
      setInvoice(inv);
    } catch (e) {
      toast.error("Failed to load invoice");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (invoiceId && open) {
      load(invoiceId);
    } else {
      setInvoice(null);
      setPreviewMessage(null);
      setPreviewRung(null);
    }
  }, [invoiceId, open]);

  const doPreview = async (rung) => {
    setPreviewRung(rung);
    setPreviewLoading(true);
    try {
      const r = await api.previewMessage(invoiceId, rung);
      setPreviewMessage(r);
    } catch (e) {
      toast.error("Preview failed");
    } finally {
      setPreviewLoading(false);
    }
  };

  const doChase = async () => {
    try {
      const r = await api.chaseOne(invoiceId);
      if (r.skipped) toast.info(`Not chased: ${r.reason}`);
      else toast.success(`Sent Rung ${r.rung} message via WhatsApp (demo)`);
      await load(invoiceId);
      onRefresh && onRefresh();
    } catch (e) {
      toast.error("Chase failed");
    }
  };

  const conversation = React.useMemo(() => {
    if (!invoice) return [];
    const out = [];
    (invoice.chase_events || []).forEach((e) =>
      out.push({ ...e, kind: "outbound", at: e.sent_at })
    );
    (invoice.inbound_messages || []).forEach((m) =>
      out.push({ ...m, kind: "inbound", at: m.received_at })
    );
    return out.sort((a, b) => new Date(a.at) - new Date(b.at));
  }, [invoice]);

  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent
        data-testid="invoice-drawer"
        side="right"
        className="bg-white border-l border-ink/20 sm:max-w-2xl w-full overflow-y-auto p-0"
      >
        {loading || !invoice ? (
          <div className="p-8 font-mono-data text-xs uppercase tracking-widest text-ink/40">
            Loading…
          </div>
        ) : (
          <>
            <SheetHeader className="p-6 border-b border-ink/10">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-mono-data text-xs uppercase tracking-widest text-ink/60">
                  {invoice.invoice_number}
                </span>
                <span
                  className={`font-mono-data text-[10px] uppercase tracking-wider px-2 py-0.5 border ${
                    invoice.days_overdue > 45
                      ? "text-terracotta border-terracotta/30 bg-terracotta/10"
                      : invoice.days_overdue > 0
                      ? "text-marigold border-marigold/30 bg-marigold/10"
                      : "text-ink border-ink/20 bg-ink/5"
                  }`}
                >
                  {invoice.days_overdue > 0 ? `${invoice.days_overdue}d overdue` : "current"}
                </span>
              </div>
              <SheetTitle className="font-serif-display text-3xl text-ink text-left">
                {invoice.debtor?.name}
              </SheetTitle>
              <div className="font-mono-data text-xs text-ink/60">
                {invoice.debtor?.company} · {invoice.debtor?.phone_whatsapp}
              </div>
            </SheetHeader>

            <div className="grid grid-cols-2 divide-x divide-ink/10 border-b border-ink/10">
              <div className="p-4">
                <div className="font-mono-data text-[10px] uppercase tracking-widest text-ink/50">
                  Amount
                </div>
                <div className="font-serif-display text-3xl mt-1 text-ink">
                  {formatINR(invoice.amount_inr)}
                </div>
              </div>
              <div className="p-4">
                <div className="font-mono-data text-[10px] uppercase tracking-widest text-ink/50">
                  Statutory
                </div>
                <div className="font-mono-data text-sm mt-1 text-ink">
                  Limit: {invoice.statutory_limit_days}d
                </div>
                <div className="font-mono-data text-sm text-ink">
                  Past limit: {invoice.days_past_statutory}d
                </div>
                {invoice.statutory_eligible ? (
                  <div className="font-mono-data text-xs mt-1 text-terracotta">
                    Interest: {formatINR(invoice.accrued_interest_inr)}
                  </div>
                ) : (
                  <div className="font-mono-data text-[10px] mt-1 text-ink/50 italic">
                    Not statutory-eligible · {invoice.eligibility_reason}
                  </div>
                )}
              </div>
            </div>

            <Tabs defaultValue="conversation" className="p-6">
              <TabsList className="bg-parchment border border-ink/10 rounded-none">
                <TabsTrigger data-testid="tab-conversation" value="conversation" className="font-mono-data text-xs uppercase tracking-wider">
                  Conversation
                </TabsTrigger>
                <TabsTrigger data-testid="tab-preview" value="preview" className="font-mono-data text-xs uppercase tracking-wider">
                  Preview message
                </TabsTrigger>
                <TabsTrigger data-testid="tab-details" value="details" className="font-mono-data text-xs uppercase tracking-wider">
                  Details
                </TabsTrigger>
              </TabsList>

              <TabsContent value="conversation" className="mt-4 space-y-3">
                {conversation.length === 0 ? (
                  <div className="text-center py-8 font-mono-data text-xs uppercase tracking-widest text-ink/40">
                    No conversation yet
                  </div>
                ) : (
                  conversation.map((m) => (
                    <div
                      key={m.id}
                      className={`p-3 border ${
                        m.kind === "outbound"
                          ? "bg-parchment border-ink/10"
                          : "bg-marigold/5 border-marigold/20 ml-8"
                      }`}
                      data-testid={`conv-${m.id}`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        {m.kind === "outbound" ? (
                          m.rung === 3 ? (
                            <Scales size={12} weight="fill" className="text-terracotta" />
                          ) : (
                            <PaperPlaneTilt size={12} weight="fill" />
                          )
                        ) : (
                          <ChatCircleText size={12} weight="fill" className="text-marigold" />
                        )}
                        {m.kind === "outbound" ? (
                          <RungPill rung={m.rung} />
                        ) : (
                          <span className="font-mono-data text-[10px] uppercase tracking-wider text-marigold">
                            Debtor · {m.classified_intent}
                          </span>
                        )}
                        <span className="font-mono-data text-[10px] text-ink/40 ml-auto">
                          {relativeTime(m.at)}
                        </span>
                      </div>
                      <div className={`text-sm leading-snug whitespace-pre-wrap ${m.kind === "outbound" && m.rung === 3 ? "font-mono-data text-xs" : ""}`}>
                        {m.kind === "outbound" ? m.message_text : m.raw_text}
                      </div>
                    </div>
                  ))
                )}
                <div className="pt-2 flex gap-2">
                  <button
                    data-testid="btn-chase-now"
                    onClick={doChase}
                    className="bg-ink text-parchment px-4 py-2 font-mono-data text-xs uppercase tracking-wider hover:bg-ink-2"
                  >
                    Chase now
                  </button>
                </div>
              </TabsContent>

              <TabsContent value="preview" className="mt-4">
                <div className="flex gap-2 mb-4">
                  {[1, 2, 3].map((r) => (
                    <button
                      key={r}
                      data-testid={`btn-preview-rung-${r}`}
                      onClick={() => doPreview(r)}
                      className={`font-mono-data text-xs uppercase tracking-wider px-4 py-2 border ${
                        previewRung === r
                          ? "bg-ink text-parchment border-ink"
                          : "border-ink/20 hover:bg-parchment-2"
                      }`}
                    >
                      Rung {r}
                    </button>
                  ))}
                </div>
                {previewLoading && (
                  <div className="font-mono-data text-xs text-ink/50">Generating…</div>
                )}
                {previewMessage && (
                  <div className="p-4 border border-ink/15 bg-parchment">
                    <div className="flex items-center gap-2 mb-3 flex-wrap">
                      <RungPill rung={previewMessage.rung} />
                      {previewMessage.statutory_eligible ? (
                        <span className="font-mono-data text-[10px] uppercase tracking-wider text-forest">
                          Eligible · Interest accrued: {previewMessage.accrued_interest_formatted}
                        </span>
                      ) : (
                        <span className="font-mono-data text-[10px] uppercase tracking-wider text-ink/50">
                          Gate: {previewMessage.eligibility_reason}
                        </span>
                      )}
                      {previewMessage.payment_link && (
                        <span
                          className={`font-mono-data text-[10px] uppercase tracking-wider px-2 py-0.5 border ml-auto ${
                            previewMessage.payment_link.provider === "razorpay"
                              ? "text-forest border-forest/30 bg-forest/5"
                              : "text-ink/60 border-ink/15 bg-ink/5"
                          }`}
                          data-testid="preview-payment-provider"
                        >
                          {previewMessage.payment_link.provider === "razorpay"
                            ? "Razorpay live"
                            : "Mock UPI"}
                        </span>
                      )}
                    </div>
                    <div
                      className={`text-sm leading-relaxed whitespace-pre-wrap ${
                        previewMessage.rung === 3 ? "font-mono-data text-xs" : ""
                      }`}
                      data-testid="preview-message-body"
                    >
                      {previewMessage.message}
                    </div>
                  </div>
                )}
                {!previewMessage && !previewLoading && (
                  <div className="font-mono-data text-xs uppercase tracking-widest text-ink/40">
                    Pick a rung to see the generated WhatsApp message
                  </div>
                )}
              </TabsContent>

              <TabsContent value="details" className="mt-4 space-y-3 font-mono-data text-sm">
                <Row label="Invoice number" value={invoice.invoice_number} />
                <Row label="Issue date" value={invoice.issue_date} />
                <Row label="Acceptance" value={invoice.acceptance_date} />
                <Row label="Due date" value={invoice.due_date} />
                <Row label="Written agreement" value={invoice.has_written_agreement ? "Yes" : "No"} />
                <Row label="Supplier Udyam" value={invoice.supplier_udyam_category} />
                <Row label="Aging bucket" value={invoice.aging_bucket} />
                <Row label="Selected rung" value={`R${invoice.selected_rung}`} />
                <Row
                  label={`Payment link (${invoice.payment_link?.provider || "mock_upi"})`}
                  value={
                    invoice.payment_link?.short_url ? (
                      <a
                        href={invoice.payment_link.short_url}
                        target="_blank"
                        rel="noreferrer"
                        className="underline text-forest hover:text-terracotta break-all"
                        data-testid="drawer-payment-link"
                      >
                        {invoice.payment_link.short_url}
                      </a>
                    ) : (
                      "—"
                    )
                  }
                  mono
                />
                {invoice.reconciled_via && (
                  <Row label="Reconciled via" value={invoice.reconciled_via} />
                )}
              </TabsContent>
            </Tabs>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

function Row({ label, value, mono }) {
  return (
    <div className="flex justify-between gap-4 py-2 border-b border-ink/5">
      <span className="text-[10px] uppercase tracking-widest text-ink/50">{label}</span>
      <span className={`text-ink text-right ${mono ? "break-all" : ""}`}>{value}</span>
    </div>
  );
}
