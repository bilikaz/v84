import { Entity, PrimaryColumn, Column, CreateDateColumn } from 'typeorm';

// [v84-2-1-1][back-nestjs:entities]
@Entity('sessions')
export class Session {
  @PrimaryColumn('uuid')
  id!: string;

  @Column({ name: 'user_id', type: 'varchar' })
  userId!: string;

  @Column({ name: 'refresh_token_hash', type: 'varchar' })
  refreshTokenHash!: string;

  @Column({ name: 'device_name', type: 'varchar', nullable: true })
  deviceName!: string | null;

  @Column({ name: 'device_os', type: 'varchar', nullable: true })
  deviceOs!: string | null;

  @Column({ name: 'ip_address', type: 'varchar', nullable: true })
  ipAddress!: string | null;

  @Column({ name: 'last_seen_at', type: 'datetime' })
  lastSeenAt!: Date;

  @CreateDateColumn({ name: 'created_at' })
  createdAt!: Date;
}
