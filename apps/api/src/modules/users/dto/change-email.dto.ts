import { ApiProperty } from '@nestjs/swagger';
import { IsEmail, IsString } from 'class-validator';

// [v84-4-2-2][back-nestjs:api]
export class RequestEmailChangeDto {
  @ApiProperty()
  @IsEmail()
  newEmail!: string;

  @ApiProperty()
  @IsString()
  currentPassword!: string;
}

export class ConfirmEmailChangeDto {
  @ApiProperty()
  @IsString()
  token!: string;
}
