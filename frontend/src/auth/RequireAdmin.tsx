import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { Spinner } from "../components/ui/Spinner";
import { useAuth } from "./useAuth";

// A UI convenience only. The real control is StaffJWTAuth on the API.
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner className="mx-auto mt-16" />;
  if (!user) return <Navigate to="/login" replace />;
  if (!user.is_staff) return <Navigate to="/" replace />;
  return <>{children}</>;
}
