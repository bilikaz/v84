import { Injectable } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';

// [v84-2-2-2][back-nestjs:api]
@Injectable()
export class GoogleAuthGuard extends AuthGuard('google-id-token') {}
