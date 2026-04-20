// [v84-2-2-2][back-nestjs:api]
import { Injectable } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';

@Injectable()
export class RefreshAuthGuard extends AuthGuard('jwt-refresh') {}
