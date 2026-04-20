// [v84-2-4-1][back-nestjs:api]
import { ApiPropertyOptional } from '@nestjs/swagger';
import { IsEnum, IsOptional, IsString } from 'class-validator';
import { ListQueryDto } from '../../../common/dto';
import { UserRole } from '../entities';

export class ListUsersQueryDto extends ListQueryDto {
  @ApiPropertyOptional({ enum: UserRole })
  @IsOptional()
  @IsEnum(UserRole)
  role?: UserRole;

  @ApiPropertyOptional({ description: 'Case-insensitive search on username or email' })
  @IsOptional()
  @IsString()
  search?: string;
}
