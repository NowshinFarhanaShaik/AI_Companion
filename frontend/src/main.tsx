import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { ApiError } from "./api/client";
import { AuthProvider } from "./auth/AuthProvider";
import { router } from "./routes";
import "./index.css";

// A 4xx answer will not change on a retry; only network and server errors are worth one more try.
const retry = (failureCount: number, error: Error) =>
  failureCount < 1 && !(error instanceof ApiError && error.status >= 400 && error.status < 500);

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry, staleTime: 10_000, refetchOnWindowFocus: false } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
