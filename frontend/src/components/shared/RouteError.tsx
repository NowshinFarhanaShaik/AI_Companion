import { useEffect } from "react";
import { Link, useRouteError } from "react-router-dom";
import { Button } from "../ui/Button";
import { buttonClasses } from "../ui/buttonStyles";

// Also shown when a lazy page fails to load, which happens after a deploy replaces the old code files.
export function RouteError() {
  const error = useRouteError();
  useEffect(() => console.error(error), [error]);

  return (
    <div role="alert" className="mx-auto mt-16 max-w-md rounded-xl border border-slate-200 bg-white p-6 text-center">
      <h1 className="text-lg font-semibold text-slate-900">Something went wrong on this page</h1>
      <p className="mt-2 text-sm text-slate-600">Your work is saved. Reloading the page usually fixes this.</p>
      <div className="mt-4 flex justify-center gap-2">
        <Button onClick={() => window.location.reload()}>Reload page</Button>
        <Link to="/" className={buttonClasses("secondary")}>
          Go home
        </Link>
      </div>
    </div>
  );
}
