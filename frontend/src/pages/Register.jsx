import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Truck } from "@phosphor-icons/react";

export default function Register() {
  const { register, error } = useAuth();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    const res = await register(email, password, name);
    setLoading(false);
    if (res.ok) {
      nav("/verify-pending", { state: { email: res.email }, replace: true });
    }
  };

  return (
    <div className="rf-app-min-h-screen flex flex-col rf-safe-top">
      <div className="px-5 sm:px-6 pt-10 sm:pt-12 pb-6">
        <div className="flex items-center gap-2 text-rf-blue">
          <Truck size={26} weight="duotone" />
          <span className="rf-label text-white">ROUTIER FACILE</span>
        </div>
        <h1 className="font-display text-4xl sm:text-5xl tracking-tight mt-4">
          Créer<br />votre compte
        </h1>
        <p className="text-rf-muted mt-3 text-sm">
          Suivez votre temps de conduite, votre repos et vos indemnités en quelques secondes.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="px-5 sm:px-6 py-4 max-w-md mx-auto w-full space-y-5 rf-safe-bottom">
        <div>
          <div className="rf-label mb-2">Prénom (optionnel)</div>
          <input
            data-testid="register-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rf-input w-full"
            placeholder="Jean"
          />
        </div>
        <div>
          <div className="rf-label mb-2">Email</div>
          <input
            data-testid="register-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rf-input w-full"
            placeholder="conducteur@routier.fr"
          />
        </div>
        <div>
          <div className="rf-label mb-2">Mot de passe (6 caractères min.)</div>
          <input
            data-testid="register-password"
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rf-input w-full"
            placeholder="••••••••"
          />
        </div>
        {error && (
          <div data-testid="register-error" className="text-rf-red text-sm">
            {error}
          </div>
        )}
        <button
          data-testid="register-submit"
          disabled={loading}
          className="rf-btn-primary w-full text-lg disabled:opacity-50"
        >
          {loading ? "Création…" : "Créer mon compte"}
        </button>
        <p className="text-center text-rf-muted text-sm">
          Déjà inscrit ?{" "}
          <Link to="/login" data-testid="link-login" className="text-rf-blue">
            Se connecter
          </Link>
        </p>
      </form>
    </div>
  );
}
