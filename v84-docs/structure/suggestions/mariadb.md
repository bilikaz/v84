# Suggestion: MariaDB + Adminer

## When

Simple projects that don't need advanced PostgreSQL features (JSON queries, full-text search, complex aggregations).

## Rule

Suggest MariaDB as the database with Adminer as the web-based database manager.

When using MariaDB with TypeORM:
- Install `mysql2` as the npm driver — NOT `mariadb`. TypeORM uses the MySQL driver internally for both MySQL and MariaDB.
- Set TypeORM `type: 'mysql'` — NOT `type: 'mariadb'`. The `mariadb` type looks for the `mariadb` package which TypeORM doesn't properly support.
- Docker image stays `mariadb:latest` — the driver choice is separate from the database image.

## Why

Lighter and easier to set up than PostgreSQL + pgAdmin. Adminer is a single-file PHP app with a clean UI — much simpler for users who aren't database experts. Good default for straightforward CRUD apps.
