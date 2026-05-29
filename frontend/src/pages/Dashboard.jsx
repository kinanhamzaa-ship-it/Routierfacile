import { useEffect, useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import api from "../lib/api";
import ComplianceBar from "../components/ComplianceBar";
import { useAuth } from "../context/AuthContext";
import { minutesToHM, formatDateFR, weekdayFR, MONTHS_FR } from "../lib/time";
import {
  Plus, SignOut, ForkKnife, Bed, ChartBar, ClipboardText, Clock, Briefcase, Gauge, ArrowsClockwise, UserGear,
} from "@phosphor-icons/react";

function dailyRestColor(status) {
  if (status === "ok" || status === "fractioned") return "rf-green";
  if (status === "reduced") return "rf-orange";
  return "rf-red";
}

function dailyRestBadgeClass(status) {
  if (status === "ok" || status === "fractioned") return "bg-rf-green/20 text-rf-green";
  if (status === "reduced") return "bg-rf-orange/20 text-rf-orange";
  return "bg-rf-red/20 text-rf-red";
}

function dailyRestLabel(status) {
  if (status === "ok") return "Repos normal";
  if (status === "fractioned") return "Repos fractionné";
  if (status === "reduced") return "Repos réduit";
  return "< 9h Alerte";
}


export default function Dashboard() {
  const { user, logout } = useAuth();
  const [data, setData] = useState(null);
  const [recent, setRecent] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshTick, setRefreshTick] = useState(0);
  const nav = useNavigate();
  const loc = useLocation();

  useEffect(() => {
    setLoading(true);
    Promise.all([api.get("/summary/dashboard"), api.get("/entries", { params: { limit: 5 } })])
      .then(([d, r]) => { setData(d.data); setRecent(r.data); })
      .finally(() => setLoading(false));
  }, [loc.key, refreshTick]);

  if (loading) {
    return <div className="min-h-[60vh] flex items-center justify-center text-rf-muted">Chargement du tableau de bord…</div>;
  }

  const cycle = data.cycle;
  const latest = data.latest_entry;
  const todayIsoStr = (() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  })();
  const isToday = latest?.date === todayIsoStr;
  const m = data.month;
  const now = new Date();

  return (
    <div data-testid="dashboard-page">
      <ComplianceBar data={data} />

      <header className="px-4 pt-5 pb-2 flex items-center justify-between">
        <div>
          <div className="rf-label">Bonjour</div>
          <h1 className="font-display text-3xl tracking-tight mt-1" data-testid="dashboard-greeting">
            {user?.name || user?.email}
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setRefreshTick((t) => t + 1)}
            data-testid="refresh-dashboard"
            className="rf-btn-ghost px-3 py-2"
            aria-label="Actualiser"
            title="Actualiser"
          >
            <ArrowsClockwise size={18} className={loading ? "animate-spin" : ""} />
          </button>
          <Link
            to="/account"
            data-testid="account-link"
            className="rf-btn-ghost flex items-center gap-2 text-sm"
            aria-label="Mon compte"
            title="Mon compte"
          >
            <UserGear size={18} />
          </Link>
          <button onClick={logout} data-testid="logout-btn" className="rf-btn-ghost flex items-center gap-2 text-sm" aria-label="Se déconnecter">
            <SignOut size={18} />
          </button>
        </div>
      </header>

      <div className="px-4 pt-3">
        <Link to="/new" data-testid="cta-new-entry" className="rf-btn-primary w-full flex items-center justify-center gap-2 text-lg">
          <Plus size={22} weight="bold" /> Saisir la journée du {now.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" })}
        </Link>
      </div>

      {/* Leave period info banner (6+ days inactive) */}
      {data.leave_period && <LeavePeriodBanner leave={data.leave_period} />}

      {/* Previous cycle reference (shown at the start of a new cycle) */}
      {data.previous_cycle && cycle && (
        <PreviousCycleCard prev={data.previous_cycle} current={cycle} />
      )}

      {/* Latest entry snapshot */}
      {latest && (
        <section className="px-4 pt-6" data-testid="today-section">
          <div className="rf-label mb-3 flex items-center gap-2">
            {isToday ? (
              <>Aujourd'hui · {weekdayFR(latest.date)}</>
            ) : (
              <>Dernière journée · {weekdayFR(latest.date)} {formatDateFR(latest.date)}</>
            )}
            {latest.is_legacy && (
              <span className="rf-label text-rf-muted bg-rf-elevated px-1.5 py-0.5 rounded">Archive</span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <SmallTile icon={Clock} label="Amplitude" value={minutesToHM(latest.amplitude_minutes)} testid="today-amplitude" />
            <SmallTile icon={Briefcase} label="Heures travaillées" value={minutesToHM(latest.total_working_minutes)} testid="today-worked" />
            <SmallTile icon={Gauge} label="Conduite" value={minutesToHM(latest.total_driving_minutes)} testid="today-driving" color="rf-blue" />
            <SmallTile icon={Bed} label="Pauses & repos" value={minutesToHM(latest.total_rest_minutes)} testid="today-rest" />
          </div>
          {latest.daily_rest_minutes != null && (
            <div className="mt-3 rf-tile flex items-center justify-between" data-testid="today-daily-rest">
              <div>
                <div className="rf-label">Repos journalier (depuis la veille)</div>
                <div className={`font-display text-2xl tracking-tight mt-1 text-${dailyRestColor(latest.daily_rest_status)}`}>
                  {minutesToHM(latest.daily_rest_minutes)}
                </div>
              </div>
              <div className="text-right">
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${dailyRestBadgeClass(latest.daily_rest_status)}`}>
                  {dailyRestLabel(latest.daily_rest_status)}
                </span>
                {latest.daily_rest_status === "fractioned" && (
                  <div className="text-[11px] text-rf-green mt-1">
                    3h + 9h · considéré normal
                  </div>
                )}
              </div>
            </div>
          )}
        </section>
      )}

      <section className="px-4 pt-6">
        <div className="rf-label mb-3">Mois en cours · {MONTHS_FR[m.month - 1]} {m.year}</div>
        <div className="grid grid-cols-2 gap-3">
          <SmallTile icon={ChartBar} label="Conduite" value={minutesToHM(m.total_driving_minutes)} testid="tile-driving" color="rf-blue" />
          <SmallTile icon={ClipboardText} label="Jours travaillés" value={m.working_days} testid="tile-days" />
          <SmallTile icon={Bed} label="Découcher" value={m.decoucher_count} testid="tile-decoucher" color="rf-orange" />
          <SmallTile icon={ForkKnife} label="Repas OUI" value={m.meal_counts.yes} testid="tile-meal-yes" color="rf-green" />
          <SmallTile label="Repas NON" value={m.meal_counts.no} testid="tile-meal-no" color="rf-red" />
          <SmallTile label="Repas PAS SÛR" value={m.meal_counts.unsure} testid="tile-meal-unsure" color="rf-orange" />
        </div>
        <Link to="/monthly" data-testid="monthly-shortcut" className="rf-btn-ghost mt-3 w-full flex items-center justify-center">
          Voir le rapport mensuel complet →
        </Link>
      </section>

      <section className="px-4 pt-6">
        <div className="flex items-center justify-between mb-3">
          <div className="rf-label">Dernières entrées</div>
          <Link to="/history" className="text-rf-blue text-sm" data-testid="link-history">Voir tout</Link>
        </div>
        {recent.length === 0 ? (
          <div className="rf-card p-6 text-center text-rf-muted text-sm" data-testid="empty-recent">
            Aucune entrée pour l'instant.
          </div>
        ) : (
          <div className="space-y-2">
            {recent.map((e) => (
              <button key={e.id} onClick={() => nav(`/edit/${e.id}`)} data-testid={`recent-${e.id}`} className="w-full text-left rf-tile">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <div className="rf-label capitalize">{weekdayFR(e.date)}</div>
                      {e.is_legacy && (
                        <span className="rf-label text-rf-muted bg-rf-elevated px-1.5 py-0.5 rounded">
                          Archive
                        </span>
                      )}
                    </div>
                    <div className="font-display text-xl mt-0.5">{formatDateFR(e.date)}</div>
                    <div className="text-[11px] text-rf-muted mt-1">
                      Amplitude {minutesToHM(e.amplitude_minutes)} · Travail {minutesToHM(e.total_working_minutes)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-display text-rf-blue text-lg">{minutesToHM(e.total_driving_minutes)}</div>
                    <div className="text-[11px] text-rf-muted">conduite</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function SmallTile({ icon: Icon, label, value, testid, color = "rf-blue" }) {
  return (
    <div className="rf-tile" data-testid={testid}>
      <div className="flex items-center gap-2">
        {Icon && <Icon size={14} className={`text-${color}`} weight="duotone" />}
        <span className="rf-label">{label}</span>
      </div>
      <div className="font-display text-2xl tracking-tight mt-1">{value}</div>
    </div>
  );
}

function PreviousCycleCard({ prev, current }) {
  const formatDate = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" });
  };
  const formatDateOnly = (ymd) => {
    if (!ymd) return "—";
    const [y, m, d] = ymd.split("-");
    return `${d}/${m}`;
  };
  const fmtH = (m) => {
    const h = Math.floor((m || 0) / 60);
    const min = (m || 0) % 60;
    return `${h}h${String(min).padStart(2, "0")}`;
  };
  const isLeave = prev.is_leave_period;
  const rangeStart = isLeave ? formatDateOnly(prev.leave_start_date) : formatDate(prev.started_at);
  const rangeEnd = isLeave ? formatDateOnly(prev.leave_end_date) : formatDate(prev.ended_at);
  return (
    <section className="px-4 pt-5" data-testid="previous-cycle-card">
      <div className="rf-label mb-2 flex items-center gap-2">
        Référence · Cycle précédent
        {isLeave && (
          <span className="rf-label text-rf-orange bg-rf-orange/15 px-1.5 py-0.5 rounded">
            Période d'absence
          </span>
        )}
        {!isLeave && prev.is_reduced_weekly_rest && (
          <span className="rf-label text-rf-orange bg-rf-orange/15 px-1.5 py-0.5 rounded">
            Repos réduit
          </span>
        )}
      </div>
      <div className="rf-card overflow-hidden">
        <div className="px-4 py-2.5 text-[11px] text-rf-muted border-b border-rf-border flex items-center justify-between">
          <span>Du {rangeStart} au {rangeEnd}</span>
          <span>{prev.days_worked} j</span>
        </div>
        <table className="w-full text-sm" data-testid="previous-cycle-table">
          <tbody>
            <tr className="border-b border-rf-border">
              <td className="px-4 py-2 text-rf-muted text-xs uppercase tracking-[0.12em]">Indicateur</td>
              <td className="px-3 py-2 text-rf-muted text-xs uppercase tracking-[0.12em] text-right">Précédent</td>
              <td className="px-4 py-2 text-rf-blue text-xs uppercase tracking-[0.12em] text-right">Cycle actuel</td>
            </tr>
            <Row label="Conduite totale" prev={fmtH(prev.total_driving_minutes)} curr={fmtH(current.total_driving_minutes)} highlight />
            <Row label="Jours travaillés" prev={prev.days_worked} curr={current.days_worked} />
            <Row label="Repos réduits" prev={`${prev.reduced_rest_used} / 3`} curr={`${current.reduced_rest_used} / 3`} />
            <Row label="Extensions 10h" prev={`${prev.extensions_used} / 2`} curr={`${current.extensions_used} / 2`} />
            <Row label="Découcher" prev={prev.decoucher_count} curr={current.decoucher_count} />
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-rf-muted mt-2 px-1">
        {isLeave
          ? "Période d'absence (≥ 6 jours) — point de remise à zéro pour le cycle actuel."
          : "Cycle de référence pour rester conforme à la réglementation européenne."}
      </p>
    </section>
  );
}

function Row({ label, prev, curr, highlight }) {
  return (
    <tr className="border-b border-rf-border last:border-b-0">
      <td className="px-4 py-2 text-rf-muted">{label}</td>
      <td className="px-3 py-2 text-right tabular-nums">{prev}</td>
      <td className={`px-4 py-2 text-right font-medium tabular-nums ${highlight ? "text-rf-blue" : ""}`}>{curr}</td>
    </tr>
  );
}

function LeavePeriodBanner({ leave }) {
  const fmt = (iso) => {
    if (!iso) return "—";
    const [y, m, d] = iso.split("-");
    return `${d}/${m}/${y}`;
  };
  return (
    <section className="px-4 pt-4" data-testid="leave-period-banner">
      <div className="rf-card border border-rf-orange/30 bg-rf-orange/5 px-4 py-3 flex items-start gap-3">
        <Bed size={20} weight="duotone" className="text-rf-orange shrink-0 mt-0.5" />
        <div className="flex-1">
          <div className="rf-label text-rf-orange">Période d'absence détectée</div>
          <div className="font-display text-xl mt-1" data-testid="leave-period-days">
            {leave.leave_days} jours sans activité
          </div>
          <div className="text-[11px] text-rf-muted mt-1">
            Du {fmt(leave.leave_start_date)} au {fmt(leave.leave_end_date)} · cycle vide enregistré
          </div>
        </div>
      </div>
    </section>
  );
}
