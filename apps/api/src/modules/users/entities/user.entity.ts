import {
  Entity,
  PrimaryColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
} from 'typeorm';
import { v7 as uuidv7 } from 'uuid';

export enum UserRole {
  USER = 'user',
  ADMIN = 'admin',
}

// [v84-2-1-1][back-nestjs:entities]
@Entity('users')
export class User {
  @PrimaryColumn('uuid')
  id: string = uuidv7();

  @Column({ name: 'username', type: 'varchar', unique: true })
  username!: string;

  @Column({ name: 'email', type: 'varchar', unique: true })
  email!: string;

  @Column({ name: 'password_hash', type: 'varchar' })
  passwordHash!: string;

  @Column({ name: 'role', type: 'enum', enum: UserRole, default: UserRole.USER })
  role!: UserRole;

  @Column({ name: 'two_factor_enabled', type: 'boolean', default: false })
  twoFactorEnabled!: boolean;

  @Column({ name: 'two_factor_secret', type: 'varchar', nullable: true })
  twoFactorSecret!: string | null;

  @CreateDateColumn({ name: 'created_at' })
  createdAt!: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt!: Date;
}
