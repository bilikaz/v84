// [v84-4][back-nestjs:api] — session management endpoints (iter 4 "active sessions" scope)
import { Controller, Get, Delete, Param, UseGuards, HttpCode, HttpStatus } from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { SessionsService } from './sessions.service';
import { SessionResponseDto, toSessionResponse } from './dto';
import { JwtAuthGuard } from '../../common/guards';
import { CurrentUser } from '../../common/decorators';
import { User } from '../users/entities';

@ApiTags('sessions')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('users/me/sessions')
export class SessionsController {
  constructor(private readonly sessionsService: SessionsService) {}

  @Get()
  @ApiOperation({ summary: 'List active sessions for the current user' })
  async list(
    @CurrentUser() user: User & { sessionId?: string },
  ): Promise<SessionResponseDto[]> {
    const sessions = await this.sessionsService.findByUser(user.id);
    return sessions.map((s) => toSessionResponse(s, user.sessionId));
  }

  @Delete('all')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Revoke every session except the current one' })
  async revokeAll(@CurrentUser() user: User & { sessionId?: string }): Promise<void> {
    await this.sessionsService.revokeAll(user.id, user.sessionId);
  }

  @Delete(':sessionId')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Revoke a single session by id' })
  async revoke(
    @Param('sessionId') sessionId: string,
    @CurrentUser() user: User & { sessionId?: string },
  ): Promise<void> {
    await this.sessionsService.revoke(sessionId, user.id, user.sessionId);
  }
}
