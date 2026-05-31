import { useEffect, useState } from "react";
import api from "../lib/api";

export default function Admin() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  async function loadStats() {
    try {
      const res = await api.get("/admin/stats");
      setStats(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="px-4 pt-5">
      <div className="rf-label">Administration</div>

      <h1 className="font-display text-3xl mt-1">
        Admin Panel
      </h1>

      {loading && (
        <div className="rf-card p-4 mt-4">
          Chargement...
        </div>
      )}

      {!loading && stats && (
        <>
          <div className="rf-card p-4 mt-4">
            <div className="rf-label">Utilisateurs</div>
            <div className="text-2xl mt-2">
              {stats.users_count}
            </div>
          </div>

          <div className="rf-card p-4 mt-4">
            <div className="rf-label">Journées enregistrées</div>
            <div className="text-2xl mt-2">
              {stats.entries_count}
            </div>
          </div>

          <div className="rf-card p-4 mt-4">
            <div className="rf-label">Premium</div>
            <div className="text-2xl mt-2">
              {stats.premium_users}
            </div>
          </div>

          <div className="rf-card p-4 mt-4">
            <div className="rf-label">Administrateurs</div>
            <div className="text-2xl mt-2">
              {stats.admin_users}
            </div>
          </div>

          <div className="rf-card p-4 mt-4">
            <div className="rf-label mb-3">
              Derniers utilisateurs
            </div>

            {stats.latest_users?.map((u) => (
              <div
                key={u.id}
                className="border-b border-white/10 py-2"
              >
                <div>{u.name || "Sans nom"}</div>
                <div className="text-sm opacity-70">
                  {u.email}
                </div>
                <div className="text-xs text-rf-blue mt-1">
                  {u.plan || "free"}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
