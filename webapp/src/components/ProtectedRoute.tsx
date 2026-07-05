import { Navigate } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { getAuthStatus, getToken } from '@/api/auth';

/**
 * Gate for the authenticated app.
 *
 * - If the daemon has no password configured, renders children freely.
 * - If a password is configured but no token is stored, redirects to /login.
 * - Otherwise renders children; individual API calls will redirect to /login
 *   if the stored token turns out to be invalid (handled in the API client).
 */
export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['auth-status'],
    queryFn: getAuthStatus,
    staleTime: 1000 * 60,
    retry: false,
  });

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        Loading…
      </div>
    );
  }

  // If we can't reach the daemon, fail open rather than trapping the user.
  const authRequired = !isError && (data?.auth_required ?? false);

  if (authRequired && !getToken()) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
