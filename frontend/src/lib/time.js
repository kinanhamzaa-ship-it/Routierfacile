// Time formatting helpers

export function minutesToHM(mins) {
  if (mins == null || isNaN(mins)) return "0h00";
  const sign = mins < 0 ? "-" : "";
  const abs = Math.abs(Math.round(mins));
  const h = Math.floor(abs / 60);
  const m = abs % 60;
  return `${sign}${h}h${String(m).padStart(2, "0")}`;
}

export function parseHmToMinutes(s) {
  if (!s) return 0;
  const str = String(s).trim().replace(",", ".").toLowerCase();
  // Accept "4h20", "4:20", "4.33", "260"
  if (str.includes("h")) {
    const [h, m] = str.split("h");
    return (parseInt(h || "0", 10) || 0) * 60 + (parseInt(m || "0", 10) || 0);
  }
  if (str.includes(":")) {
    const [h, m] = str.split(":");
    return (parseInt(h || "0", 10) || 0) * 60 + (parseInt(m || "0", 10) || 0);
  }
  const n = parseFloat(str);
  if (isNaN(n)) return 0;
  // If decimal, treat as hours
  if (str.includes(".")) return Math.round(n * 60);
  // Otherwise minutes
  return Math.round(n);
}

export function todayIso() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export function formatDateFR(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

export function weekdayFR(iso) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("fr-FR", { weekday: "long" });
}

export const MONTHS_FR = [
  "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
];
