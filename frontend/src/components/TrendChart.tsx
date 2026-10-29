import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { tr, currentLocale } from "../i18n";
import { dateLabel, money } from "../types";
import type { Currency, Dashboard } from "../types";
export default function TrendChart({
  data,
  reduced,
  currency,
}: {
  data: Dashboard["trend"];
  reduced: boolean;
  currency: Currency;
}) {
  return (
    <div
      className="trend-chart"
      role="img"
      aria-label={`${tr("Vendas no período")}: ${money(
        data.reduce((total, p) => total + p.amount_cents, 0),
        currency,
      )}`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 12, right: 8, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient id="salesFill" x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="0%"
                stopColor="var(--liq-accent)"
                stopOpacity={0.24}
              />
              <stop
                offset="100%"
                stopColor="var(--liq-accent)"
                stopOpacity={0}
              />
            </linearGradient>
          </defs>
          <CartesianGrid
            vertical={false}
            stroke="var(--liq-border)"
            strokeDasharray="3 6"
          />
          <XAxis
            dataKey="date"
            axisLine={false}
            tickLine={false}
            tick={{ fill: "var(--liq-muted)", fontSize: 13 }}
            tickFormatter={(value) => dateLabel(String(value))}
            minTickGap={42}
            dy={10}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: "var(--liq-muted)", fontSize: 13 }}
            tickFormatter={(v) =>
              new Intl.NumberFormat(currentLocale(), {
                notation: "compact",
                maximumFractionDigits: 1,
              }).format(v / 100)
            }
            tickCount={4}
          />
          <Tooltip
            labelFormatter={(v) => dateLabel(String(v))}
            formatter={(v) => [money(Number(v), currency), tr("Vendas")]}
            contentStyle={{
              background: "var(--liq-surface-elevated)",
              border: "1px solid var(--liq-border)",
              borderRadius: 8,
              color: "var(--liq-text)",
              fontSize: 13,
            }}
          />
          <Area
            type="monotone"
            dataKey="amount_cents"
            stroke="var(--liq-accent-bright)"
            strokeWidth={2.4}
            fill="url(#salesFill)"
            isAnimationActive={!reduced}
            animationDuration={550}
            dot={data.length === 1 ? { r: 4 } : false}
            activeDot={{ r: 5, stroke: "var(--liq-bg)", strokeWidth: 3 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
