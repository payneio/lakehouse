import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Waves, Lock, Eye, EyeOff, Loader2 } from 'lucide-react';
import { login } from '@/api/auth';
import { ApiError } from '@/api/client';

export function LoginPage() {
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(password);
      navigate('/home', { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError('Incorrect password.');
      } else {
        setError('Unable to sign in. Is the daemon running?');
      }
      setPassword('');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background p-4">
      {/* Soft decorative backdrop */}
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-32 -top-32 h-80 w-80 rounded-full bg-indigo-400/20 blur-3xl dark:bg-indigo-600/20" />
        <div className="absolute -bottom-32 -right-32 h-80 w-80 rounded-full bg-sky-400/20 blur-3xl dark:bg-sky-600/20" />
      </div>

      <div className="relative w-full max-w-sm">
        {/* Brand */}
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg">
            <Waves className="h-7 w-7" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Lakehouse</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">Your personal data platform</p>
        </div>

        {/* Card */}
        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border border-border bg-background p-6 shadow-xl"
        >
          <label htmlFor="password" className="mb-2 block text-sm font-medium text-foreground">
            Password
          </label>
          <div className="relative">
            <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              autoFocus
              autoComplete="current-password"
              aria-invalid={error ? true : undefined}
              className="w-full rounded-lg border border-input bg-background py-2.5 pl-10 pr-10 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              tabIndex={-1}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              className="absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>

          {error && (
            <div className="mt-3 rounded-lg border border-destructive bg-destructive/10 px-3 py-2 text-sm text-red-600 dark:text-red-400">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !password}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-primary py-2.5 text-sm font-medium text-primary-foreground shadow-sm transition-opacity hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Signing in…
              </>
            ) : (
              'Sign in'
            )}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Local-first · Private · Yours
        </p>
      </div>
    </div>
  );
}
