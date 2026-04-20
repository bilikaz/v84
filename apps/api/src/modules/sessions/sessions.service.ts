// [v84-2-1-2][back-nestjs:services]
import { Injectable, NotFoundException, ForbiddenException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Session } from './entities';
import { RedisService } from '../../database';

@Injectable()
export class SessionsService {
  constructor(
    @InjectRepository(Session)
    private readonly sessionRepository: Repository<Session>,
    private readonly redisService: RedisService,
  ) {}

  async findByUser(userId: string): Promise<Session[]> {
    return this.sessionRepository.find({
      where: { userId },
      order: { lastSeenAt: 'DESC' },
    });
  }

  async revoke(sessionId: string, userId: string, currentSessionId?: string): Promise<void> {
    if (sessionId === currentSessionId) {
      throw new ForbiddenException('Cannot revoke current session from session list');
    }
    const session = await this.sessionRepository.findOne({
      where: { id: sessionId, userId },
    });
    if (!session) throw new NotFoundException('Session not found');
    await this.redisService.del(`refresh:${sessionId}`);
    await this.sessionRepository.delete(sessionId);
  }

  async revokeAll(userId: string, currentSessionId?: string): Promise<void> {
    const sessions = await this.findByUser(userId);
    const toRevoke = currentSessionId
      ? sessions.filter((s) => s.id !== currentSessionId)
      : sessions;
    await Promise.all(toRevoke.map((s) => this.redisService.del(`refresh:${s.id}`)));
    if (toRevoke.length > 0) {
      await this.sessionRepository.delete(toRevoke.map((s) => s.id));
    }
  }

  async updateLastSeen(sessionId: string): Promise<void> {
    await this.sessionRepository.update(sessionId, { lastSeenAt: new Date() });
  }
}
