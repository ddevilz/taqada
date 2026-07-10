import React from "react";
import { formatINR, compactINR, bucketLabel, bucketColor } from "@/lib/format";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Cell,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export default function AgingBuckets({ buckets }) {
  if (!buckets) return null;
  const data = buckets.map((b) => ({
    key: b.key,
    label: bucketLabel(b.key),
    amount: b.amount,
    count: b.count,
    color: bucketColor(b.key),
  }));

  return (
    <div
      data-testid="aging-buckets-widget"
      className="bg-white border border-ink/10 p-6"
    >
      <div className="flex items-baseline justify-between mb-6">
        <div>
          <div className="font-mono-data text-xs uppercase tracking-widest text-ink/60">
            Aging Buckets
          </div>
          <h2 className="font-serif-display text-2xl mt-1 text-ink">
            Where the money is stuck
          </h2>
        </div>
      </div>

      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 8, right: 8, bottom: 8, left: 0 }}
          >
            <XAxis
              dataKey="label"
              stroke="#0A1128"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: "#EBE7DD" }}
              style={{ fontFamily: "IBM Plex Mono" }}
            />
            <YAxis
              stroke="#0A1128"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => compactINR(v).replace("₹", "")}
              style={{ fontFamily: "IBM Plex Mono" }}
            />
            <Tooltip
              cursor={{ fill: "rgba(10,17,40,0.04)" }}
              contentStyle={{
                background: "#0A1128",
                border: "none",
                borderRadius: 0,
                fontFamily: "IBM Plex Mono",
                fontSize: 12,
                color: "#F9F6F0",
              }}
              itemStyle={{ color: "#F9F6F0" }}
              labelStyle={{ color: "#F9F6F0" }}
              formatter={(v, _n, p) => [
                `${formatINR(v)} · ${p.payload.count} inv`,
                "amount",
              ]}
            />
            <Bar dataKey="amount">
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-5 gap-3 mt-4 pt-4 border-t border-ink/10">
        {data.map((b) => (
          <div key={b.key} data-testid={`bucket-${b.key}`}>
            <div className="flex items-center gap-2">
              <span
                className="w-2 h-2 inline-block"
                style={{ background: b.color }}
              />
              <span className="font-mono-data text-[10px] uppercase text-ink/60">
                {b.label}
              </span>
            </div>
            <div className="font-mono-data text-sm text-ink mt-1">
              {compactINR(b.amount)}
            </div>
            <div className="font-mono-data text-[10px] text-ink/50">
              {b.count} invoices
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
