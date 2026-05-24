import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { CheckCircle, WarningCircle, Spinner } from "@phosphor-icons/react";

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [status, setStatus] = useState("loading"); // loading | success | error
  const [errorMsg, setErrorMsg] = useState("");
  const nav = useNavigate();

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setErrorMsg("Aucun jeton de vérification fourni.");
      return;
    }
    let cancelled = false;
    api
      .post("/auth/verify-email", { token })
      .then(() => {
        if (cancelled) return;
        setStatus("success");
      })
      .catch((e) => {
        if (cancelled) return;
        const detail = e.response?.data?.detail;
        setStatus("error");
        setErrorMsg(formatApiError(detail) || "Lien de vérification invalide ou expiré.");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div data-testid="verify-email-page" className="rf-app-min-h-screen flex flex-col rf-safe-top">
      <div className="flex-1 px-5 sm:px-6 py-10 max-w-md mx-auto w-full rf-safe-bottom">
        <div className="rf-card p-6 text-center">
          {status === "loading" && (
            <>
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-rf-blue/15 text-rf-blue mb-4 animate-pulse">
                <Spinner size={32} weight="bold" />
              </div>
              <h1 className="font-display text-3xl tracking-tight">Vérification…</h1>
              <p className="text-rf-muted text-sm mt-2">Validation de votre e-mail en cours.</p>
            </>
          )}
          {status === "success" && (
            <>
              <div
                data-testid="verify-success"
                className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-rf-green/15 text-rf-green mb-4"
              >
                <CheckCircle size={36} weight="duotone" />
              </div>
              <div className="rf-label text-rf-green">E-mail vérifié</div>
              <h1 className="font-display text-3xl tracking-tight mt-1">Compte activé</h1>
              <p className="text-rf-muted text-sm mt-3">
                Votre adresse e-mail est confirmée. Vous pouvez maintenant vous connecter.
              </p>
              <button
                data-testid="verify-goto-login"
                onClick={() => nav("/login", { replace: true })}
                className="rf-btn-primary w-full mt-6"
              >
                Se connecter
              </button>
            </>
          )}
          {status === "error" && (
            <>
              <div
                data-testid="verify-error"
                className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-rf-red/15 text-rf-red mb-4"
              >
                <WarningCircle size={36} weight="duotone" />
              </div>
              <div className="rf-label text-rf-red">Échec de la vérification</div>
              <h1 className="font-display text-3xl tracking-tight mt-1">Lien invalide</h1>
              <p className="text-rf-muted text-sm mt-3">{errorMsg}</p>
              <Link
                to="/login"
                data-testid="verify-back-to-login"
                className="rf-btn-ghost w-full mt-6 inline-block"
              >
                Retour à la connexion
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
