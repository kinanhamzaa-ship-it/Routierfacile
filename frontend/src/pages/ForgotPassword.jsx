import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ArrowLeft, EnvelopeSimple } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function ForgotPassword() {
  const { forgotPassword } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSending(true);
    const r = await forgotPassword(email);
    setSending(false);
    if (r.ok) {
      setSent(true);
      toast.success(r.message);
    } else {
      toast.error(r.message || "Erreur");
    }
  };

  return (
    <div data-testid="forgot-password-page" className="rf-app-min-h-screen flex flex-col rf-safe-top">
      <header className="px-5 sm:px-6 pt-10 sm:pt-12 pb-2 flex items-center gap-3">
        <button
          type="button"
          onClick={() => nav(-1)}
          className="rf-btn-ghost px-3 py-2"
          aria-label="Retour"
          data-testid="forgot-back-btn"
        >
          <ArrowLeft size={18} />
        </button>
        <div>
          <div className="rf-label">Récupération</div>
          <h1 className="font-display text-3xl sm:text-4xl tracking-tight mt-1">
            Mot de passe oublié
          </h1>
        </div>
      </header>

      {sent ? (
        <div className="flex-1 px-5 sm:px-6 py-8 max-w-md mx-auto w-full rf-safe-bottom">
          <div className="rf-card p-6 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-rf-blue/15 text-rf-blue mb-4">
              <EnvelopeSimple size={32} weight="duotone" />
            </div>
            <div className="rf-label text-rf-blue">E-mail envoyé</div>
            <h2 className="font-display text-2xl mt-1">Vérifiez votre boîte de réception</h2>
            <p className="text-rf-muted text-sm mt-3" data-testid="forgot-sent-message">
              Si un compte existe pour <span className="text-white font-medium">{email}</span>, un lien de
              réinitialisation a été envoyé. Le lien expire dans 1h.
            </p>
            <Link
              to="/login"
              data-testid="forgot-back-to-login"
              className="rf-btn-ghost w-full mt-6 inline-block"
            >
              Retour à la connexion
            </Link>
          </div>
        </div>
      ) : (
        <form
          onSubmit={handleSubmit}
          className="flex-1 px-5 sm:px-6 py-6 max-w-md mx-auto w-full space-y-5 rf-safe-bottom"
        >
          <p className="text-rf-muted text-sm">
            Entrez votre adresse e-mail. Nous vous enverrons un lien pour choisir un nouveau mot de passe.
          </p>
          <div>
            <div className="rf-label mb-2">Email</div>
            <input
              data-testid="forgot-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="rf-input w-full"
              placeholder="conducteur@routier.fr"
            />
          </div>
          <button
            data-testid="forgot-submit"
            disabled={sending}
            className="rf-btn-primary w-full text-lg disabled:opacity-50"
          >
            {sending ? "Envoi…" : "Envoyer le lien de réinitialisation"}
          </button>
          <p className="text-center text-rf-muted text-sm">
            <Link to="/login" className="text-rf-blue">Retour à la connexion</Link>
          </p>
        </form>
      )}
    </div>
  );
}
