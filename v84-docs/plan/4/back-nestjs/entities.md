[v84-4-1-1]#1 Add 2FA columns to User entity
  task: add `twoFactorEnabled` (boolean, default false) and `twoFactorSecret` (nullable varchar) columns to the User entity using the project's snake_case column-naming convention: `@Column({ name: 'two_factor_enabled', default: false }) twoFactorEnabled!: boolean;` and `@Column({ name: 'two_factor_secret', nullable: true, type: 'varchar' }) twoFactorSecret!: string | null;`.
  files: apps/api/src/modules/users/entities/user.entity.ts
  depends: [v84-2-1-1]#1
