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
