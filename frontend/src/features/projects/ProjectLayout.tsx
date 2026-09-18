import { Link, NavLink, Outlet } from "react-router-dom";
import { useProject } from "../../api/workspace";
import { ErrorState } from "../../components/shared/ErrorState";
import { Spinner } from "../../components/ui/Spinner";
import { projectTabs } from "./tabs";
import { useProjectId } from "./useProjectId";

export function ProjectLayout() {
  const project = useProject(useProjectId());

  if (project.isLoading) return <Spinner className="mx-auto mt-10" />;
  if (project.error) return <ErrorState error={project.error} onRetry={() => project.refetch()} />;
  if (!project.data) return null;

  return (
    <>
      <p className="mb-2 text-sm">
        <Link to={`/spaces/${project.data.space_id}`} className="text-indigo-600 hover:underline">
          ← {project.data.space_name}
        </Link>
      </p>
      <h1 className="text-2xl font-semibold text-slate-900">{project.data.name}</h1>
      <p className="mt-1 text-sm text-slate-600">Goal: {project.data.learning_goal}</p>
      <nav className="mb-6 mt-5 flex gap-1 overflow-x-auto border-b border-slate-200" aria-label="Project sections">
        {projectTabs.map((tab) => (
          <NavLink
            key={tab.path}
            to={tab.path}
            end={tab.path === ""}
            className={({ isActive }) =>
              `whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium ${isActive ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-600 hover:text-slate-900"}`
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </>
  );
}
