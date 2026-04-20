// [v84-1-3][back-nestjs:api]
import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { AppModule } from './app.module';
async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  const configService = app.get(ConfigService);

  // CORS is intentionally NOT enabled. The browser only ever talks to the
  // Next.js BFF (apps/web/src/app/api/*), which calls this api server-to-server
  // over the docker network — server-side fetch doesn't trigger CORS. If you
  // ever need to call this api from a real browser origin, re-enable CORS here.

  app.setGlobalPrefix(configService.get<string>('app.prefix')!);

  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  const config = new DocumentBuilder()
    .setTitle(configService.get<string>('app.name')!)
    .setDescription(configService.get<string>('app.description')!)
    .setVersion(configService.get<string>('app.version')!)
    .build();
  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('api/docs', app, document);

  const port = configService.get<number>('app.port')!;
  await app.listen(port);
}
bootstrap();
