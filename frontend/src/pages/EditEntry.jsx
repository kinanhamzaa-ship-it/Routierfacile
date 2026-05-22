import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import EntryForm from "../components/EntryForm";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { ArrowLeft, Trash } from "@phosphor-icons/react";

export default function EditEntry() {
  const { id } = useParams();
  const nav = useNavigate();
  const [entry, setEntry] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get(`/entries/${id}`).then((r) => setEntry(r.data)).catch(() => {
      toast.error("Entrée introuvable");
      nav("/history");
    });
  }, [id, nav]);

  const onSubmit = async (data) => {
    setSubmitting(true);
    try {
      await api.put(`/entries/${id}`, data);
      toast.success("Journée mise à jour");
      nav("/history", { replace: true });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Erreur");
    } finally {
      setSubmitting(false);
    }
  };

  const onDelete = async () => {
    if (!window.confirm("Supprimer cette journée définitivement ?")) return;
    try {
      const { data } = await api.delete(`/entries/${id}`);
      if (data?.reverted_to_cycle) {
        toast.success("Journée supprimée — retour au cycle précédent");
      } else {
        toast.success("Journée supprimée");
      }
      nav("/history", { replace: true });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Erreur");
    }
  };

  if (!entry) {
    return <div className="min-h-[40vh] flex items-center justify-center text-rf-muted">Chargement…</div>;
  }

  return (
    <div data-testid="edit-entry-page">
      <header className="px-4 pt-5 pb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => nav(-1)}
            className="rf-btn-ghost px-3 py-2"
            data-testid="back-btn"
            aria-label="Retour"
          >
            <ArrowLeft size={18} />
          </button>
          <div>
            <div className="rf-label">Modifier</div>
            <h1 className="font-display text-3xl tracking-tight mt-0.5">{entry.date}</h1>
          </div>
        </div>
        <button
          onClick={onDelete}
          className="rf-btn-ghost text-rf-red px-3"
          data-testid="delete-entry"
          aria-label="Supprimer"
        >
          <Trash size={18} />
        </button>
      </header>
      <EntryForm initial={entry} onSubmit={onSubmit} submitting={submitting} />
    </div>
  );
}
