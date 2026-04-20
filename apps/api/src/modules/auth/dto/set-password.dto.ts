import { ApiProperty } from '@nestjs/swagger';
import { IsString, MinLength, IsStrongPassword } from 'class-validator';

// [v84-3-1-1][back-nestjs:api]
export class SetPasswordDto {
  @ApiProperty({ description: 'One-time invitation/reset token' })
  @IsString()
  token!: string;

  @ApiProperty({ description: 'Min 10 chars, 1 uppercase, 1 number, 1 symbol' })
  @IsString()
  @MinLength(10)
  @IsStrongPassword({ minUppercase: 1, minNumbers: 1, minSymbols: 1, minLowercase: 0 })
  password!: string;
}
