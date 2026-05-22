import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import api from "../lib/api";
import { minutesToHM, formatDateFR, weekdayFR } from "../lib/time";
import { MagnifyingGlass, Bed, ForkKnife, Warning, Archive } from "@phosphor-icons/react";

const REST_LABEL = {
  ok: { text: "Repos OK", color: "rf-green" },
  reduced: { text: "Repos réduit", color: "rf-orange" },
  warning: { text: "Repos insuffisant", color: "rf-red" },
};

export default function History() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const loc = useLocation();

  useEffect(() => {
    setLoading(true);
    api.get("/entries", { params: { limit: 500 } })
      .then((r) => setEntries(r.data))
      .finally(() => setLoading(false));
  }, [loc.key]);

  const filtered = useMemo(() => {
    if (!q.trim()) return entries;
    const s = q.toLowerCase();
    return entries.filter((e) =>
      e.date.includes(s) ||
      (e.departure || "").toLowerCase().includes(s) ||
      (e.arrival || "").toLowerCase().includes(s) ||
      (e.notes || "").toLowerCase().includes(s)
    );
  }, [entries, q]);

  return (
    <div data-testid="history-page">
      <header className="px-4 pt-5 pb-3">
        <div className="rf-label">Archive</div>
        <h1 className="font-display text-4xl tracking-tight mt-1">Historique</h1>
        <p className="text-rf-muted text-sm mt-1">
          {entries.length} journée{entries.length > 1 ? "s" : ""} enregistrée{entries.length > 1 ? "s" : ""}
        </p>
      </header>

      <div className="px-4 pb-3">
        <div className="relative">
          <MagnifyingGlass size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-rf-muted" />
          <input data-testid="history-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher (date, ville, note…)" className="rf-input w-full pl-10" />
        </div>
      </div>

      {loading ? (
        <div className="text-center text-rf-muted py-12">Chargement…</div>
      ) : filtered.length === 0 ? (
        <div className="px-4">
          <div className="rf-card p-8 text-center" data-testid="history-empty">
            <div className="h-32 rounded-md bg-cover bg-center mb-4 opacity-70"
              style={{ backgroundImage: "url('https://images.pexels.com/photos/11053641/pexels-photo-11053641.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=400&w=600')" }} />
            <p className="text-rf-muted mb-4">Aucune entrée pour le moment.</p>
            <Link to="/new" className="rf-btn-primary inline-flex">Saisir ma première journée</Link>
          </div>
        </div>
      ) : (
        <div className="px-4 space-y-2 pb-6">
          {filtered.map((e) => (
            <Link key={e.id} to={`/edit/${e.id}`} data-testid={`history-item-${e.id}`} className="block rf-tile">
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="rf-label capitalize">{weekdayFR(e.date)}</div>
                    {e.is_legacy && (
                      <span className="rf-label text-rf-muted bg-rf-elevated px-1.5 py-0.5 rounded" data-testid={`legacy-${e.id}`}>
                        <Archive size={9} className="inline mr-0.5" /> Archive
                      </span>
                    )}
                  </div>
                  <div className="font-display text-2xl tracking-tight mt-0.5">{formatDateFR(e.date)}</div>
                  <div className="text-[11px] text-rf-muted uppercase tracking-[0.15em] mt-1">
                    {e.start_time} – {e.end_time}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="font-display text-rf-blue text-2xl">{minutesToHM(e.total_driving_minutes)}</div>
                  <div className="text-[11px] text-rf-muted">conduite</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] mt-2 pt-2 border-t border-rf-border">
                <Row label="Amplitude" value={minutesToHM(e.amplitude_minutes)} />
                <Row label="Heures travaillées" value={minutesToHM(e.total_working_minutes)} />
                <Row label="Pauses & repos" value={minutesToHM(e.total_rest_minutes)} />
                <Row label="Repos précédent" value={
                  e.daily_rest_minutes != null
                    ? `${minutesToHM(e.daily_rest_minutes)}`
                    : "N/A"
                } status={e.daily_rest_status} />
                {(e.departure || e.arrival) && (
                  <div className="col-span-2 text-rf-muted truncate mt-1">{e.departure || "?"} → {e.arrival || "?"}</div>
                )}
              </div>

              <div className="flex items-center flex-wrap gap-3 mt-2 text-[11px] text-rf-muted">
                {e.break_rule_status === "violation" && (
                  <span className="flex items-center gap-1 text-rf-red" data-testid={`break-violation-${e.id}`}>
                    <Warning size={12} /> Pause 4h30/45min
                  </span>
                )}
                {e.is_driving_extension && (
                  <span className="flex items-center gap-1 text-rf-orange" data-testid={`ext-${e.id}`}>
                    <Warning size={12} /> Extension 10h
                  </span>
                )}
                {e.double_equipage && (
                  <span className="flex items-center gap-1 text-rf-blue" data-testid={`co-driver-${e.id}`}>
                    <Warning size={12} /> Double équipage
                  </span>
                )}
                {e.decoucher && (
                  <span className="flex items-center gap-1 text-rf-orange">
                    <Bed size={12} /> Découcher
                  </span>
                )}
                <span className="flex items-center gap-1">
                  <ForkKnife size={12} /> {labelMeal(e.meal_status)}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function Row({ label, value, status }) {
  const meta = status ? REST_LABEL[status] : null;
  return (
    <div className="flex items-baseline justify-between">
      <span className="text-rf-muted">{label}</span>
      <span className={meta ? `text-${meta.color} font-medium` : "text-white font-medium"}>{value}</span>
    </div>
  );
}

function labelMeal(v) {
  if (v === "yes") return "Repas Oui";
  if (v === "no") return "Repas Non";
  return "Repas Pas sûr";
}
