import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../../auth/useAuth";
import { Button } from "../ui/Button";
import { navItems } from "./nav";

export function AppLayout() {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-6">
            <span className="font-semibold text-indigo-700">AI Study Companion</span>
            <nav className="flex gap-1" aria-label="Main">
              {navItems
                .filter((item) => !item.staffOnly || user?.is_staff)
                .map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/"}
                    className={({ isActive }) =>
                      `rounded-lg px-3 py-1.5 text-sm ${isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100"}`
                    }
                  >
                    {item.label}
                  </NavLink>
                ))}
            </nav>
          </div>
          <div className="flex items-center gap-3 text-sm text-slate-600">
            <span className="hidden sm:inline">{user?.name || user?.email}</span>
            <Button variant="ghost" size="sm" onClick={logout}>
              Sign out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
