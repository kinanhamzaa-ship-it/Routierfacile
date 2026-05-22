import { minutesToHM } from "../lib/time";

const colorClass = {
  green: "bg-rf-green",
  orange: "bg-rf-orange",
  red: "bg-rf-red",
};

export default function ComplianceBar({ data }) {
  if (!data) return null;
  const { week, daily_rest_status, month } = data;
  const pct = Math.min(100, (week.total_driving_minutes / week.weekly_limit_minutes) * 100);
  const barColor = colorClass[week.status];

  return (
    <div
      data-testid="compliance-bar"
      className="sticky top-0 z-30 bg-rf-bg/95 backdrop-blur-md border-b border-rf-border"
    >
      <div className="px-4 pt-4 pb-3">
        <div className="flex items-center justify-between mb-2">
          <div>
            <div className="rf-label">Semaine en cours</div>
            <div className="font-display text-3xl tracking-tight leading-none mt-1">
              <span data-testid="weekly-driven">{minutesToHM(week.total_driving_minutes)}</span>
              <span className="text-rf-muted text-lg ml-2">/ 56h00</span>
            </div>
          </div>
          <div className="text-right">
            <div className="rf-label">Restant</div>
            <div className="font-display text-2xl mt-1" data-testid="weekly-remaining">
              {minutesToHM(week.remaining_minutes)}
            </div>
          </div>
        </div>

        <div className="h-2 w-full bg-rf-elevated rounded-full overflow-hidden">
          <div
            data-testid="weekly-progress"
            className={`h-full ${barColor} transition-all`}
            style={{ width: `${pct}%` }}
          />
        </div>

        <div className="mt-3 grid grid-cols-3 gap-2 text-[11px]">
          <Indicator label="Repos jour" status={daily_rest_status} testid="indicator-rest" />
          <Indicator label="Conduite hebdo" status={week.status} testid="indicator-weekly" />
          <div className="rf-tile py-2 px-3" data-testid="indicator-decoucher">
            <div className="rf-label">Découcher / mois</div>
            <div className="font-display text-base mt-0.5">{month?.decoucher_count ?? 0}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Indicator({ label, status, testid }) {
  const text = status === "green" ? "OK" : status === "orange" ? "Vigilance" : "Risque";
  const dot = colorClass[status] || "bg-rf-muted";
  return (
    <div className="rf-tile py-2 px-3" data-testid={testid}>
      <div className="rf-label">{label}</div>
      <div className="flex items-center gap-2 mt-0.5">
        <span className={`rf-status-dot ${dot}`} />
        <span className="text-sm font-medium">{text}</span>
      </div>
    </div>
  );
}
