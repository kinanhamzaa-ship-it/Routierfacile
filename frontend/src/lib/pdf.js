import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import { minutesToHM, formatDateFR, MONTHS_FR } from "./time";

export function exportMonthlyPdf({ year, month, summary, driverName }) {
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  const title = `Routier Facile - ${MONTHS_FR[month - 1]} ${year}`;
  doc.setFontSize(18);
  doc.text(title, 40, 50);
  doc.setFontSize(10);
  doc.setTextColor(120);
  doc.text(`Conducteur : ${driverName || "—"}`, 40, 68);
  doc.text(`Généré le ${new Date().toLocaleString("fr-FR")}`, 40, 82);

  doc.setTextColor(0);
  doc.setFontSize(12);
  doc.text("Résumé mensuel", 40, 110);

  const stats = [
    ["Jours travaillés", String(summary.working_days)],
    ["Conduite totale", minutesToHM(summary.total_driving_minutes)],
    ["Travail total", minutesToHM(summary.total_working_minutes)],
    ["Repos & pauses", minutesToHM(summary.total_rest_minutes)],
    ["Découcher", String(summary.decoucher_count)],
    ["Repas OUI", String(summary.meal_counts.yes)],
    ["Repas NON", String(summary.meal_counts.no)],
    ["Repas Pas sûr", String(summary.meal_counts.unsure)],
  ];

  autoTable(doc, {
    startY: 120,
    head: [["Indicateur", "Valeur"]],
    body: stats,
    theme: "grid",
    headStyles: { fillColor: [20, 20, 20], textColor: 255 },
    styles: { fontSize: 10 },
  });

  const rows = (summary.entries || []).map((e) => [
    formatDateFR(e.date),
    `${e.start_time}\n${e.end_time}`,
    minutesToHM(e.amplitude_minutes),
    minutesToHM(e.total_working_minutes),
    minutesToHM(e.total_driving_minutes),
    minutesToHM(e.total_rest_minutes),
    e.daily_rest_minutes != null ? minutesToHM(e.daily_rest_minutes) : "N/A",
    `${e.departure || ""}\n→ ${e.arrival || ""}`,
    e.decoucher ? "Oui" : "Non",
    e.meal_status === "yes" ? "Oui" : e.meal_status === "no" ? "Non" : "Pas sûr",
  ]);

  autoTable(doc, {
    head: [["Date", "Horaires", "Amplitude", "Travail", "Conduite", "Pauses", "Repos prec.", "Trajet", "Découcher", "Repas"]],
    body: rows,
    theme: "striped",
    headStyles: { fillColor: [0, 122, 255], textColor: 255 },
    styles: { fontSize: 7, cellPadding: 3 },
    startY: doc.lastAutoTable.finalY + 20,
  });

  doc.save(`routier-facile-${year}-${String(month).padStart(2, "0")}.pdf`);
}
