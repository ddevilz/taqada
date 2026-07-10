import React, { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import AgingBuckets from "@/components/AgingBuckets";
import RecoveredCounter from "@/components/RecoveredCounter";
import ActivityFeed from "@/components/ActivityFeed";
import EscalationQueue from "@/components/EscalationQueue";
import ControlStrip from "@/components/ControlStrip";
import InvoiceLedger from "@/components/InvoiceLedger";
import InvoiceDrawer from "@/components/InvoiceDrawer";
import { Scales } from "@phosphor-icons/react";

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [activity, setActivity] = useState([]);
  const [escalations, setEscalations] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [drawerId, setDrawerId] = useState(null);
  const [config, setConfig] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [s, a, e, inv, c] = await Promise.all([
        api.summary(),
        api.activity(40),
        api.escalations(),
        api.invoices(),
        api.config(),
      ]);
      setSummary(s);
      setActivity(a);
      setEscalations(e);
      setInvoices(inv);
      setConfig(c);
    } catch (err) {
      toast.error("Failed to load dashboard: " + err.message);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const openInvoice = (id) => setDrawerId(id);
  const closeDrawer = () => setDrawerId(null);

  return (
    <div className="min-h-screen bg-parchment">
      {/* Top masthead */}
      <header className="border-b border-ink/10 bg-parchment">
        <div className="max-w-[1500px] mx-auto px-6 lg:px-10 py-6 flex items-baseline justify-between">
          <div className="flex items-baseline gap-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 bg-ink text-parchment flex items-center justify-center">
                <Scales size={18} weight="fill" />
              </div>
              <div>
                <h1 className="font-serif-display text-3xl leading-none text-ink" data-testid="app-title">
                  Taqada
                </h1>
                <div className="font-mono-data text-[10px] uppercase tracking-[0.25em] text-ink/50 mt-1">
                  MSME Collections · Agentic
                </div>
              </div>
            </div>
          </div>
          <div className="hidden md:flex items-center gap-6 font-mono-data text-[10px] uppercase tracking-widest text-ink/60">
            {config && (
              <>
                <span data-testid="cfg-rbi-rate">RBI · {config.rbi_bank_rate_percent}%</span>
                <span data-testid="cfg-llm">LLM · {config.llm.backend}</span>
                <span
                  data-testid="cfg-razorpay"
                  className={config.razorpay?.enabled ? "text-forest" : "text-ink/50"}
                >
                  Razorpay · {config.razorpay?.enabled ? "test" : "off"}
                </span>
                <span
                  data-testid="cfg-channel"
                  className={
                    config.messaging?.active === "whatsapp"
                      ? "text-forest"
                      : config.messaging?.active === "telegram"
                      ? "text-forest"
                      : "text-ink/50"
                  }
                >
                  Channel · {config.messaging?.active}
                  {config.messaging?.telegram?.bot_username &&
                    ` (@${config.messaging.telegram.bot_username})`}
                </span>
              </>
            )}
          </div>
        </div>
      </header>

      <ControlStrip invoices={invoices} onRefresh={refresh} />

      {/* Hero pitch strip */}
      <section className="max-w-[1500px] mx-auto px-6 lg:px-10 pt-10">
        <p className="font-serif-display text-3xl lg:text-4xl leading-tight text-ink max-w-4xl">
          Indian small businesses spend <span className="text-terracotta">14 hours a week</span> chasing money they&apos;ve already earned. Taqada chases it for them — politely, persistently, and with the tax code on its side.
        </p>
      </section>

      {/* 4-widget dashboard grid */}
      <section className="max-w-[1500px] mx-auto px-6 lg:px-10 py-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <RecoveredCounter summary={summary} />
        </div>
        <div className="lg:col-span-2">
          <AgingBuckets buckets={summary?.buckets} />
        </div>
        <div className="lg:col-span-2">
          <ActivityFeed items={activity} onOpenInvoice={openInvoice} />
        </div>
        <div className="lg:col-span-1">
          <EscalationQueue items={escalations} onOpenInvoice={openInvoice} />
        </div>
      </section>

      {/* Invoice ledger */}
      <section className="max-w-[1500px] mx-auto px-6 lg:px-10 pb-16">
        <InvoiceLedger invoices={invoices} onOpenInvoice={openInvoice} />
      </section>

      {/* Legal footer */}
      <footer className="border-t border-ink/10 bg-white">
        <div className="max-w-[1500px] mx-auto px-6 lg:px-10 py-8 grid grid-cols-1 md:grid-cols-3 gap-8 font-mono-data text-[11px] text-ink/70">
          <div>
            <div className="uppercase tracking-widest text-ink/50 mb-2">MSMED Act, 2006 · Section 15</div>
            Buyer must pay a micro/small enterprise within the agreed period, capped at 45 days. If no written agreement, within 15 days.
          </div>
          <div>
            <div className="uppercase tracking-widest text-ink/50 mb-2">MSMED Act · Section 16</div>
            Delayed payment attracts compound interest, monthly compounded, at 3× the RBI bank rate.
          </div>
          <div>
            <div className="uppercase tracking-widest text-ink/50 mb-2">Income Tax Act · Section 43B(h)</div>
            Payments to micro/small enterprises made after the Section 15 limit are not tax-deductible in the same financial year.
          </div>
        </div>
      </footer>

      <InvoiceDrawer
        invoiceId={drawerId}
        open={!!drawerId}
        onClose={closeDrawer}
        onRefresh={refresh}
      />
    </div>
  );
}
