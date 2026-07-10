import React, { useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import {
  Play,
  ChatDots,
  CheckSquare,
  ArrowsClockwise,
} from "@phosphor-icons/react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

export default function ControlStrip({ invoices, onRefresh }) {
  const [running, setRunning] = useState(false);
  const [replyOpen, setReplyOpen] = useState(false);
  const [paidOpen, setPaidOpen] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState("");
  const [replyText, setReplyText] = useState("Cash flow is tight this month — can I pay by the 25th?");
  const [paidInvoice, setPaidInvoice] = useState("");

  const unpaid = (invoices || []).filter(
    (i) => i.status === "unpaid" || i.status === "promised"
  );
  const chasableInvoices = unpaid.filter((i) => i.days_overdue > 0);

  const runTick = async () => {
    setRunning(true);
    try {
      const r = await api.runAgent();
      toast.success(
        `Agent tick complete · ${r.chased} messages sent · ${r.scanned} invoices scanned`
      );
      onRefresh && onRefresh();
    } catch (e) {
      toast.error("Agent tick failed: " + (e.response?.data?.detail || e.message));
    } finally {
      setRunning(false);
    }
  };

  const submitReply = async () => {
    if (!selectedInvoice || !replyText.trim()) {
      toast.error("Pick an invoice and enter a reply");
      return;
    }
    try {
      const r = await api.simulateReply(selectedInvoice, replyText);
      toast.success(`Classified as ${r.intent} · action: ${r.action}`);
      setReplyOpen(false);
      onRefresh && onRefresh();
    } catch (e) {
      toast.error("Reply failed: " + (e.response?.data?.detail || e.message));
    }
  };

  const submitPaid = async () => {
    if (!paidInvoice) {
      toast.error("Pick an invoice");
      return;
    }
    try {
      const r = await api.markPaid(paidInvoice);
      toast.success(`Marked paid: ₹${r.amount.toLocaleString("en-IN")}`);
      setPaidOpen(false);
      onRefresh && onRefresh();
    } catch (e) {
      toast.error("Mark paid failed: " + (e.response?.data?.detail || e.message));
    }
  };

  return (
    <>
      <div
        data-testid="control-strip"
        className="bg-ink text-parchment px-6 py-3 flex items-center gap-3 flex-wrap border-y border-ink"
      >
        <div className="font-mono-data text-[10px] uppercase tracking-[0.2em] text-parchment/60 mr-2">
          Demo Mode
        </div>
        <button
          onClick={runTick}
          disabled={running}
          data-testid="btn-run-agent"
          className="flex items-center gap-2 bg-parchment text-ink px-4 py-2 font-mono-data text-xs uppercase tracking-wider hover:bg-parchment-2 transition-colors disabled:opacity-50"
        >
          {running ? (
            <ArrowsClockwise size={14} weight="bold" className="animate-spin" />
          ) : (
            <Play size={14} weight="fill" />
          )}
          {running ? "Running…" : "Run agent tick"}
        </button>
        <button
          onClick={() => {
            setSelectedInvoice(chasableInvoices[0]?.id || "");
            setReplyOpen(true);
          }}
          data-testid="btn-simulate-reply"
          className="flex items-center gap-2 border border-parchment/30 text-parchment px-4 py-2 font-mono-data text-xs uppercase tracking-wider hover:bg-parchment/10 transition-colors"
        >
          <ChatDots size={14} weight="fill" />
          Simulate debtor reply
        </button>
        <button
          onClick={() => {
            setPaidInvoice(unpaid[0]?.id || "");
            setPaidOpen(true);
          }}
          data-testid="btn-mark-paid"
          className="flex items-center gap-2 border border-parchment/30 text-parchment px-4 py-2 font-mono-data text-xs uppercase tracking-wider hover:bg-parchment/10 transition-colors"
        >
          <CheckSquare size={14} weight="fill" />
          Mark invoice paid
        </button>
        <div className="ml-auto font-mono-data text-[10px] uppercase tracking-widest text-parchment/50">
          Gemma · Fireworks AI
        </div>
      </div>

      {/* Simulate reply modal */}
      <Dialog open={replyOpen} onOpenChange={setReplyOpen}>
        <DialogContent data-testid="simulate-reply-dialog" className="bg-white border border-ink/20 max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-serif-display text-2xl text-ink">
              Simulate a debtor WhatsApp reply
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div>
              <label className="font-mono-data text-[10px] uppercase tracking-widest text-ink/60 mb-2 block">
                On invoice
              </label>
              <Select value={selectedInvoice} onValueChange={setSelectedInvoice}>
                <SelectTrigger data-testid="reply-invoice-select" className="border-ink/20">
                  <SelectValue placeholder="Pick an invoice" />
                </SelectTrigger>
                <SelectContent className="bg-white border-ink/20 max-h-72">
                  {chasableInvoices.map((i) => (
                    <SelectItem key={i.id} value={i.id} data-testid={`reply-option-${i.invoice_number}`}>
                      {i.invoice_number} · {i.debtor?.name} · ₹{i.amount_inr.toLocaleString("en-IN")} · {i.days_overdue}d
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="font-mono-data text-[10px] uppercase tracking-widest text-ink/60 mb-2 block">
                Reply text
              </label>
              <Textarea
                data-testid="reply-text-input"
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                rows={4}
                className="border-ink/20 font-body"
              />
              <div className="mt-2 flex gap-2 flex-wrap">
                {[
                  "I'll pay by next Friday",
                  "Already paid — check your account",
                  "This invoice is wrong, we didn't order this",
                  "Cash flow is tight, can I pay next month?",
                  "Stop messaging me",
                ].map((s) => (
                  <button
                    key={s}
                    onClick={() => setReplyText(s)}
                    className="text-[10px] font-mono-data uppercase tracking-wider bg-parchment px-2 py-1 border border-ink/15 hover:bg-parchment-2"
                    data-testid={`reply-preset-${s.slice(0, 6)}`}
                  >
                    {s.slice(0, 30)}…
                  </button>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter className="mt-4">
            <button
              onClick={() => setReplyOpen(false)}
              className="border border-ink/20 px-4 py-2 font-mono-data text-xs uppercase tracking-wider hover:bg-parchment-2"
            >
              Cancel
            </button>
            <button
              onClick={submitReply}
              data-testid="reply-submit"
              className="bg-ink text-parchment px-4 py-2 font-mono-data text-xs uppercase tracking-wider hover:bg-ink-2"
            >
              Send reply as debtor
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Mark paid modal */}
      <Dialog open={paidOpen} onOpenChange={setPaidOpen}>
        <DialogContent data-testid="mark-paid-dialog" className="bg-white border border-ink/20 max-w-md">
          <DialogHeader>
            <DialogTitle className="font-serif-display text-2xl text-ink">
              Simulate payment received
            </DialogTitle>
          </DialogHeader>
          <div className="mt-2">
            <label className="font-mono-data text-[10px] uppercase tracking-widest text-ink/60 mb-2 block">
              Which invoice
            </label>
            <Select value={paidInvoice} onValueChange={setPaidInvoice}>
              <SelectTrigger data-testid="paid-invoice-select" className="border-ink/20">
                <SelectValue placeholder="Pick an invoice" />
              </SelectTrigger>
              <SelectContent className="bg-white border-ink/20 max-h-72">
                {unpaid.map((i) => (
                  <SelectItem key={i.id} value={i.id}>
                    {i.invoice_number} · {i.debtor?.name} · ₹{i.amount_inr.toLocaleString("en-IN")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter className="mt-4">
            <button
              onClick={() => setPaidOpen(false)}
              className="border border-ink/20 px-4 py-2 font-mono-data text-xs uppercase tracking-wider hover:bg-parchment-2"
            >
              Cancel
            </button>
            <button
              onClick={submitPaid}
              data-testid="paid-submit"
              className="bg-forest text-parchment px-4 py-2 font-mono-data text-xs uppercase tracking-wider hover:opacity-90"
            >
              Mark paid
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
