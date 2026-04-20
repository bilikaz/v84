import { IsString } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';

// [v84-2-2-1][back-nestjs:api]
export class AppleLoginDto {
  @ApiProperty()
  @IsString()
  identityToken!: string;
}
