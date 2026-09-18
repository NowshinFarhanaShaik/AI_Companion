import { Navigate, Outlet, useLocation } from "react-router-dom";
import { Spinner } from "../components/ui/Spinner";
import { useAuth } from "./useAuth";

export function RequireAuth() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner className="mx-auto mt-24" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}
