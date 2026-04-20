// [v84-2-4-1][back-nestjs:api]
import { ApiProperty } from '@nestjs/swagger';
import { Type } from 'class-transformer';
import { IsInt, IsOptional, IsPositive, Max, Min } from 'class-validator';

export class ListQueryDto {
  @ApiProperty({ required: false, default: 1, minimum: 1 })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @IsPositive()
  @Min(1)
  page: number = 1;

  @ApiProperty({ required: false, default: 20, minimum: 1, maximum: 100 })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @IsPositive()
  @Min(1)
  @Max(100)
  limit: number = 20;
}

export class PaginatedResponseDto<T> {
  items!: T[];
  total!: number;
  page!: number;
  limit!: number;
  pages!: number;

  static from<T>(items: T[], total: number, page: number, limit: number): PaginatedResponseDto<T> {
    const dto = new PaginatedResponseDto<T>();
    dto.items = items;
    dto.total = total;
    dto.page = page;
    dto.limit = limit;
    dto.pages = Math.max(1, Math.ceil(total / limit));
    return dto;
  }
}
