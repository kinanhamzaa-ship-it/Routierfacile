import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Truck } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function Login() {
  const { login, resendVerification, error } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [unverifiedEmail, setUnverifiedEmail] = useState(null);
  const [resending, setResending] = useState(false);
  const nav = useNavigate();
  const loc = useLocation();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setUnverifiedEmail(null);
    const res = await login(email, password);
    setLoading(false);
    if (res.ok) {
      nav(loc.state?.from?.pathname || "/", { replace: true });
    } else if (res.code === "email_not_verified") {
      setUnverifiedEmail(res.email);
    }
  };

  const handleResend = async () => {
    if (!unverifiedEmail) return;
    setResending(true);
    const r = await resendVerification(unverifiedEmail);
    setResending(false);
    toast.success(r.message || "Si un compte existe pour cette adresse, un e-mail de vérification a été envoyé.");
  };

  return (
    <div className="rf-app-min-h-screen flex flex-col rf-safe-top">
      <div
        className="relative h-48 sm:h-56 bg-cover bg-center"
        style={{
          backgroundImage:
            "linear-gradient(180deg, rgba(10,10,10,0.4) 0%, rgba(10,10,10,1) 100%), url('https://images.unsplash.com/photo-1485575301924-6891ef935dcd?crop=entropy&cs=srgb&fm=jpg&q=85')",
        }}
      >
        <div className="absolute inset-0 flex items-end p-5 sm:p-6">
          <div>
            <div className="flex items-center gap-2 text-rf-blue">
              <Truck size={26} weight="duotone" />
              <span className="rf-label text-white">ROUTIER FACILE</span>
            </div>
            <h1 className="font-display text-4xl sm:text-5xl tracking-tight mt-2">
              Votre carnet<br />de route
            </h1>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="flex-1 px-5 sm:px-6 py-8 max-w-md mx-auto w-full space-y-5 rf-safe-bottom">
        <div>
          <div className="rf-label mb-2">Email</div>
          <input
            data-testid="login-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rf-input w-full"
            placeholder="conducteur@routier.fr"
          />
        </div>
        <div>
          <div className="rf-label mb-2">Mot de passe</div>
          <input
            data-testid="login-password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rf-input w-full"
            placeholder="••••••••"
          />
        </div>
        {error && (
          <div data-testid="login-error" className="text-rf-red text-sm">
            {error}
          </div>
        )}
        {unverifiedEmail && (
          <div data-testid="resend-verification-block" className="rf-card border border-rf-orange/30 bg-rf-orange/5 p-3 text-sm">
            <p className="text-rf-muted">
              Vous n'avez pas reçu l'e-mail ? Renvoyez-en un nouveau.
            </p>
            <button
              type="button"
              data-testid="resend-verification-btn"
              onClick={handleResend}
              disabled={resending}
              className="rf-btn-ghost w-full mt-2 disabled:opacity-50"
            >
              {resending ? "Envoi…" : "Renvoyer l'e-mail de vérification"}
            </button>
          </div>
        )}
        <button
          data-testid="login-submit"
          disabled={loading}
          className="rf-btn-primary w-full text-lg disabled:opacity-50"
        >
          {loading ? "Connexion…" : "Se connecter"}
        </button>
        <div className="text-center">
          <Link
            to="/forgot-password"
            data-testid="link-forgot-password"
            className="text-rf-muted text-sm hover:text-rf-blue"
          >
            Mot de passe oublié ?
          </Link>
        </div>
        <p className="text-center text-rf-muted text-sm">
          Pas encore de compte ?{" "}
          <Link to="/register" data-testid="link-register" className="text-rf-blue">
            Créer un compte
          </Link>
        </p>
      </form>
    </div>
  );
}
