// Indian number formatting + helpers
export function formatINR(amount, { withSymbol = true, showPaise = false } = {}) {
  if (amount === null || amount === undefined || isNaN(amount)) return "—";
  const sign = amount < 0 ? "-" : "";
  const abs = Math.abs(Number(amount));
  const [whole, frac] = abs.toFixed(2).split(".");
  let grouped;
  if (whole.length <= 3) {
    grouped = whole;
  } else {
    const head = whole.slice(0, -3);
    const tail = whole.slice(-3);
    const chunks = [];
    let h = head;
    while (h.length > 2) {
      chunks.unshift(h.slice(-2));
      h = h.slice(0, -2);
    }
    if (h) chunks.unshift(h);
    grouped = chunks.join(",") + "," + tail;
  }
  const symbol = withSymbol ? "₹" : "";
  return showPaise ? `${sign}${symbol}${grouped}.${frac}` : `${sign}${symbol}${grouped}`;
}

export function compactINR(amount) {
  if (amount === null || amount === undefined || isNaN(amount)) return "—";
  const abs = Math.abs(Number(amount));
  if (abs >= 10000000) return `₹${(abs / 10000000).toFixed(2)} Cr`;
  if (abs >= 100000) return `₹${(abs / 100000).toFixed(2)} L`;
  if (abs >= 1000) return `₹${(abs / 1000).toFixed(1)}K`;
  return `₹${abs.toFixed(0)}`;
}

export function relativeTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const diff = (now - d) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function bucketLabel(key) {
  const map = {
    current: "Current",
    "1-15": "1–15 days",
    "16-45": "16–45 days",
    "46-90": "46–90 days",
    "90+": "90+ days",
  };
  return map[key] || key;
}

export function bucketColor(key) {
  const map = {
    current: "#0A1128",
    "1-15": "#3A435E",
    "16-45": "#D97706",
    "46-90": "#C84B31",
    "90+": "#8B2F1F",
  };
  return map[key] || "#0A1128";
}

export function statusColor(status) {
  const map = {
    unpaid: "text-ink border-ink/20 bg-ink/5",
    promised: "text-marigold border-marigold/30 bg-marigold/10",
    paid: "text-forest border-forest/30 bg-forest/10",
    disputed: "text-terracotta border-terracotta/30 bg-terracotta/10",
    escalated_human: "text-terracotta border-terracotta/30 bg-terracotta/10",
  };
  return map[status] || "text-ink border-ink/20 bg-ink/5";
}
