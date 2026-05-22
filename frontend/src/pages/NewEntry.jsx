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

  const persist = async (data) => {
    setSubmitting(true);
    try {
      await api.post("/entries", data);
      toast.success("Journée enregistrée");
      nav("/", { replace: true });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Erreur");
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
      if (action === "start-new") {
        await api.post("/cycles/start-new");
      } else if (action === "confirm-reduced") {
        await api.post("/cycles/confirm-reduced");
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
    </div>
  );
}
