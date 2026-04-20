
# --- iteration 2 ---
[v84-2-1-1]#1 Verify database indexes for auth performance
  task: Verify that Session.user_id and User.email have `@Index` decorators in the TypeORM entities to ensure the migration generator includes them, rather than relying on manual DB verification.
[v84-2-2-2]#1 Prevent N+1 queries in auth guards
  task: Inspect guard execution flow to ensure user/role resolution happens via a single query or shared cache, preventing redundant database calls on every protected route hit.
[v84-2-3-2]#1 Isolate auth context to prevent full-tree re-renders
  task: Verify the auth provider returns a stable context object reference and splits token management from UI state to block unnecessary re-renders during token refresh cycles.
[v84-2-4-1]#1 Enforce pagination and eager loading on user list
  task: Verify the admin user list endpoint implements pagination and joins related roles/profiles in the initial query to eliminate N+1 patterns on table data fetching.
[v84-2-4-2]#1 Optimize admin table rendering stability
  task: Verify the user management table isolates row components from auth state updates and uses memoization or stable state slices to prevent table re-renders on token rotation.

# --- iteration 3 ---
[v84-3-1-1]#1 Registration endpoint triggers N+1 or unnecessary joins during user creation
  risk: Creating a user record via POST /auth/register loads related entities (e.g., sessions, profiles) into memory or triggers lazy-loaded relations, increasing DB load per registration
  impact: degraded registration throughput and higher database CPU under concurrent sign-ups
  action: the register service must insert only the User entity and required auth relations in a single query; lazy-loaded relations must not be accessed or eagerly joined during creation
[v84-3-1-2]#1 Verify email endpoint causes unnecessary re-renders on landing pages
  risk: GET /auth/verify/:token updates the auth context or triggers a state update that bubbles through global providers, forcing VerifyEmailPage and UserDashboardPage to re-render even when their local data hasn't changed
  impact: visible UI flicker or layout shift after successful verification, degrading user experience
  action: context updates from verification must be scoped to token-only state; UI state for verified pages must be isolated from auth provider re-renders
[v84-3-2-1]#1 Forgot password lookup bypasses indexes or triggers unnecessary joins
  risk: POST /auth/forgot-password performs a full table scan or joins unrelated relations to find the user instead of querying the indexed email column directly
  impact: database CPU spikes and slow response times as the user table grows; potential account enumeration via timing differences caused by query depth
  action: the lookup must rely solely on the indexed email column, return identical status and timing regardless of existence, and avoid loading related entities during the search
[v84-3-2-2]#1 Reset password invalidates sessions via N+1 or heavy joins
  risk: POST /auth/reset-password queries or joins all related sessions for the user to invalidate them, causing an N+1 pattern or excessive memory usage on the DB
  impact: latency spikes during password changes; database connection pool exhaustion under concurrent reset requests
  action: session invalidation must use a targeted DELETE or bulk update against the sessions table indexed by user_id; related session objects must not be loaded into the application context

# --- iteration 4 ---
[v84-4-1-2]#1 Login endpoint loads unnecessary relations when checking 2FA status
  risk: POST /auth/login fetches the full user entity or joins related tables (e.g., sessions, roles) just to check is2faEnabled before validating password or processing 2FA.
  impact: login latency increases and database CPU spikes under high concurrent authentication traffic.
  action: the login query must select only email, passwordHash, and is2faEnabled without joining or eager-loading relations.
[v84-4-3-1]#1 Session listing triggers N+1 or loads full user objects
  risk: GET /auth/sessions fetches the user entity and iterates over a lazy-loaded sessions relation, or joins the user table unnecessarily for each row.
  impact: database load increases linearly with the number of active sessions per user; API response time degrades for users with many devices.
  action: the endpoint must query the sessions table directly using the user_id index, selecting only display fields, and must not load or join the parent User entity.
[v84-4-1-1]#1 2FA toggle triggers full auth context re-renders
  risk: Enabling or disabling 2FA updates the global auth context with the full user payload, causing the entire settings page and sibling components to re-render unnecessarily.
  impact: UI flicker on the settings page; wasted client-side CPU during rapid UI interactions.
  action: context updates from 2FA changes must be scoped to a lightweight boolean or token flag; UI components must subscribe only to the 2FA slice, not the entire user object.
