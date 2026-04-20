import { ApiProperty } from '@nestjs/swagger';
import { Session } from '../entities';

// [v84-4-3-1][back-nestjs:api]
export class SessionResponseDto {
  @ApiProperty()
  id!: string;

  @ApiProperty({ nullable: true })
  deviceName!: string | null;

  @ApiProperty({ nullable: true })
  deviceOs!: string | null;

  @ApiProperty({ nullable: true })
  ipAddress!: string | null;

  @ApiProperty()
  lastSeenAt!: Date;

  @ApiProperty()
  createdAt!: Date;

  @ApiProperty({ description: 'True if this is the session that made the request.' })
  current!: boolean;
}

export function toSessionResponse(session: Session, currentSessionId?: string): SessionResponseDto {
  return {
    id: session.id,
    deviceName: session.deviceName,
    deviceOs: session.deviceOs,
    ipAddress: session.ipAddress,
    lastSeenAt: session.lastSeenAt,
    createdAt: session.createdAt,
    current: session.id === currentSessionId,
  };
}
