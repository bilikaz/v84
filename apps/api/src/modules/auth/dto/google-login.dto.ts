import { IsString } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';

// [v84-2-2-1][back-nestjs:api]
export class GoogleLoginDto {
  @ApiProperty()
  @IsString()
  idToken!: string;
}
