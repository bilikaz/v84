// [v84-1-3][back-nestjs:api]
import 'dotenv/config';
import { DataSource } from 'typeorm';
import databaseConfig from '../config/database.config';

const cfg = databaseConfig();

export const AppDataSource = new DataSource({
  type: 'mysql',
  host: cfg.host,
  port: cfg.port,
  username: cfg.username,
  password: cfg.password,
  database: cfg.name,
  entities: [__dirname + '/../modules/**/entities/*.entity{.ts,.js}'],
  migrations: [__dirname + '/migrations/*{.ts,.js}'],
  synchronize: false,
  timezone: 'Z',
});
