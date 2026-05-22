import { useMemo, useState } from "react";
import { Plus, Trash, ArrowRight, Clock, Briefcase } from "@phosphor-icons/react";
import { parseHmToMinutes, minutesToHM, todayIso } from "../lib/time";

const MEAL_OPTIONS = [
  { v: "yes", label: "OUI", color: "rf-green" },
  { v: "no", label: "NON", color: "rf-red" },
  { v: "unsure", label: "PAS SÛR", color: "rf-orange" },
];

function minutesToText(m) {
  if (!m) return "";
  const h = Math.floor(m / 60);
  const min = m % 60;
  return `${h}h${String(min).padStart(2, "0")}`;
}

function amplitudeMinutes(start, end) {
  if (!start || !end) return 0;
  const [sh, sm] = start.split(":").map((n) => parseInt(n, 10) || 0);
  const [eh, em] = end.split(":").map((n) => parseInt(n, 10) || 0);
  let s = sh * 60 + sm;
  let e = eh * 60 + em;
  if (e < s) e += 24 * 60;
  return e - s;
}

function computeBreakRule(drivingMins, restMins) {
  let accDrive = 0, accBreak = 0, hasHalf = false, maxAcc = 0;
  for (let i = 0; i < drivingMins.length; i++) {
    accDrive += drivingMins[i] || 0;
    if (accDrive > maxAcc) maxAcc = accDrive;
    if (i < restMins.length) {
      const b = restMins[i] || 0;
      accBreak += b;
      if (b >= 30) hasHalf = true;
      if (accBreak >= 45 && hasHalf) {
        accDrive = 0; accBreak = 0; hasHalf = false;
      }
    }
  }
  return { maxConsecutive: maxAcc, violation: maxAcc > 4 * 60 + 30 };
}

function makeItem(value = "") {
  return { id: Math.random().toString(36).slice(2) + Date.now().toString(36), value };
}

export default function EntryForm({ initial, onSubmit, submitting }) {
  const [date, setDate] = useState(initial?.date || todayIso());
  const [startTime, setStartTime] = useState(initial?.start_time || "06:00");
  const [endTime, setEndTime] = useState(initial?.end_time || "18:00");
  const [drivingInputs, setDrivingInputs] = useState(
    initial?.driving_segments?.length
      ? initial.driving_segments.map((m) => makeItem(minutesToText(m)))
      : [makeItem()]
  );
  const [restInputs, setRestInputs] = useState(
    initial?.rest_breaks?.length
      ? initial.rest_breaks.map((m) => makeItem(minutesToText(m)))
      : [makeItem()]
  );
  const [departure, setDeparture] = useState(initial?.departure || "");
  const [arrival, setArrival] = useState(initial?.arrival || "");
  const [notes, setNotes] = useState(initial?.notes || "");
  const [decoucher, setDecoucher] = useState(!!initial?.decoucher);
  const [meal, setMeal] = useState(initial?.meal_status || "unsure");
  const [doubleEquipage, setDoubleEquipage] = useState(!!initial?.double_equipage);

  const updateArr = (arr, setArr, id, val) => {
    setArr(arr.map((it) => (it.id === id ? { ...it, value: val } : it)));
  };
  const addItem = (arr, setArr) => setArr([...arr, makeItem()]);
  const removeItem = (arr, setArr, id) => setArr(arr.filter((it) => it.id !== id));

  const totals = useMemo(() => {
    const drivingArr = drivingInputs.map((it) => parseHmToMinutes(it.value));
    const restArr = restInputs.map((it) => parseHmToMinutes(it.value));
    const driving = drivingArr.reduce((s, x) => s + x, 0);
    const rest = restArr.reduce((s, x) => s + x, 0);
    const amp = amplitudeMinutes(startTime, endTime);
    const worked = Math.max(amp - rest, 0);
    const isExtension = driving > 9 * 60 && driving <= 10 * 60;
    const isOverDriving = driving > 10 * 60;
    const breakRule = computeBreakRule(drivingArr, restArr);
    return { driving, rest, amp, worked, isExtension, isOverDriving, breakRule };
  }, [drivingInputs, restInputs, startTime, endTime]);

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({
      date,
      start_time: startTime,
      end_time: endTime,
      driving_segments: drivingInputs.map((it) => parseHmToMinutes(it.value)).filter((m) => m > 0),
      rest_breaks: restInputs.map((it) => parseHmToMinutes(it.value)).filter((m) => m > 0),
      departure, arrival, notes, decoucher, meal_status: meal,
      double_equipage: doubleEquipage,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="px-4 py-5 pb-24 space-y-5" data-testid="entry-form">
      {/* Live calculation banner */}
      <div className="rf-card-elevated p-4 grid grid-cols-2 gap-3 sticky top-0 z-10 animate-fade-in-up" data-testid="live-totals">
        <LiveStat icon={Clock} label="Amplitude" value={minutesToHM(totals.amp)} testid="live-amplitude" />
        <LiveStat icon={Briefcase} label="Heures travaillées" value={minutesToHM(totals.worked)} testid="live-worked" />
        <LiveStat label="Conduite" value={minutesToHM(totals.driving)} testid="live-driving" color={totals.isOverDriving ? "rf-red" : totals.isExtension ? "rf-orange" : "rf-blue"} />
        <LiveStat label="Pauses & repos" value={minutesToHM(totals.rest)} testid="live-rest" />
        {totals.isExtension && (
          <div className="col-span-2 text-xs text-rf-orange flex items-center gap-2" data-testid="extension-warning">
            <span className="rf-status-dot bg-rf-orange" /> Conduite &gt; 9h : compteur extension 10h
          </div>
        )}
        {totals.isOverDriving && (
          <div className="col-span-2 text-xs text-rf-red flex items-center gap-2" data-testid="overdriving-warning">
            <span className="rf-status-dot bg-rf-red" /> Conduite &gt; 10h : limite quotidienne dépassée
          </div>
        )}
        {totals.breakRule.violation && (
          <div className="col-span-2 text-xs text-rf-red flex items-center gap-2" data-testid="breakrule-warning">
            <span className="rf-status-dot bg-rf-red" /> Règle 4h30 / 45 min non respectée
            ({minutesToHM(totals.breakRule.maxConsecutive)} sans pause qualifiante)
          </div>
        )}
        {!totals.breakRule.violation && totals.driving > 0 && (
          <div className="col-span-2 text-xs text-rf-green flex items-center gap-2" data-testid="breakrule-ok">
            <span className="rf-status-dot bg-rf-green" /> Règle 4h30 / 45 min respectée
          </div>
        )}
      </div>

      <Section title="Jour" testid="section-date">
        <input data-testid="entry-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} className="rf-input w-full" />
      </Section>

      <Section title="Horaires" testid="section-times">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="rf-label mb-2">Début</div>
            <input data-testid="entry-start-time" type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} className="rf-input w-full" />
          </div>
          <div>
            <div className="rf-label mb-2">Fin</div>
            <input data-testid="entry-end-time" type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} className="rf-input w-full" />
          </div>
        </div>
      </Section>

      <Section title="Périodes de conduite" testid="section-driving" accent={minutesToHM(totals.driving)}>
        <p className="text-xs text-rf-muted mb-3">Format : <span className="text-white">4h20</span>, <span className="text-white">3:30</span>, ou minutes</p>
        <div className="space-y-2">
          {drivingInputs.map((it, i) => (
            <div key={it.id} className="flex gap-2">
              <input data-testid={`driving-segment-${i}`} value={it.value} onChange={(e) => updateArr(drivingInputs, setDrivingInputs, it.id, e.target.value)} placeholder="ex: 4h20" className="rf-input flex-1" />
              {drivingInputs.length > 1 && (
                <button type="button" data-testid={`remove-driving-${i}`} onClick={() => removeItem(drivingInputs, setDrivingInputs, it.id)} className="rf-btn-ghost px-3" aria-label="Supprimer">
                  <Trash size={18} />
                </button>
              )}
            </div>
          ))}
          <button type="button" data-testid="add-driving" onClick={() => addItem(drivingInputs, setDrivingInputs)} className="rf-btn-ghost w-full flex items-center justify-center gap-2">
            <Plus size={16} /> Ajouter une période
          </button>
        </div>
      </Section>

      <Section title="Pauses & repos" testid="section-rest" accent={minutesToHM(totals.rest)}>
        <div className="space-y-2">
          {restInputs.map((it, i) => (
            <div key={it.id} className="flex gap-2">
              <input data-testid={`rest-break-${i}`} value={it.value} onChange={(e) => updateArr(restInputs, setRestInputs, it.id, e.target.value)} placeholder="ex: 45 ou 0h45" className="rf-input flex-1" />
              {restInputs.length > 1 && (
                <button type="button" data-testid={`remove-rest-${i}`} onClick={() => removeItem(restInputs, setRestInputs, it.id)} className="rf-btn-ghost px-3">
                  <Trash size={18} />
                </button>
              )}
            </div>
          ))}
          <button type="button" data-testid="add-rest" onClick={() => addItem(restInputs, setRestInputs)} className="rf-btn-ghost w-full flex items-center justify-center gap-2">
            <Plus size={16} /> Ajouter une pause
          </button>
        </div>
      </Section>

      <Section title="Trajet" testid="section-trip">
        <div className="grid grid-cols-1 gap-3">
          <input data-testid="entry-departure" value={departure} onChange={(e) => setDeparture(e.target.value)} placeholder="Ville de départ" className="rf-input" />
          <div className="flex justify-center text-rf-muted"><ArrowRight size={20} /></div>
          <input data-testid="entry-arrival" value={arrival} onChange={(e) => setArrival(e.target.value)} placeholder="Ville d'arrivée" className="rf-input" />
          <textarea data-testid="entry-notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Notes (livraison, retard, cargaison…)" rows={3} className="rf-input" />
        </div>
      </Section>

      <Section title="Double équipage" testid="section-double-equipage">
        <p className="text-xs text-rf-muted mb-3 leading-relaxed">
          En double équipage, une période de relais de 45 minutes avec l'autre conducteur permet
          de reprendre un nouveau cycle de conduite de 4h30. Le temps de travail reste soumis
          aux règles du Code du travail, notamment la pause obligatoire de 30 minutes.
        </p>
        <div className="grid grid-cols-2 gap-2">
          <Toggle testid="double-equipage-yes" active={doubleEquipage} onClick={() => setDoubleEquipage(true)} label="Oui" color="rf-blue" />
          <Toggle testid="double-equipage-no" active={!doubleEquipage} onClick={() => setDoubleEquipage(false)} label="Non" color="rf-green" />
        </div>
      </Section>

      <Section title="Découcher" testid="section-decoucher">
        <div className="grid grid-cols-2 gap-2">
          <Toggle testid="decoucher-yes" active={decoucher} onClick={() => setDecoucher(true)} label="Oui" color="rf-orange" />
          <Toggle testid="decoucher-no" active={!decoucher} onClick={() => setDecoucher(false)} label="Non" color="rf-green" />
        </div>
      </Section>

      <Section title="Indemnité repas" testid="section-meal">
        <div className="grid grid-cols-3 gap-2">
          {MEAL_OPTIONS.map((o) => (
            <Toggle key={o.v} testid={`meal-${o.v}`} active={meal === o.v} onClick={() => setMeal(o.v)} label={o.label} color={o.color} />
          ))}
        </div>
      </Section>

      <button type="submit" data-testid="submit-entry" disabled={submitting} className="rf-btn-primary w-full text-lg disabled:opacity-50">
        {submitting ? "Enregistrement…" : "Enregistrer la journée"}
      </button>
    </form>
  );
}

function Section({ title, children, testid, accent }) {
  return (
    <section data-testid={testid} className="rf-card p-4 animate-fade-in-up">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-display text-xl tracking-tight">{title}</h2>
        {accent && <span className="font-display text-rf-blue text-lg">{accent}</span>}
      </div>
      {children}
    </section>
  );
}

function Toggle({ active, onClick, label, color, testid }) {
  return (
    <button type="button" onClick={onClick} data-testid={testid}
      className={`py-3 px-3 rounded-md border text-sm font-medium tracking-wide transition-colors ${
        active ? `bg-${color} text-black border-transparent` : "bg-rf-elevated border-rf-border text-white hover:border-rf-blue/50"
      }`}>
      {label}
    </button>
  );
}

function LiveStat({ icon: Icon, label, value, testid, color = "rf-blue" }) {
  return (
    <div className="bg-rf-surface border border-rf-border rounded-md p-3" data-testid={testid}>
      <div className="flex items-center gap-1.5">
        {Icon && <Icon size={12} className="text-rf-muted" />}
        <span className="rf-label">{label}</span>
      </div>
      <div className={`font-display text-2xl tracking-tight mt-1 text-${color}`}>{value}</div>
    </div>
  );
}
