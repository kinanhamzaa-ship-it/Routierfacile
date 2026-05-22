import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { minutesToHM, formatDateFR, weekdayFR } from "../lib/time";
import { MagnifyingGlass, Bed, ForkKnife } from "@phosphor-icons/react";

export default function History() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");

  useEffect(() => {
    api.get("/entries", { params: { limit: 500 } })
      .then((r) => setEntries(r.data))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    if (!q.trim()) return entries;
    const s = q.toLowerCase();
    return entries.filter(
      (e) =>
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
          <MagnifyingGlass
            size={18}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-rf-muted"
          />
          <input
            data-testid="history-search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Rechercher (date, ville, note…)"
            className="rf-input w-full pl-10"
          />
        </div>
      </div>

      {loading ? (
        <div className="text-center text-rf-muted py-12">Chargement…</div>
      ) : filtered.length === 0 ? (
        <div className="px-4">
          <div className="rf-card p-8 text-center" data-testid="history-empty">
            <div
              className="h-32 rounded-md bg-cover bg-center mb-4 opacity-70"
              style={{
                backgroundImage:
                  "url('https://images.pexels.com/photos/11053641/pexels-photo-11053641.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=400&w=600')",
              }}
            />
            <p className="text-rf-muted mb-4">Aucune entrée pour le moment.</p>
            <Link to="/new" className="rf-btn-primary inline-flex">
              Saisir ma première journée
            </Link>
          </div>
        </div>
      ) : (
        <div className="px-4 space-y-2 pb-6">
          {filtered.map((e) => (
            <Link
              key={e.id}
              to={`/edit/${e.id}`}
              data-testid={`history-item-${e.id}`}
              className="block rf-tile"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="rf-label capitalize">{weekdayFR(e.date)}</div>
                  <div className="font-display text-2xl tracking-tight mt-0.5">
                    {formatDateFR(e.date)}
                  </div>
                  {(e.departure || e.arrival) && (
                    <div className="text-sm text-rf-muted truncate mt-1">
                      {e.departure || "?"} → {e.arrival || "?"}
                    </div>
                  )}
                  <div className="flex items-center gap-3 mt-2 text-[11px] text-rf-muted">
                    {e.decoucher && (
                      <span className="flex items-center gap-1 text-rf-orange">
                        <Bed size={12} /> Découcher
                      </span>
                    )}
                    <span className="flex items-center gap-1">
                      <ForkKnife size={12} /> {labelMeal(e.meal_status)}
                    </span>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="font-display text-rf-blue text-2xl">
                    {minutesToHM(e.total_driving_minutes)}
                  </div>
                  <div className="text-[11px] text-rf-muted uppercase tracking-[0.15em]">
                    {e.start_time}–{e.end_time}
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function labelMeal(v) {
  if (v === "yes") return "Repas Oui";
  if (v === "no") return "Repas Non";
  return "Repas Pas sûr";
}
