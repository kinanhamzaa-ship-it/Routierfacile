import { useEffect, useState } from "react";
import api from "../lib/api";

export default function Admin() {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [successMessage, setSuccessMessage] = useState("");
  const [search, setSearch] = useState("");
  const [pendingReviews, setPendingReviews] = useState([]);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    const statsRes = await api.get("/admin/stats");
    const usersRes = await api.get("/admin/users");
    const reviewsRes = await api.get("/admin/reviews/pending");

    setStats(statsRes.data);
    setUsers(usersRes.data);
    setPendingReviews(reviewsRes.data || []);
  }

  async function changePlan(userId, plan) {
    try {
      await api.patch(`/admin/users/${userId}/plan`, { plan });

      setSuccessMessage(`✓ Plan changé vers ${plan}`);

      setTimeout(() => {
        setSuccessMessage("");
      }, 2500);

      loadData();
    } catch (err) {
      console.error(err);
    }
  }

  async function approveReview(reviewId) {
    try {
      await api.patch(`/admin/reviews/${reviewId}/approve`);

      setSuccessMessage("✓ Avis approuvé");

      setTimeout(() => {
        setSuccessMessage("");
      }, 2500);

      loadData();
    } catch (err) {
      console.error(err);
    }
  }

  async function deleteReview(reviewId) {
    const ok = window.confirm("Supprimer définitivement cet avis ?");
    if (!ok) return;

    try {
      await api.delete(`/admin/reviews/${reviewId}`);

      setSuccessMessage("✓ Avis supprimé");

      setTimeout(() => {
        setSuccessMessage("");
      }, 2500);

      loadData();
    } catch (err) {
      console.error(err);
    }
  }

  if (!stats) {
    return (
      <div className="px-4 pt-5">
        <div className="rf-card p-4">Chargement...</div>
      </div>
    );
  }

  return (
    <div className="px-4 pt-5">
      <div className="rf-label">Administration</div>
      <h1 className="font-display text-3xl mt-1">Admin Panel</h1>

      {successMessage && (
        <div className="mt-4 rounded-xl border border-green-500/30 bg-green-500/10 p-3 text-green-400">
          {successMessage}
        </div>
      )}

      <div className="rf-card p-4 mt-4">
        <div className="rf-label">Utilisateurs</div>
        <div className="text-2xl mt-2">{stats.users_count}</div>
      </div>

      <div className="rf-card p-4 mt-4">
        <div className="rf-label">Journées enregistrées</div>
        <div className="text-2xl mt-2">{stats.entries_count}</div>
      </div>

      <div className="rf-card p-4 mt-4">
        <div className="flex items-center justify-between gap-3">
          <div className="rf-label">Avis en attente</div>
          <span className="px-2 py-1 rounded-full text-xs bg-rf-orange/20 text-rf-orange">
            {pendingReviews.length}
          </span>
        </div>

        {pendingReviews.length === 0 ? (
          <div className="text-sm text-rf-muted mt-3">
            Aucun avis en attente.
          </div>
        ) : (
          <div className="mt-3 space-y-3">
            {pendingReviews.map((review) => (
              <div
                key={review.id}
                className="rounded-xl border border-white/10 bg-white/5 p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium">
                      {review.name || "Conducteur"}
                    </div>
                    <div className="text-rf-orange text-sm mt-1">
                      {"★".repeat(review.rating || 0)}
                      {"☆".repeat(5 - (review.rating || 0))}
                    </div>
                  </div>

                  <div className="text-xs text-rf-muted">
                    En attente
                  </div>
                </div>

                {review.comment && (
                  <p className="text-sm text-rf-muted mt-3">
                    {review.comment}
                  </p>
                )}

                <div className="flex gap-2 mt-3">
                  <button
                    onClick={() => approveReview(review.id)}
                    className="px-3 py-2 rounded-lg text-sm bg-green-500/20 text-green-400 border border-green-500/30"
                  >
                    Approuver
                  </button>

                  <button
                    onClick={() => deleteReview(review.id)}
                    className="px-3 py-2 rounded-lg text-sm bg-rf-red/10 text-rf-red border border-rf-red/30"
                  >
                    Supprimer
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rf-card p-4 mt-4">
        <div className="rf-label mb-3">Tous les utilisateurs</div>

        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Rechercher un utilisateur..."
          className="rf-input w-full mb-4"
        />

        {users
          .filter((u) => {
            const q = search.toLowerCase();
            return (
              !q ||
              (u.name || "").toLowerCase().includes(q) ||
              (u.email || "").toLowerCase().includes(q)
            );
          })
          .map((u) => (
          <div
            key={u.id}
            className="border-b border-white/10 py-3"
          >
            <div className="font-medium">{u.name || "Sans nom"}</div>
            <div className="text-sm opacity-70">{u.email}</div>

            <div className="mt-2">
              <span
                className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                  u.plan === "admin"
                    ? "bg-rf-blue/20 text-rf-blue"
                    : u.plan === "premium"
                    ? "bg-green-500/20 text-green-400"
                    : "bg-white/10 text-white/70"
                }`}
              >
                {u.plan || "free"}
              </span>
            </div>

            <div className="flex gap-2 mt-3 flex-wrap">
              <button
                className={`px-3 py-1 rounded text-sm ${
                  u.plan === "free"
                    ? "bg-white text-black"
                    : "bg-white/10"
                }`}
                disabled={u.plan === "free"}
                onClick={() => changePlan(u.id, "free")}
              >
                Free
              </button>

              <button
                className={`px-3 py-1 rounded text-sm ${
                  u.plan === "premium"
                    ? "bg-green-500 text-black"
                    : "bg-green-500/20 text-green-400"
                }`}
                disabled={u.plan === "premium"}
                onClick={() => changePlan(u.id, "premium")}
              >
                Premium
              </button>

              <button
                className={`px-3 py-1 rounded text-sm ${
                  u.plan === "admin"
                    ? "bg-rf-blue text-white"
                    : "bg-rf-blue/20 text-rf-blue"
                }`}
                disabled={u.plan === "admin"}
                onClick={() => changePlan(u.id, "admin")}
              >
                Admin
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
