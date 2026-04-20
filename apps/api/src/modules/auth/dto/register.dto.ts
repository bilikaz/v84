// [v84-3-1-1][back-nestjs:api]
import { ApiProperty } from '@nestjs/swagger';
import { IsEmail, IsString, MinLength } from 'class-validator';

// Step 1: user submits just an email; we send a verification link.
export class RegisterDto {
  @ApiProperty()
  @IsEmail()
  email!: string;
}

// [v84-3-1-2][back-nestjs:api]
// Step 2: user follows the link, fills in username + password, and we create the account.
export class CompleteRegistrationDto {
  @ApiProperty()
  @IsString()
  token!: string;

  @ApiProperty()
  @IsString()
  @MinLength(3)
  username!: string;

  @ApiProperty()
  @IsString()
  @MinLength(8)
  password!: string;
}
