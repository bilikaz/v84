// [v84-3-2-1][back-nestjs:api]
import { ApiProperty } from '@nestjs/swagger';
import { IsEmail } from 'class-validator';

export class ForgotPasswordDto {
  @ApiProperty({ example: 'parent@example.com' })
  @IsEmail()
  email!: string;
}
