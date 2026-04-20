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
