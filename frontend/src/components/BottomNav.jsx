import { NavLink, useLocation } from "react-router-dom";
import { House, ClipboardText, ChartBar, ListChecks } from "@phosphor-icons/react";

const items = [
  { to: "/", label: "Tableau", icon: House, testid: "nav-dashboard" },
  { to: "/new", label: "Nouvelle", icon: ClipboardText, testid: "nav-new" },
  { to: "/history", label: "Historique", icon: ListChecks, testid: "nav-history" },
  { to: "/monthly", label: "Mensuel", icon: ChartBar, testid: "nav-monthly" },
];

export default function BottomNav() {
  const loc = useLocation();
  if (["/login", "/register"].includes(loc.pathname)) return null;
  return (
    <nav
      data-testid="bottom-nav"
      className="fixed bottom-0 left-0 right-0 z-40 border-t border-rf-border bg-rf-bg/95 backdrop-blur-md"
    >
      <div className="max-w-md mx-auto grid grid-cols-4">
        {items.map((it) => {
          const Icon = it.icon;
          return (
            <NavLink
              key={it.to}
              to={it.to}
              end={it.to === "/"}
              data-testid={it.testid}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center gap-1 py-3 text-[11px] uppercase tracking-[0.15em] transition-colors ${
                  isActive ? "text-rf-blue" : "text-rf-muted hover:text-white"
                }`
              }
            >
              <Icon size={22} weight="duotone" />
              <span>{it.label}</span>
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
}
