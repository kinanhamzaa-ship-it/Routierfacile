import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import { minutesToHM, formatDateFR, MONTHS_FR } from "./time";

export function exportMonthlyPdf({ year, month, summary, driverName }) {
  const doc = new jsPDF({ unit: "pt", format: "a4", orientation: "landscape" });
  const title = `Routier Facile - ${MONTHS_FR[month - 1]} ${year}`;
  const generatedAt = new Date().toLocaleString("fr-FR");

  // === Header ===
  doc.setFontSize(18);
  doc.setTextColor(20);
  doc.text(title, 40, 50);
  doc.setFontSize(10);
  doc.setTextColor(120);
  doc.text(`Conducteur : ${driverName || "—"}`, 40, 68);
  doc.text(`Généré le ${generatedAt}`, 40, 82);

  // === Summary block ===
  doc.setTextColor(0);
  doc.setFontSize(12);
  doc.text("Résumé mensuel", 40, 110);

  const doubleEquipageDays = (summary.entries || []).filter((e) => e.double_equipage).length;
  const stats = [
    ["Jours travaillés", String(summary.working_days)],
    ["Conduite totale", minutesToHM(summary.total_driving_minutes)],
    ["Travail total", minutesToHM(summary.total_working_minutes)],
    ["Pauses & repos", minutesToHM(summary.total_rest_minutes)],
    ["Découcher", String(summary.decoucher_count)],
    ["Jours en double équipage", String(doubleEquipageDays)],
    ["Repas OUI", String(summary.meal_counts.yes)],
    ["Repas NON", String(summary.meal_counts.no)],
    ["Repas Pas sûr", String(summary.meal_counts.unsure)],
  ];

  autoTable(doc, {
    startY: 120,
    head: [["Indicateur", "Valeur"]],
    body: stats,
    theme: "grid",
    headStyles: { fillColor: [20, 20, 20], textColor: 255, fontStyle: "bold" },
    styles: { fontSize: 10, cellPadding: 5 },
    columnStyles: { 0: { cellWidth: 180 }, 1: { cellWidth: 100, halign: "right" } },
    margin: { left: 40, right: 40 },
  });

  // === Daily detail table ===
  const rows = (summary.entries || []).map((e) => [
    formatDateFR(e.date),
    `${e.start_time} – ${e.end_time}`,
    minutesToHM(e.amplitude_minutes),
    minutesToHM(e.total_working_minutes),
    minutesToHM(e.total_driving_minutes),
    minutesToHM(e.total_rest_minutes),
    e.daily_rest_minutes != null ? minutesToHM(e.daily_rest_minutes) : "N/A",
    e.break_rule_status === "violation" ? "Pause insuf." : "Conforme",
    e.double_equipage ? "Double" : "Solo",
    `${e.departure || "—"}\n→ ${e.arrival || "—"}`,
    e.decoucher ? "Oui" : "Non",
    e.meal_status === "yes" ? "Oui" : e.meal_status === "no" ? "Non" : "Pas sûr",
  ]);

  const breakColIndex = 7;
  const equipageColIndex = 8;

  autoTable(doc, {
    head: [[
      "Date",
      "Horaires",
      "Amplitude",
      "Travail",
      "Conduite",
      "Pauses",
      "Repos journalier",
      "Pause 4h30",
      "Équipage",
      "Trajet",
      "Découcher",
      "Repas",
    ]],
    body: rows,
    theme: "striped",
    headStyles: {
      fillColor: [0, 122, 255],
      textColor: 255,
      fontStyle: "bold",
      fontSize: 8,
      halign: "center",
      valign: "middle",
      cellPadding: 4,
    },
    bodyStyles: { fontSize: 8, cellPadding: 4, valign: "middle" },
    alternateRowStyles: { fillColor: [248, 250, 252] },
    styles: { overflow: "linebreak", lineColor: [220, 224, 230], lineWidth: 0.3 },
    columnStyles: {
      0: { cellWidth: 56, halign: "center" },              // Date
      1: { cellWidth: 56, halign: "center" },              // Horaires
      2: { cellWidth: 48, halign: "right" },               // Amplitude
      3: { cellWidth: 48, halign: "right" },               // Travail
      4: { cellWidth: 48, halign: "right" },               // Conduite
      5: { cellWidth: 48, halign: "right" },               // Pauses
      6: { cellWidth: 64, halign: "right" },               // Repos journalier
      7: { cellWidth: 72, halign: "center", fontStyle: "bold" }, // Pause 4h30
      8: { cellWidth: 54, halign: "center" },              // Équipage
      9: { cellWidth: 138, halign: "left" },               // Trajet
      10: { cellWidth: 52, halign: "center" },             // Découcher
      11: { cellWidth: 50, halign: "center" },             // Repas
    },
    startY: doc.lastAutoTable.finalY + 24,
    margin: { left: 40, right: 40, bottom: 50 },
    didParseCell: (data) => {
      if (data.section === "body" && data.column.index === breakColIndex) {
        const val = String(data.cell.raw || "");
        if (val.startsWith("Pause insuf")) {
          data.cell.styles.textColor = [220, 38, 38];
          data.cell.styles.fillColor = [254, 226, 226];
        } else if (val === "Conforme") {
          data.cell.styles.textColor = [22, 101, 52];
          data.cell.styles.fillColor = [220, 252, 231];
        }
      }
      if (data.section === "body" && data.column.index === equipageColIndex) {
        const val = String(data.cell.raw || "");
        if (val === "Double") {
          data.cell.styles.textColor = [29, 78, 216];
          data.cell.styles.fillColor = [219, 234, 254];
          data.cell.styles.fontStyle = "bold";
        }
      }
    },
    // === Footer on every page ===
    didDrawPage: (data) => {
      const pageSize = doc.internal.pageSize;
      const pageHeight = pageSize.height || pageSize.getHeight();
      const pageWidth = pageSize.width || pageSize.getWidth();
      const pageNumber = doc.internal.getNumberOfPages
        ? doc.internal.getNumberOfPages()
        : 1;

      doc.setDrawColor(220, 224, 230);
      doc.setLineWidth(0.5);
      doc.line(40, pageHeight - 32, pageWidth - 40, pageHeight - 32);

      doc.setFontSize(8);
      doc.setTextColor(140);
      doc.text("Document généré par Routier Facile", 40, pageHeight - 20);
      doc.text(generatedAt, pageWidth / 2, pageHeight - 20, { align: "center" });
      doc.text(`Page ${pageNumber}`, pageWidth - 40, pageHeight - 20, { align: "right" });
    },
  });

  doc.save(`routier-facile-${year}-${String(month).padStart(2, "0")}.pdf`);
}
