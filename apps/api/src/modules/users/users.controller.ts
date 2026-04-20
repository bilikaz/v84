// [v84-2-4-1][back-nestjs:api]
import {
  Controller,
  Get,
  Post,
  Patch,
  Delete,
  Body,
  Param,
  Query,
  UseGuards,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { UsersService } from './users.service';
import {
  CreateUserDto,
  UpdateUserDto,
  AdminUpdateUserDto,
  UserResponseDto,
  ListUsersQueryDto,
  VerifyTwoFactorDto,
  DisableTwoFactorDto,
  RequestEmailChangeDto,
  ConfirmEmailChangeDto,
  toUserResponse,
} from './dto';
import { JwtAuthGuard, RolesGuard } from '../../common/guards';
import { CurrentUser, Roles } from '../../common/decorators';
import { PaginatedResponseDto } from '../../common/dto';
import { User, UserRole } from './entities';

@ApiTags('users')
@ApiBearerAuth()
@Controller('users')
export class UsersController {
  constructor(private readonly usersService: UsersService) {}

  // ── Self-management ──

  @Get('me')
  @UseGuards(JwtAuthGuard)
  @ApiOperation({ summary: 'Get current user profile' })
  async getMe(@CurrentUser() user: User): Promise<UserResponseDto> {
    return toUserResponse(user);
  }

  @Patch('me')
  @UseGuards(JwtAuthGuard)
  @ApiOperation({ summary: 'Update current user (password, username)' })
  async updateMe(
    @CurrentUser() user: User,
    @Body() dto: UpdateUserDto,
  ): Promise<UserResponseDto> {
    const updated = await this.usersService.update(user.id, dto);
    return toUserResponse(updated);
  }

  // ── 2FA ──

  @Post('me/2fa/enable')
  @UseGuards(JwtAuthGuard)
  @ApiOperation({ summary: 'Generate TOTP secret for 2FA setup' })
  async enableTwoFactor(@CurrentUser() user: User) {
    return this.usersService.enableTwoFactor(user.id);
  }

  @Post('me/2fa/verify')
  @HttpCode(HttpStatus.NO_CONTENT)
  @UseGuards(JwtAuthGuard)
  @ApiOperation({ summary: 'Confirm 2FA setup with a 6-digit TOTP code' })
  async verifyTwoFactor(
    @CurrentUser() user: User,
    @Body() dto: VerifyTwoFactorDto,
  ): Promise<void> {
    await this.usersService.verifyAndActivateTwoFactor(user.id, dto.code);
  }

  @Delete('me/2fa')
  @HttpCode(HttpStatus.NO_CONTENT)
  @UseGuards(JwtAuthGuard)
  @ApiOperation({ summary: 'Disable 2FA (requires password + TOTP code)' })
  async disableTwoFactor(
    @CurrentUser() user: User,
    @Body() dto: DisableTwoFactorDto,
  ): Promise<void> {
    await this.usersService.disableTwoFactor(user.id, dto.password, dto.code);
  }

  // ── Email change ──

  @Post('me/email')
  @HttpCode(HttpStatus.NO_CONTENT)
  @UseGuards(JwtAuthGuard)
  @ApiOperation({ summary: 'Request email change — sends confirmation to new address' })
  async requestEmailChange(
    @CurrentUser() user: User,
    @Body() dto: RequestEmailChangeDto,
  ): Promise<void> {
    await this.usersService.requestEmailChange(user.id, dto.newEmail, dto.currentPassword);
  }

  @Post('me/email/confirm')
  @UseGuards(JwtAuthGuard)
  @ApiOperation({ summary: 'Confirm email change with token from email' })
  async confirmEmailChange(
    @CurrentUser() user: User,
    @Body() dto: ConfirmEmailChangeDto,
  ): Promise<UserResponseDto> {
    const updated = await this.usersService.confirmEmailChange(dto.token);
    return toUserResponse(updated);
  }

  // ── Admin CRUD ──

  @Get()
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Roles(UserRole.ADMIN)
  @ApiOperation({ summary: 'List users (paginated, admin only)' })
  async findAll(@Query() query: ListUsersQueryDto): Promise<PaginatedResponseDto<UserResponseDto>> {
    const [users, total] = await this.usersService.findAll(query);
    return PaginatedResponseDto.from(users.map(toUserResponse), total, query.page, query.limit);
  }

  @Get(':id')
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Roles(UserRole.ADMIN)
  @ApiOperation({ summary: 'Get user by ID (admin only)' })
  async findOne(@Param('id') id: string): Promise<UserResponseDto> {
    const user = await this.usersService.findById(id);
    return toUserResponse(user);
  }

  @Post()
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Roles(UserRole.ADMIN)
  @ApiOperation({ summary: 'Create a new user (admin only)' })
  async create(@Body() dto: CreateUserDto): Promise<UserResponseDto> {
    const user = await this.usersService.create(dto);
    return toUserResponse(user);
  }

  @Patch(':id')
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Roles(UserRole.ADMIN)
  @ApiOperation({ summary: 'Update user by ID (admin only)' })
  async adminUpdate(
    @Param('id') id: string,
    @Body() dto: AdminUpdateUserDto,
  ): Promise<UserResponseDto> {
    const user = await this.usersService.adminUpdate(id, dto);
    return toUserResponse(user);
  }

  @Delete(':id')
  @HttpCode(HttpStatus.NO_CONTENT)
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Roles(UserRole.ADMIN)
  @ApiOperation({ summary: 'Delete user by ID (admin only)' })
  async remove(@Param('id') id: string): Promise<void> {
    await this.usersService.remove(id);
  }
}
