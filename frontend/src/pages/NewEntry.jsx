import { useState } from "react";
import { useNavigate } from "react-router-dom";
import EntryForm from "../components/EntryForm";
import RestDetectionModal from "../components/RestDetectionModal";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { ArrowLeft } from "@phosphor-icons/react";

export default function NewEntry() {
  const nav = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [pendingPayload, setPendingPayload] = useState(null);
  const [detection, setDetection] = useState(null);
  const [maxDaysPrompt, setMaxDaysPrompt] = useState(null); // { payload, maxDays }

  const persist = async (data) => {
    setSubmitting(true);
    try {
      await api.post("/entries", data);
      toast.success("Journée enregistrée");
      nav("/", { replace: true });
    } catch (e) {
      const detail = e.response?.data?.detail;
      if (detail && typeof detail === "object" && detail.code === "cycle_max_days_reached") {
        setMaxDaysPrompt({
          maxDays: detail.max_days,
          title: detail.title,
          headline: detail.headline,
          message: detail.message,
        });
      } else {
        toast.error(formatApiError(detail) || "Erreur");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const onSubmit = async (data) => {
    setSubmitting(true);
    try {
      const { data: det } = await api.post("/cycles/detect-rest", {
        date: data.date,
        start_time: data.start_time,
      });
      if (det?.detection) {
        setPendingPayload(data);
        setDetection(det);
        setSubmitting(false);
        return;
      }
      await persist(data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Erreur");
      setSubmitting(false);
    }
  };

  const confirmDetection = async (action) => {
    // action: "start-new" | "confirm-reduced" | "ignore"
    try {
      const body = pendingPayload
        ? { date: pendingPayload.date, start_time: pendingPayload.start_time }
        : null;
      if (action === "start-new") {
        await api.post("/cycles/start-new", body);
      } else if (action === "confirm-reduced") {
        await api.post("/cycles/confirm-reduced", body);
      }
      setDetection(null);
      const p = pendingPayload;
      setPendingPayload(null);
      await persist(p);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Erreur");
    }
  };

  return (
    <div data-testid="new-entry-page">
      <header className="px-4 pt-5 pb-2 flex items-center gap-3">
        <button onClick={() => nav(-1)} className="rf-btn-ghost px-3 py-2" data-testid="back-btn" aria-label="Retour">
          <ArrowLeft size={18} />
        </button>
        <div>
          <div className="rf-label">Saisie</div>
          <h1 className="font-display text-3xl tracking-tight mt-0.5">Nouvelle journée</h1>
        </div>
      </header>
      <EntryForm onSubmit={onSubmit} submitting={submitting} />
      <RestDetectionModal detection={detection} onChoice={confirmDetection} onClose={() => { setDetection(null); setPendingPayload(null); }} />
      {maxDaysPrompt && (
        <MaxDaysModal prompt={maxDaysPrompt} onClose={() => setMaxDaysPrompt(null)} />
      )}
    </div>
  );
}

function MaxDaysModal({ prompt, onClose }) {
  const headline = prompt.headline || `${prompt.maxDays} jours travaillés`;
  const title = prompt.title || "Limite du cycle atteinte";
  return (
    <div
      data-testid="max-days-modal"
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center px-4 pb-28 sm:pb-0"
      onClick={onClose}
    >
      <div
        className="rf-card max-w-md w-full p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="rf-label text-rf-orange">{title}</div>
        <h2 className="font-display text-2xl mt-1" data-testid="max-days-headline">{headline}</h2>
        <p className="text-sm text-rf-muted mt-3 whitespace-pre-line">
          {prompt.message}
        </p>
        <button
          data-testid="max-days-acknowledge"
          onClick={onClose}
          className="rf-btn-primary w-full mt-5"
        >
          J'ai compris
        </button>
      </div>
    </div>
  );
}
