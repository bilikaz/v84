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
