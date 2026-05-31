import { useEffect, useState } from "react";
import api from "../lib/api";

export default function Admin() {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [successMessage, setSuccessMessage] = useState("");

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
