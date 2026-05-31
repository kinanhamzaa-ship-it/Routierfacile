import { useEffect, useState } from "react";
import api from "../lib/api";

export default function Admin() {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    const statsRes = await api.get("/admin/stats");
    const usersRes = await api.get("/admin/users");

    setStats(statsRes.data);
    setUsers(usersRes.data);
  }

  async function changePlan(userId, plan) {
    await api.patch(`/admin/users/${userId}/plan`, { plan });
    loadData();
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

      <div className="rf-card p-4 mt-4">
        <div className="rf-label">Utilisateurs</div>
        <div className="text-2xl mt-2">{stats.users_count}</div>
      </div>

      <div className="rf-card p-4 mt-4">
        <div className="rf-label">Journées enregistrées</div>
        <div className="text-2xl mt-2">{stats.entries_count}</div>
      </div>

      <div className="rf-card p-4 mt-4">
        <div className="rf-label">Répartition des plans</div>
        <div className="mt-2">Free : {stats.free_users}</div>
        <div>Premium : {stats.premium_users}</div>
        <div>Admin : {stats.admin_users}</div>
      </div>

      <div className="rf-card p-4 mt-4">
        <div className="rf-label mb-3">Tous les utilisateurs</div>

        {users.map((u) => (
          <div
            key={u.id}
            className="border-b border-white/10 py-3"
          >
            <div className="font-medium">{u.name || "Sans nom"}</div>
            <div className="text-sm opacity-70">{u.email}</div>

            <div className="text-xs mt-1 opacity-70">
              Plan actuel : {u.plan || "free"}
            </div>

            <div className="flex gap-2 mt-3">
              <button
                className="rf-btn-secondary"
                onClick={() => changePlan(u.id, "free")}
              >
                Free
              </button>

              <button
                className="rf-btn-secondary"
                onClick={() => changePlan(u.id, "premium")}
              >
                Premium
              </button>

              <button
                className="rf-btn-secondary"
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
