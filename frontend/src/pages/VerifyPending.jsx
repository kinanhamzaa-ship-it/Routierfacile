import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { EnvelopeSimple } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function VerifyPending() {
  const { resendVerification } = useAuth();
  const loc = useLocation();
  const email = loc.state?.email || "";
  const [sending, setSending] = useState(false);

  const handleResend = async () => {
    if (!email) return;
    setSending(true);
    const r = await resendVerification(email);
    setSending(false);
    toast.success(r.message || "Si un compte existe pour cette adresse, un e-mail de vérification a été envoyé.");
  };

  return (
    <div data-testid="verify-pending-page" className="rf-app-min-h-screen flex flex-col rf-safe-top">
      <div className="flex-1 px-5 sm:px-6 py-10 max-w-md mx-auto w-full rf-safe-bottom">
        <div className="rf-card p-6 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-rf-blue/15 text-rf-blue mb-4">
            <EnvelopeSimple size={32} weight="duotone" />
          </div>
          <div className="rf-label text-rf-blue">Vérification requise</div>
          <h1 className="font-display text-3xl tracking-tight mt-1">
            Vérifiez votre e-mail
          </h1>
          {email && (
            <p className="text-rf-muted text-sm mt-3" data-testid="verify-pending-email">
              Un lien de vérification a été envoyé à <span className="text-white font-medium">{email}</span>.
            </p>
          )}
          <p className="text-rf-muted text-sm mt-2">
            Cliquez sur le lien dans l'e-mail pour activer votre compte avant de vous connecter.
          </p>
          <button
            data-testid="resend-verification-btn"
            onClick={handleResend}
            disabled={!email || sending}
            className="rf-btn-ghost w-full mt-6 disabled:opacity-50"
          >
            {sending ? "Envoi…" : "Renvoyer l'e-mail de vérification"}
          </button>
          <p className="text-rf-muted text-xs mt-4">
            Pensez à vérifier votre dossier spam si vous ne le voyez pas.
          </p>
        </div>
        <p className="text-center text-rf-muted text-sm mt-6">
          Déjà vérifié ?{" "}
          <Link to="/login" data-testid="link-login" className="text-rf-blue">
            Se connecter
          </Link>
        </p>
      </div>
    </div>
  );
}
