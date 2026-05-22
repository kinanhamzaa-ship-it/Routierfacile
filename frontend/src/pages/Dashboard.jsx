import { useEffect, useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import api from "../lib/api";
import ComplianceBar from "../components/ComplianceBar";
import { useAuth } from "../context/AuthContext";
import { minutesToHM, formatDateFR, weekdayFR, MONTHS_FR } from "../lib/time";
import {
  Plus, SignOut, ForkKnife, Bed, ChartBar, ClipboardText, Clock, Briefcase, Gauge,
} from "@phosphor-icons/react";

export default function Dashboard() {
  const { user, logout } = useAuth();
  const [data, setData] = useState(null);
  const [recent, setRecent] = useState([]);
  const [loading, setLoading] = useState(true);
  const nav = useNavigate();
  const loc = useLocation();

  useEffect(() => {
    setLoading(true);
    Promise.all([api.get("/summary/dashboard"), api.get("/entries", { params: { limit: 5 } })])
      .then(([d, r]) => { setData(d.data); setRecent(r.data); })
      .finally(() => setLoading(false));
  }, [loc.key]);

  if (loading) {
    return <div className="min-h-[60vh] flex items-center justify-center text-rf-muted">Chargement du tableau de bord…</div>;
  }

  const cycle = data.cycle;
  const today = data.today;
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
        <button onClick={logout} data-testid="logout-btn" className="rf-btn-ghost flex items-center gap-2 text-sm" aria-label="Se déconnecter">
          <SignOut size={18} />
        </button>
      </header>

      <div className="px-4 pt-3">
        <Link to="/new" data-testid="cta-new-entry" className="rf-btn-primary w-full flex items-center justify-center gap-2 text-lg">
          <Plus size={22} weight="bold" /> Saisir la journée du {now.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" })}
        </Link>
      </div>

      {/* Today's snapshot */}
      {today && (
        <section className="px-4 pt-6" data-testid="today-section">
          <div className="rf-label mb-3">Aujourd'hui · {weekdayFR(today.date)}</div>
          <div className="grid grid-cols-2 gap-3">
            <SmallTile icon={Clock} label="Amplitude" value={minutesToHM(today.amplitude_minutes)} testid="today-amplitude" />
            <SmallTile icon={Briefcase} label="Heures travaillées" value={minutesToHM(today.total_working_minutes)} testid="today-worked" />
            <SmallTile icon={Gauge} label="Conduite" value={minutesToHM(today.total_driving_minutes)} testid="today-driving" color="rf-blue" />
            <SmallTile icon={Bed} label="Pauses & repos" value={minutesToHM(today.total_rest_minutes)} testid="today-rest" />
          </div>
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
