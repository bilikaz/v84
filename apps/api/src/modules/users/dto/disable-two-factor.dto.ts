import { ApiProperty } from '@nestjs/swagger';
import { IsString, Length } from 'class-validator';

// [v84-4-1-1][back-nestjs:api]
export class DisableTwoFactorDto {
  @ApiProperty()
  @IsString()
  password!: string;

  @ApiProperty({ example: '123456', description: '6-digit TOTP code' })
  @IsString()
  @Length(6, 6)
  code!: string;
}
