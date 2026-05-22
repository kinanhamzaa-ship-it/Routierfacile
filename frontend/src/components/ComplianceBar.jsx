import { minutesToHM } from "../lib/time";
import { Gauge } from "@phosphor-icons/react";

export default function ComplianceBar({ data }) {
  if (!data) return null;
  const { cycle, latest_entry } = data;
  const dailyRestStatus = latest_entry?.daily_rest_status || null;

  return (
    <div data-testid="compliance-bar" className="sticky top-0 z-30 bg-rf-bg/95 backdrop-blur-md border-b border-rf-border">
      <div className="px-4 pt-4 pb-3">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="rf-label">Cycle en cours</div>
            <div className="flex items-baseline gap-2 mt-1">
              <Gauge size={20} className="text-rf-blue" weight="duotone" />
              <span className="font-display text-3xl tracking-tight leading-none" data-testid="weekly-driven">
                {minutesToHM(cycle.total_driving_minutes)}
              </span>
              <span className="text-rf-muted text-xs uppercase tracking-[0.15em]">conduite</span>
            </div>
          </div>
          <div className="text-right">
            <div className="rf-label">Jours</div>
            <div className="font-display text-2xl mt-1" data-testid="cycle-days">
              {cycle.days_worked}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <DailyRestTile status={dailyRestStatus} minutes={latest_entry?.daily_rest_minutes} />
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
          <BreakViolationsTile
            count={cycle.break_violations_count || 0}
            testid="indicator-break-violations"
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

function BreakViolationsTile({ count, testid }) {
  const color = count === 0 ? "rf-green" : "rf-red";
  return (
    <div className="rf-tile py-2 px-3" data-testid={testid}>
      <div className="rf-label">Pauses 4h30</div>
      <div className={`font-display text-base mt-0.5 text-${color}`}>
        {count === 0 ? "OK" : `${count} alerte${count > 1 ? "s" : ""}`}
      </div>
    </div>
  );
}
