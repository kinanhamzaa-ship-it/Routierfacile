import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  ArrowLeft,
  Trash,
  Warning,
  SignOut,
  UserCircle,
  Crown,
  Lifebuoy,
  Database,
  Info,
} from "@phosphor-icons/react";
import { toast } from "sonner";

function getPlanLabel(plan) {
  if (plan === "admin") return "Admin";
  if (plan === "premium") return "Premium";
  return "Gratuit";
}

function getPlanBadgeClass(plan) {
  if (plan === "admin") return "bg-rf-blue/20 text-rf-blue";
  if (plan === "premium") return "bg-rf-green/20 text-rf-green";
  return "bg-rf-muted/15 text-rf-muted";
}

export default function Account() {
  const { user, logout, deleteAccount } = useAuth();
  const nav = useNavigate();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const plan = user?.plan || "free";
  const planLabel = getPlanLabel(plan);

  const handleDelete = async (e) => {
    e.preventDefault();
    setError("");

    if (!password) {
      setError("Veuillez saisir votre mot de passe pour confirmer.");
      return;
    }

    setSubmitting(true);
    const r = await deleteAccount(password);
    setSubmitting(false);

    if (r.ok) {
      toast.success("Votre compte a été supprimé.");
      nav("/login", { replace: true });
    } else {
      setError(r.message || "Échec de la suppression.");
    }
  };

  return (
    <div data-testid="account-page">
      <header className="px-4 pt-5 pb-2 flex items-center gap-3">
        <button
          onClick={() => nav(-1)}
          className="rf-btn-ghost px-3 py-2"
          data-testid="account-back-btn"
          aria-label="Retour"
        >
          <ArrowLeft size={18} />
        </button>
        <div>
          <div className="rf-label">Compte</div>
          <h1 className="font-display text-3xl tracking-tight mt-0.5">Mon compte</h1>
        </div>
      </header>

      <section className="px-4 mt-4">
        <div className="rf-card p-4">
          <div className="flex items-start gap-3">
            <UserCircle size={34} weight="duotone" className="text-rf-blue shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <div className="rf-label">Connecté en tant que</div>
              <div className="font-display text-2xl mt-1 break-words" data-testid="account-email">
                {user?.email || "—"}
              </div>
              {user?.name && (
                <div className="text-rf-muted text-sm mt-1">{user.name}</div>
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="px-4 mt-4">
        <div className="rf-card p-4">
          <div className="flex items-start gap-3">
            <Crown size={28} weight="duotone" className="text-rf-orange shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="rf-label">Plan actuel</div>
              <div className="flex items-center justify-between gap-3 mt-2">
                <div>
                  <div className="font-display text-2xl">{planLabel}</div>
                  <div className="text-rf-muted text-sm mt-1">
                    Les options Premium seront ajoutées progressivement.
                  </div>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${getPlanBadgeClass(plan)}`}>
                  {planLabel}
                </span>
              </div>

              
              {plan === "admin" && (
                <div className="mt-4 rounded-xl border border-rf-blue/30 bg-rf-blue/10 p-3">
                  <div className="text-sm font-medium text-rf-blue">
                    Administration
                  </div>
                  <button
                    onClick={() => nav("/admin")}
                    className="rf-btn-primary w-full mt-3"
                  >
                    Ouvrir le panneau Admin
                  </button>
                </div>
              )}

              {plan === "free" && (
                <div className="mt-4 rounded-xl border border-rf-border bg-rf-elevated/40 p-3">
                  <div className="text-sm font-medium">Premium bientôt disponible</div>
                  <div className="text-rf-muted text-xs mt-1">
                    Historique illimité, sauvegarde, alertes avancées et support prioritaire.
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="px-4 mt-4">
        <div className="rf-card p-4">
          <div className="flex items-start gap-3">
            <Database size={28} weight="duotone" className="text-rf-blue shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="rf-label">Synchronisation Cloud</div>

              <p className="text-rf-muted text-sm mt-2">
                Vos données sont automatiquement synchronisées avec votre compte.
              </p>

              <p className="text-rf-muted text-sm mt-3">
                Connectez-vous simplement sur un autre appareil pour retrouver vos journées,
                cycles et statistiques.
              </p>

              <div className="mt-4 rounded-xl border border-rf-blue/20 bg-rf-blue/5 p-3">
                <div className="text-rf-blue text-sm font-medium">
                  Synchronisation active
                </div>

                <div className="text-rf-muted text-xs mt-1">
                  Les données sont enregistrées automatiquement sur le cloud.
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="px-4 mt-4">
        <div className="rf-card p-4">
          <div className="flex items-start gap-3">
            <Lifebuoy size={28} weight="duotone" className="text-rf-green shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="rf-label">Support</div>
              <p className="text-rf-muted text-sm mt-2">
                Besoin d’aide ou envie de signaler un problème ?
              </p>
              <a
                href="mailto:kinan.hamzaa@gmail.com?subject=Support%20Routier%20Facile"
                className="rf-btn-ghost w-full mt-4 flex items-center justify-center"
              >
                Contacter le support
              </a>
            </div>
          </div>
        </div>
      </section>

      <section className="px-4 mt-4">
        <div className="rf-card p-4">
          <div className="flex items-start gap-3">
            <Info size={28} weight="duotone" className="text-rf-muted shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="rf-label">À propos</div>
              <div className="font-display text-xl mt-1">Routier Facile</div>
              <div className="text-rf-muted text-sm mt-1">Version 1.0</div>
              <p className="text-rf-muted text-xs mt-3">
                Application pensée pour aider les conducteurs routiers à suivre leurs journées,
                leurs repos et leurs alertes de conformité.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="px-4 mt-6">
        <button
          data-testid="logout-action"
          onClick={() => logout()}
          className="rf-btn-ghost w-full flex items-center justify-center gap-2"
        >
          <SignOut size={18} />
          Se déconnecter
        </button>
      </section>

      <section className="px-4 mt-10 pb-8">
        <div className="rf-label text-rf-red mb-2">Zone dangereuse</div>
        <div className="rf-card border border-rf-red/30 bg-rf-red/5 p-4">
          <div className="flex items-start gap-3">
            <Warning size={22} weight="duotone" className="text-rf-red shrink-0 mt-0.5" />
            <div className="flex-1">
              <h2 className="font-display text-xl">Supprimer mon compte</h2>
              <p className="text-rf-muted text-sm mt-2">
                Cette action est <strong>définitive</strong>. Votre compte, vos cycles, vos journées et tous vos
                jetons d'authentification seront effacés. Vous ne pourrez pas récupérer vos données.
              </p>
              <button
                data-testid="delete-account-open"
                onClick={() => setConfirmOpen(true)}
                className="rf-btn-ghost w-full mt-4 text-rf-red border border-rf-red/40"
              >
                <Trash size={16} className="mr-2" /> Supprimer mon compte
              </button>
            </div>
          </div>
        </div>
      </section>

      {confirmOpen && (
        <div
          data-testid="delete-confirm-modal"
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center px-4"
          onClick={() => !submitting && setConfirmOpen(false)}
        >
          <form
            onSubmit={handleDelete}
            className="rf-card max-w-md w-full p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="rf-label text-rf-red">Confirmation requise</div>
            <h2 className="font-display text-2xl mt-1">Supprimer définitivement ?</h2>
            <p className="text-sm text-rf-muted mt-3">
              Pour confirmer, saisissez votre mot de passe. Vos données seront immédiatement supprimées
              et vous serez déconnecté.
            </p>
            <div className="mt-4">
              <div className="rf-label mb-2">Mot de passe</div>
              <input
                data-testid="delete-confirm-password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="rf-input w-full"
                placeholder="••••••••"
                autoFocus
              />
            </div>
            {error && (
              <div data-testid="delete-confirm-error" className="text-rf-red text-sm mt-3">
                {error}
              </div>
            )}
            <div className="flex gap-2 mt-5">
              <button
                type="button"
                data-testid="delete-confirm-cancel"
                onClick={() => setConfirmOpen(false)}
                disabled={submitting}
                className="rf-btn-ghost flex-1"
              >
                Annuler
              </button>
              <button
                type="submit"
                data-testid="delete-confirm-submit"
                disabled={submitting}
                className="rf-btn-primary flex-1 bg-rf-red border-rf-red disabled:opacity-50"
              >
                {submitting ? "Suppression…" : "Supprimer"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
