import { NavLink, Outlet } from "react-router-dom";
import { PageHeader } from "../../components/shared/PageHeader";

const SECTIONS = [
  { path: "", label: "Overview" },
  { path: "users", label: "Users" },
  { path: "activity", label: "Activity" },
  { path: "ai-usage", label: "AI usage" },
  { path: "evals", label: "Evals" },
  { path: "jobs", label: "Jobs" },
  { path: "health", label: "Health" },
];

export function AdminLayout() {
  return (
    <div className="space-y-4">
      <PageHeader title="Admin" subtitle="Platform-wide view of users, learning activity, AI and system health" />
      <nav className="flex gap-1 overflow-x-auto border-b border-slate-200" aria-label="Admin sections">
        {SECTIONS.map((section) => (
          <NavLink
            key={section.path}
            to={section.path}
            end={section.path === ""}
            className={({ isActive }) =>
              `whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium ${
                isActive ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-600 hover:text-slate-900"
              }`
            }
          >
            {section.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
