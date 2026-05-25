import { Link } from "react-router-dom";
import {
  Truck, Clock, Coffee, Bed, ListBullets, FilePdf, DeviceMobile, ArrowRight, CheckCircle,
} from "@phosphor-icons/react";

const FEATURES = [
  { icon: Clock, label: "Calcul des heures",
    detail: "Conduite, pauses, amplitude, travail effectif — calculés automatiquement à partir de vos saisies." },
  { icon: Coffee, label: "Suivi des pauses",
    detail: "Règle 4h30 / 45 min appliquée en direct, avec validation visuelle conforme à la réglementation européenne." },
  { icon: Bed, label: "Repos quotidien et hebdomadaire",
    detail: "Détection des repos journaliers, hebdomadaires complets ou réduits — sans risquer la double comptabilité." },
  { icon: ListBullets, label: "Historique",
    detail: "Retrouvez chaque journée, par cycle, par semaine ou par mois — éditables à tout moment." },
  { icon: FilePdf, label: "Export PDF",
    detail: "Générez vos relevés mensuels en PDF paysage prêts à transmettre pour la paie ou un contrôle." },
  { icon: DeviceMobile, label: "Adapté mobile",
    detail: "Conçu pour la cabine : sombre, lisible, tactile, fonctionne aussi installé en application sur votre écran d'accueil." },
];

export default function Landing() {
  return (
    <div data-testid="landing-page" className="rf-app-min-h-screen rf-safe-top rf-grain">
      {/* Hero */}
      <header className="relative">
        <div
          className="absolute inset-0 -z-10 bg-cover bg-center"
          style={{
            backgroundImage:
              "linear-gradient(180deg, rgba(10,10,10,0.55) 0%, rgba(10,10,10,1) 90%), url('https://images.unsplash.com/photo-1485575301924-6891ef935dcd?crop=entropy&cs=srgb&fm=jpg&q=85')",
          }}
        />
        <div className="px-5 sm:px-8 pt-10 pb-12 max-w-3xl mx-auto">
          <div className="flex items-center gap-2 text-rf-blue">
            <Truck size={26} weight="duotone" />
            <span className="rf-label text-white" data-testid="landing-brand">ROUTIER FACILE</span>
          </div>
          <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl tracking-tight mt-6 leading-[1.05]">
            Votre carnet<br />de route, simple.
          </h1>
          <p className="text-rf-muted text-base sm:text-lg mt-6 max-w-xl" data-testid="landing-tagline">
            L'application simple pour les conducteurs routiers. Suivez vos heures de conduite,
            pauses, amplitude, repos et exportez vos journées en PDF.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row gap-3">
            <Link
              to="/register"
              data-testid="landing-cta-register"
              className="rf-btn-primary flex items-center justify-center gap-2 text-lg"
            >
              Créer un compte
              <ArrowRight size={18} weight="bold" />
            </Link>
            <Link
              to="/login"
              data-testid="landing-cta-login"
              className="rf-btn-ghost flex items-center justify-center gap-2 text-lg"
            >
              Se connecter
            </Link>
          </div>
          <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-rf-muted">
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle size={14} weight="duotone" className="text-rf-green" /> Conformité européenne
            </span>
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle size={14} weight="duotone" className="text-rf-green" /> Sans publicité
            </span>
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle size={14} weight="duotone" className="text-rf-green" /> Installable sur mobile
            </span>
          </div>
        </div>
      </header>

      {/* Features */}
      <section className="px-5 sm:px-8 py-10 max-w-3xl mx-auto" data-testid="landing-features">
        <div className="rf-label mb-2">Ce que fait l'application</div>
        <h2 className="font-display text-3xl sm:text-4xl tracking-tight mb-6">
          Pensé pour la cabine.
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {FEATURES.map((f) => {
            const Icon = f.icon;
            return (
              <article
                key={f.label}
                className="rf-card p-4 flex gap-3 items-start"
                data-testid={`feature-${f.label.toLowerCase().replace(/[^a-z]+/g, "-")}`}
              >
                <div className="shrink-0 w-10 h-10 rounded-full bg-rf-blue/15 text-rf-blue flex items-center justify-center">
                  <Icon size={20} weight="duotone" />
                </div>
                <div className="flex-1">
                  <h3 className="font-display text-lg leading-tight">{f.label}</h3>
                  <p className="text-rf-muted text-sm mt-1">{f.detail}</p>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {/* Why Routier Facile */}
      <section className="px-5 sm:px-8 pb-2 max-w-3xl mx-auto" data-testid="landing-why">
        <div className="rf-label mb-2">Notre promesse</div>
        <h2 className="font-display text-3xl sm:text-4xl tracking-tight">
          Pourquoi Routier Facile&nbsp;?
        </h2>
        <p className="text-rf-muted text-base mt-3 max-w-xl" data-testid="landing-why-body">
          Simple, rapide, pensé pour éviter les erreurs de calcul et garder une trace claire
          de vos journées.
        </p>
        <p className="text-[13px] text-rf-muted/80 mt-4" data-testid="landing-trust-line">
          Conçu pour les conducteurs routiers — sans publicité, lisible sur mobile.
        </p>
      </section>

      {/* Bottom CTA */}
      <section className="px-5 sm:px-8 pb-12 max-w-3xl mx-auto">
        <div className="rf-card p-6 sm:p-8 border border-rf-blue/30 bg-rf-blue/5">
          <h2 className="font-display text-2xl sm:text-3xl tracking-tight">
            Prêt à démarrer votre premier cycle ?
          </h2>
          <p className="text-rf-muted text-sm mt-2">
            La création de compte prend moins d'une minute. Vous serez sur le tableau de bord
            juste après avoir vérifié votre adresse e-mail.
          </p>
          <div className="mt-5 flex flex-col sm:flex-row gap-3">
            <Link
              to="/register"
              data-testid="landing-bottom-cta-register"
              className="rf-btn-primary flex items-center justify-center gap-2 text-lg"
            >
              Créer mon compte
              <ArrowRight size={18} weight="bold" />
            </Link>
            <Link
              to="/login"
              data-testid="landing-bottom-cta-login"
              className="rf-btn-ghost flex items-center justify-center gap-2 text-lg"
            >
              J'ai déjà un compte
            </Link>
          </div>
        </div>
      </section>

      <footer className="px-5 sm:px-8 py-6 max-w-3xl mx-auto text-center text-xs text-rf-muted rf-safe-bottom">
        © {new Date().getFullYear()} Routier Facile — conçu en France pour les conducteurs européens.
      </footer>
    </div>
  );
}
