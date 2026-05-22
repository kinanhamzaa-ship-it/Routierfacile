import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Truck } from "@phosphor-icons/react";

export default function Login() {
  const { login, error } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();
  const loc = useLocation();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    const ok = await login(email, password);
    setLoading(false);
    if (ok) nav(loc.state?.from?.pathname || "/", { replace: true });
  };

  return (
    <div className="min-h-screen flex flex-col">
      <div
        className="relative h-56 bg-cover bg-center"
        style={{
          backgroundImage:
            "linear-gradient(180deg, rgba(10,10,10,0.4) 0%, rgba(10,10,10,1) 100%), url('https://images.unsplash.com/photo-1485575301924-6891ef935dcd?crop=entropy&cs=srgb&fm=jpg&q=85')",
        }}
      >
        <div className="absolute inset-0 flex items-end p-6">
          <div>
            <div className="flex items-center gap-2 text-rf-blue">
              <Truck size={28} weight="duotone" />
              <span className="rf-label text-white">ROUTIER FACILE</span>
            </div>
            <h1 className="font-display text-5xl tracking-tight mt-2">
              Votre carnet<br />de route
            </h1>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="flex-1 px-6 py-8 max-w-md mx-auto w-full space-y-5">
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
        <button
          data-testid="login-submit"
          disabled={loading}
          className="rf-btn-primary w-full text-lg disabled:opacity-50"
        >
          {loading ? "Connexion…" : "Se connecter"}
        </button>
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
