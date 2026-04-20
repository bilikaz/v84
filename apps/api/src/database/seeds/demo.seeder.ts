// [v84-2-1-3][back-nestjs:entities]
import * as bcrypt from 'bcrypt';
import { faker } from '@faker-js/faker';
import { DataSource } from 'typeorm';
import { UserRole } from '../../modules/users/entities/user.entity';
import {
  createUser
} from '../factories';

const DEFAULT_PASSWORD = 'password';

export class DemoSeeder {
  async run(dataSource: DataSource): Promise<void> {
    const passwordHash = await bcrypt.hash(DEFAULT_PASSWORD, 10);

    await createUser(dataSource, {
      email: `user@user.localhost`,
      passwordHash,
      role: UserRole.USER,
    });

    await createUser(dataSource, {
      email: `admin@admin.localhost`,
      passwordHash,
      role: UserRole.ADMIN,
    });
  }
}
