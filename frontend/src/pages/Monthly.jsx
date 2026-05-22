import { useEffect, useState } from "react";
import api from "../lib/api";
import { minutesToHM, MONTHS_FR } from "../lib/time";
import { exportMonthlyPdf } from "../lib/pdf";
import { useAuth } from "../context/AuthContext";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { DownloadSimple, CaretLeft, CaretRight } from "@phosphor-icons/react";

export default function Monthly() {
  const { user } = useAuth();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get("/summary/month", { params: { year, month } })
      .then((r) => setData(r.data))
      .finally(() => setLoading(false));
  }, [year, month]);

  const shift = (delta) => {
    let m = month + delta;
    let y = year;
    if (m < 1) { m = 12; y -= 1; }
    if (m > 12) { m = 1; y += 1; }
    setMonth(m); setYear(y);
  };

  const chartData = (data?.entries || []).map((e) => ({
    day: e.date.slice(-2),
    conduite: +(e.total_driving_minutes / 60).toFixed(2),
    travail: +(e.total_working_minutes / 60).toFixed(2),
  }));

  return (
    <div data-testid="monthly-page">
      <header className="px-4 pt-5 pb-3 flex items-center justify-between">
        <div>
          <div className="rf-label">Rapport</div>
          <h1 className="font-display text-4xl tracking-tight mt-1">
            {MONTHS_FR[month - 1]} {year}
          </h1>
        </div>
        <div className="flex items-center gap-1">
          <button data-testid="month-prev" onClick={() => shift(-1)} className="rf-btn-ghost px-3 py-2">
            <CaretLeft size={18} />
          </button>
          <button data-testid="month-next" onClick={() => shift(1)} className="rf-btn-ghost px-3 py-2">
            <CaretRight size={18} />
          </button>
        </div>
      </header>

      {loading || !data ? (
        <div className="text-center text-rf-muted py-12">Chargement…</div>
      ) : (
        <div className="px-4 space-y-5 pb-6">
          {/* Headline */}
          <div className="grid grid-cols-3 gap-3">
            <Stat label="Conduite" value={minutesToHM(data.total_driving_minutes)} color="rf-blue" testid="stat-driving" />
            <Stat label="Travail" value={minutesToHM(data.total_working_minutes)} testid="stat-work" />
            <Stat label="Repos" value={minutesToHM(data.total_rest_minutes)} testid="stat-rest" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Stat label="Jours travaillés" value={data.working_days} testid="stat-days" />
            <Stat label="Découcher" value={data.decoucher_count} color="rf-orange" testid="stat-decoucher" />
          </div>

          {/* Meals */}
          <div className="rf-card p-4" data-testid="meal-summary">
            <div className="rf-label mb-3">Indemnité repas</div>
            <div className="grid grid-cols-3 gap-3">
              <MealStat label="OUI" value={data.meal_counts.yes} color="rf-green" testid="meal-yes" />
              <MealStat label="NON" value={data.meal_counts.no} color="rf-red" testid="meal-no" />
              <MealStat label="PAS SÛR" value={data.meal_counts.unsure} color="rf-orange" testid="meal-unsure" />
            </div>
          </div>

          {/* Chart */}
          {chartData.length > 0 && (
            <div className="rf-card p-4">
              <div className="rf-label mb-3">Heures par jour</div>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <XAxis dataKey="day" stroke="#A1A1AA" fontSize={11} />
                    <YAxis stroke="#A1A1AA" fontSize={11} />
                    <Tooltip
                      contentStyle={{ background: "#141414", border: "1px solid #27272A", borderRadius: 8, color: "#fff" }}
                      labelStyle={{ color: "#A1A1AA" }}
                    />
                    <Bar dataKey="conduite" name="Conduite (h)" fill="#007AFF" radius={[3, 3, 0, 0]}>
                      {chartData.map((c) => <Cell key={c.day} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          <button
            data-testid="export-pdf"
            onClick={() => exportMonthlyPdf({ year, month, summary: data, driverName: user?.name || user?.email })}
            className="rf-btn-primary w-full flex items-center justify-center gap-2"
          >
            <DownloadSimple size={20} /> Exporter en PDF
          </button>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color = "rf-blue", testid }) {
  return (
    <div className="rf-tile" data-testid={testid}>
      <div className="rf-label">{label}</div>
      <div className={`font-display text-2xl tracking-tight mt-1 text-${color}`}>{value}</div>
    </div>
  );
}

function MealStat({ label, value, color, testid }) {
  return (
    <div className="bg-rf-elevated rounded-md p-3 text-center" data-testid={testid}>
      <div className={`text-${color} text-xs font-medium tracking-[0.15em]`}>{label}</div>
      <div className="font-display text-3xl mt-1">{value}</div>
    </div>
  );
}
