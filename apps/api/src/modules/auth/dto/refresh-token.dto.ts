// [v84-2-2-1][back-nestjs:api]
import { IsString } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';

export class RefreshTokenDto {
  @ApiProperty()
  @IsString()
  refreshToken!: string;
}
