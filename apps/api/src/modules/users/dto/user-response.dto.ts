// [v84-2-4-1][back-nestjs:api]
import { ApiProperty } from '@nestjs/swagger';
import { User, UserRole } from '../entities';

export class UserResponseDto {
  @ApiProperty()
  id!: string;

  @ApiProperty()
  username!: string;

  @ApiProperty()
  email!: string;

  @ApiProperty({ enum: UserRole })
  role!: UserRole;

  @ApiProperty()
  twoFactorEnabled!: boolean;

  @ApiProperty()
  createdAt!: Date;
}

// Centralized projection from the entity to the response DTO. Strips
// `passwordHash` and `twoFactorSecret` so they never leak through any endpoint
// that returns a User. Use this anywhere we'd otherwise be tempted to cast.
export function toUserResponse(user: User): UserResponseDto {
  return {
    id: user.id,
    username: user.username,
    email: user.email,
    role: user.role,
    twoFactorEnabled: user.twoFactorEnabled,
    createdAt: user.createdAt,
  };
}
