// [v84-2-2-1][back-nestjs:api]
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsEmail, IsOptional, IsString, Length } from 'class-validator';

export class LoginDto {
  @ApiProperty({ example: 'admin@school.example' })
  @IsEmail()
  email!: string;

  @ApiProperty()
  @IsString()
  password!: string;

  @ApiPropertyOptional({ example: '123456', description: '6-digit TOTP code (required when 2FA is enabled)' })
  @IsOptional()
  @IsString()
  @Length(6, 6)
  totpCode?: string;
}
