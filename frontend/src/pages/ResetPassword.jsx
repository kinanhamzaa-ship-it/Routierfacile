import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { CheckCircle, WarningCircle } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function ResetPassword() {
  const { resetPassword } = useAuth();
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState("");
  const nav = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErr("");
    if (!token) {
      setErr("Lien invalide. Demandez un nouveau lien.");
      return;
    }
    if (password.length < 6) {
      setErr("Le mot de passe doit contenir au moins 6 caractères.");
      return;
    }
    if (password !== confirm) {
      setErr("Les deux mots de passe ne correspondent pas.");
      return;
    }
    setSubmitting(true);
    const r = await resetPassword(token, password);
    setSubmitting(false);
    if (r.ok) {
      setDone(true);
      toast.success("Mot de passe mis à jour.");
    } else {
      setErr(r.message || "Lien invalide ou expiré.");
    }
  };

  if (!token) {
    return (
      <div data-testid="reset-password-page" className="rf-app-min-h-screen flex flex-col rf-safe-top">
        <div className="flex-1 px-5 sm:px-6 py-10 max-w-md mx-auto w-full rf-safe-bottom">
          <div className="rf-card p-6 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-rf-red/15 text-rf-red mb-4">
              <WarningCircle size={36} weight="duotone" />
            </div>
            <h1 className="font-display text-3xl tracking-tight">Lien invalide</h1>
            <p className="text-rf-muted text-sm mt-3">Aucun jeton de réinitialisation fourni.</p>
            <Link to="/forgot-password" className="rf-btn-ghost w-full mt-6 inline-block" data-testid="reset-request-new">
              Demander un nouveau lien
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (done) {
    return (
      <div data-testid="reset-password-page" className="rf-app-min-h-screen flex flex-col rf-safe-top">
        <div className="flex-1 px-5 sm:px-6 py-10 max-w-md mx-auto w-full rf-safe-bottom">
          <div className="rf-card p-6 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-rf-green/15 text-rf-green mb-4">
              <CheckCircle size={36} weight="duotone" />
            </div>
            <div className="rf-label text-rf-green">Mot de passe mis à jour</div>
            <h1 className="font-display text-3xl tracking-tight mt-1">Vous êtes prêt</h1>
            <p className="text-rf-muted text-sm mt-3">
              Connectez-vous avec votre nouveau mot de passe.
            </p>
            <button
              data-testid="reset-goto-login"
              onClick={() => nav("/login", { replace: true })}
              className="rf-btn-primary w-full mt-6"
            >
              Se connecter
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div data-testid="reset-password-page" className="rf-app-min-h-screen flex flex-col rf-safe-top">
      <header className="px-5 sm:px-6 pt-10 sm:pt-12 pb-2">
        <div className="rf-label">Récupération</div>
        <h1 className="font-display text-3xl sm:text-4xl tracking-tight mt-1">
          Nouveau mot de passe
        </h1>
      </header>
      <form
        onSubmit={handleSubmit}
        className="flex-1 px-5 sm:px-6 py-6 max-w-md mx-auto w-full space-y-5 rf-safe-bottom"
      >
        <div>
          <div className="rf-label mb-2">Nouveau mot de passe</div>
          <input
            data-testid="reset-password-input"
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rf-input w-full"
            placeholder="••••••••"
          />
        </div>
        <div>
          <div className="rf-label mb-2">Confirmer le mot de passe</div>
          <input
            data-testid="reset-password-confirm"
            type="password"
            required
            minLength={6}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className="rf-input w-full"
            placeholder="••••••••"
          />
        </div>
        {err && (
          <div data-testid="reset-error" className="text-rf-red text-sm">{err}</div>
        )}
        <button
          data-testid="reset-submit"
          disabled={submitting}
          className="rf-btn-primary w-full text-lg disabled:opacity-50"
        >
          {submitting ? "Mise à jour…" : "Mettre à jour le mot de passe"}
        </button>
      </form>
    </div>
  );
}
