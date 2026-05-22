import { minutesToHM } from "../lib/time";
import { Bed } from "@phosphor-icons/react";

export default function RestDetectionModal({ detection, onChoice, onClose }) {
  if (!detection) return null;
  const minutes = detection.daily_rest_minutes;
  const type = detection.detection; // "weekly_rest_full" | "weekly_rest_reduced"

  const isFull = type === "weekly_rest_full";
  const title = isFull ? "Repos hebdomadaire détecté" : "Repos hebdomadaire réduit détecté";
  const desc = isFull
    ? `Une période de repos de ${minutesToHM(minutes)} a été détectée (≥ 45h). Souhaitez-vous démarrer un nouveau cycle de travail ?`
    : `Une période de repos de ${minutesToHM(minutes)} a été détectée (entre 24h et 45h). Voulez-vous la classer comme repos hebdomadaire réduit (congés, vacances, repos personnel) ?`;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      data-testid="rest-detection-modal"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="rf-card-elevated w-full max-w-md p-6 animate-fade-in-up">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-md bg-rf-blue/15 text-rf-blue flex items-center justify-center">
            <Bed size={22} weight="duotone" />
          </div>
          <h2 className="font-display text-2xl tracking-tight">{title}</h2>
        </div>
        <p className="text-rf-muted text-sm leading-relaxed">{desc}</p>

        <div className="mt-5 space-y-2">
          {isFull ? (
            <>
              <button
                data-testid="modal-confirm-new-cycle"
                onClick={() => onChoice("start-new")}
                className="rf-btn-primary w-full"
              >
                Oui, démarrer un nouveau cycle
              </button>
              <button
                data-testid="modal-keep-cycle"
                onClick={() => onChoice("ignore")}
                className="rf-btn-ghost w-full"
              >
                Non, garder le cycle actuel
              </button>
            </>
          ) : (
            <>
              <button
                data-testid="modal-confirm-reduced"
                onClick={() => onChoice("confirm-reduced")}
                className="rf-btn-primary w-full"
              >
                Oui, classer en repos réduit
              </button>
              <button
                data-testid="modal-ignore-reduced"
                onClick={() => onChoice("ignore")}
                className="rf-btn-ghost w-full"
              >
                Non, ignorer
              </button>
            </>
          )}
        </div>
        <p className="text-[11px] text-rf-muted mt-4 text-center">
          Routier Facile est un assistant — vous gardez le contrôle de votre cycle.
        </p>
      </div>
    </div>
  );
}
