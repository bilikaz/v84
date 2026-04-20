[v84-2-1-1]#1 Update .env.example with auth variables
  task: append JWT_SECRET, JWT_EXPIRES_IN, REFRESH_TOKEN_EXPIRES_IN, SESSION_COOKIE_SECURE to docker/dev/.env.example with documentation comments
  files: docker/dev/.env.example
