import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/useAuth";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";

export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const registering = mode === "register";

  if (user) return <Navigate to="/" replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (registering) await register(name, email, password);
      else await login(email, password);
      navigate((location.state as { from?: string } | null)?.from ?? "/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto mt-20 max-w-sm px-4">
      <h1 className="mb-6 text-center text-2xl font-semibold text-indigo-700">AI Study Companion</h1>
      <Card title={registering ? "Create your account" : "Sign in"}>
        <form onSubmit={onSubmit} className="space-y-4">
          {registering && <Input label="Name" required value={name} onChange={(e) => setName(e.target.value)} />}
          <Input
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Input
            label="Password"
            type="password"
            autoComplete={registering ? "new-password" : "current-password"}
            minLength={registering ? 8 : undefined}
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}
          <Button type="submit" loading={busy} className="w-full">
            {registering ? "Create account" : "Sign in"}
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-slate-600">
          {registering ? "Already registered? " : "New here? "}
          <Link to={registering ? "/login" : "/register"} className="text-indigo-600 hover:underline">
            {registering ? "Sign in" : "Create an account"}
          </Link>
        </p>
      </Card>
    </div>
  );
}
