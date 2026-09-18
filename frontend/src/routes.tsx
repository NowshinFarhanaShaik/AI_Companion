import type { ComponentType } from "react";
import { createBrowserRouter } from "react-router-dom";
import { RequireAdmin } from "./auth/RequireAdmin";
import { RequireAuth } from "./auth/RequireAuth";
import { AppLayout } from "./components/layout/AppLayout";
import { RouteError } from "./components/shared/RouteError";
import { Spinner } from "./components/ui/Spinner";
import { AdminLayout } from "./features/admin/AdminLayout";
import { AuthPage } from "./features/auth/AuthPage";
import { HomePage } from "./features/home/HomePage";
import { MaterialsPage } from "./features/materials/MaterialsPage";
import { ProjectDashboardPage } from "./features/projects/ProjectDashboardPage";
import { ProjectLayout } from "./features/projects/ProjectLayout";
import { QuizPage } from "./features/quiz/QuizPage";
import { SpacePage } from "./features/spaces/SpacePage";
import { SpacesPage } from "./features/spaces/SpacesPage";
import { TutorPage } from "./features/tutor/TutorPage";

// Chart and admin pages load on demand, so the charting library stays out of the main bundle.
function lazyPage<M>(load: () => Promise<M>, pick: (module: M) => ComponentType) {
  return {
    lazy: async () => ({ Component: pick(await load()) }),
    hydrateFallbackElement: <Spinner className="mx-auto mt-16" />,
    errorElement: <RouteError />,
  };
}

export const router = createBrowserRouter([
  { path: "/login", element: <AuthPage mode="login" />, errorElement: <RouteError /> },
  { path: "/register", element: <AuthPage mode="register" />, errorElement: <RouteError /> },
  {
    element: <RequireAuth />,
    errorElement: <RouteError />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <HomePage /> },
          { path: "spaces", element: <SpacesPage /> },
          { path: "spaces/:spaceId", element: <SpacePage /> },
          {
            path: "analytics",
            ...lazyPage(() => import("./features/analytics/GlobalAnalyticsPage"), (m) => m.GlobalAnalyticsPage),
          },
          {
            path: "projects/:projectId",
            element: <ProjectLayout />,
            children: [
              { index: true, element: <ProjectDashboardPage /> },
              { path: "materials", element: <MaterialsPage /> },
              { path: "tutor", element: <TutorPage /> },
              { path: "quiz", element: <QuizPage /> },
              { path: "growth", ...lazyPage(() => import("./features/growth/GrowthPage"), (m) => m.GrowthPage) },
              {
                path: "analytics",
                ...lazyPage(() => import("./features/analytics/ProjectAnalyticsPage"), (m) => m.ProjectAnalyticsPage),
              },
            ],
          },
          {
            path: "admin",
            element: (
              <RequireAdmin>
                <AdminLayout />
              </RequireAdmin>
            ),
            children: [
              { index: true, ...lazyPage(() => import("./features/admin/AdminOverviewPage"), (m) => m.AdminOverviewPage) },
              { path: "users", ...lazyPage(() => import("./features/admin/AdminUsersPage"), (m) => m.AdminUsersPage) },
              {
                path: "users/:userId",
                ...lazyPage(() => import("./features/admin/AdminUserDetailPage"), (m) => m.AdminUserDetailPage),
              },
              {
                path: "activity",
                ...lazyPage(() => import("./features/admin/AdminActivityPage"), (m) => m.AdminActivityPage),
              },
              {
                path: "ai-usage",
                ...lazyPage(() => import("./features/admin/AdminAIUsagePage"), (m) => m.AdminAIUsagePage),
              },
              { path: "evals", ...lazyPage(() => import("./features/admin/AdminEvalsPage"), (m) => m.AdminEvalsPage) },
              { path: "jobs", ...lazyPage(() => import("./features/admin/AdminJobsPage"), (m) => m.AdminJobsPage) },
              { path: "health", ...lazyPage(() => import("./features/admin/AdminHealthPage"), (m) => m.AdminHealthPage) },
            ],
          },
        ],
      },
    ],
  },
]);
