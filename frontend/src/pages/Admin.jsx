export default function Admin() {
  return (
    <div className="px-4 pt-5">
      <div className="rf-label">Administration</div>
      <h1 className="font-display text-3xl mt-1">Admin Panel</h1>

      <div className="rf-card p-4 mt-4">
        <div className="rf-label">Utilisateurs</div>
        <div className="text-2xl mt-2">--</div>
      </div>

      <div className="rf-card p-4 mt-4">
        <div className="rf-label">Journées enregistrées</div>
        <div className="text-2xl mt-2">--</div>
      </div>

      <div className="rf-card p-4 mt-4">
        <div className="rf-label">Plans Premium</div>
        <div className="text-2xl mt-2">--</div>
      </div>
    </div>
  );
}
