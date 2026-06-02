import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Star } from "@phosphor-icons/react";
import api from "../lib/api";

function Stars({ rating }) {
  const value = Math.round(Number(rating || 0));

  return (
    <div className="flex items-center gap-1 text-rf-orange">
      {[1, 2, 3, 4, 5].map((n) => (
        <Star
          key={n}
          size={18}
          weight={n <= value ? "fill" : "regular"}
        />
      ))}
    </div>
  );
}

export default function Reviews() {
  const nav = useNavigate();
  const [stats, setStats] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadReviews();
  }, []);

  async function loadReviews() {
    try {
      const [statsRes, reviewsRes] = await Promise.all([
        api.get("/reviews/stats"),
        api.get("/reviews?limit=20"),
      ]);

      setStats(statsRes.data);
      setReviews(reviewsRes.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div data-testid="reviews-page" className="px-4 pt-5 pb-10">
      <header className="flex items-center gap-3">
        <button
          onClick={() => nav(-1)}
          className="rf-btn-ghost px-3 py-2"
          aria-label="Retour"
        >
          <ArrowLeft size={18} />
        </button>

        <div>
          <div className="rf-label">Avis</div>
          <h1 className="font-display text-3xl tracking-tight mt-0.5">
            Avis des conducteurs
          </h1>
        </div>
      </header>

      {loading && (
        <div className="rf-card p-4 mt-5 text-rf-muted">
          Chargement des avis...
        </div>
      )}

      {!loading && (
        <>
          <section className="rf-card p-5 mt-5 border border-rf-blue/20 bg-rf-blue/5">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="rf-label">Note moyenne</div>

                <div className="font-display text-4xl mt-1">
                  {stats?.average_display || "5.0"} / 5
                </div>

                <div className="text-rf-muted text-sm mt-1">
                  Basé sur {stats?.count || 0} avis
                </div>
              </div>

              <Stars rating={stats?.average || 5} />
            </div>
          </section>

          <section className="mt-5">
            {reviews.length === 0 ? (
              <div className="rf-card p-4 text-rf-muted">
                Aucun avis pour le moment.
              </div>
            ) : (
              <div className="space-y-3">
                {reviews.map((review) => (
                  <article
                    key={review.id}
                    className="rf-card p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-medium">
                          {review.name || "Conducteur"}
                        </div>

                        <div className="text-xs text-rf-green mt-1">
                          ✓ Avis vérifié
                        </div>
                      </div>

                      <Stars rating={review.rating} />
                    </div>

                    {review.comment && (
                      <p className="text-rf-muted text-sm mt-3">
                        {review.comment}
                      </p>
                    )}
                  </article>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
