import { minutesToHM } from "../lib/time";

const colorClass = {
  green: "bg-rf-green",
  orange: "bg-rf-orange",
  red: "bg-rf-red",
};

export default function ComplianceBar({ data }) {
  if (!data) return null;
  const { cycle, last_entry, month } = data;
  const pct = Math.min(100, (cycle.total_driving_minutes / cycle.weekly_limit_minutes) * 100);
  const barColor = colorClass[cycle.status];
  const dailyRestStatus = last_entry?.daily_rest_status || null;

  return (
    <div data-testid="compliance-bar" className="sticky top-0 z-30 bg-rf-bg/95 backdrop-blur-md border-b border-rf-border">
      <div className="px-4 pt-4 pb-3">
        <div className="flex items-center justify-between mb-2">
          <div>
            <div className="rf-label">Cycle en cours</div>
            <div className="font-display text-3xl tracking-tight leading-none mt-1">
              <span data-testid="weekly-driven">{minutesToHM(cycle.total_driving_minutes)}</span>
              <span className="text-rf-muted text-lg ml-2">/ 56h00</span>
            </div>
          </div>
          <div className="text-right">
            <div className="rf-label">Restant</div>
            <div className="font-display text-2xl mt-1" data-testid="weekly-remaining">
              {minutesToHM(cycle.remaining_minutes)}
            </div>
          </div>
        </div>

        <div className="h-2 w-full bg-rf-elevated rounded-full overflow-hidden">
          <div data-testid="weekly-progress" className={`h-full ${barColor} transition-all`} style={{ width: `${pct}%` }} />
        </div>

        <div className="mt-3 grid grid-cols-3 gap-2">
          <DailyRestTile status={dailyRestStatus} minutes={last_entry?.daily_rest_minutes} />
          <CounterTile
            label="Repos réduits"
            value={cycle.reduced_rest_used}
            max={cycle.reduced_rest_max}
            testid="indicator-reduced"
          />
          <CounterTile
            label="Extensions 10h"
            value={cycle.extensions_used}
            max={cycle.extensions_max}
            testid="indicator-extensions"
          />
        </div>
      </div>
    </div>
  );
}

function DailyRestTile({ status, minutes }) {
  let dot = "bg-rf-muted";
  let txt = "—";
  if (status === "ok") { dot = "bg-rf-green"; txt = "OK"; }
  else if (status === "reduced") { dot = "bg-rf-orange"; txt = "Réduit"; }
  else if (status === "warning") { dot = "bg-rf-red"; txt = "Alerte"; }
  return (
    <div className="rf-tile py-2 px-3" data-testid="indicator-rest">
      <div className="rf-label">Repos jour</div>
      <div className="flex items-center gap-2 mt-0.5">
        <span className={`rf-status-dot ${dot}`} />
        <span className="text-sm font-medium">{txt}</span>
      </div>
      {minutes != null && <div className="text-[10px] text-rf-muted mt-0.5">{minutesToHM(minutes)}</div>}
    </div>
  );
}

function CounterTile({ label, value, max, testid }) {
  const pct = value / max;
  const color = pct >= 1 ? "rf-red" : pct >= 0.66 ? "rf-orange" : "rf-green";
  return (
    <div className="rf-tile py-2 px-3" data-testid={testid}>
      <div className="rf-label">{label}</div>
      <div className={`font-display text-base mt-0.5 text-${color}`}>{value} / {max}</div>
    </div>
  );
}
