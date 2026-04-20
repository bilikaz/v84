// [v84-2-1-3][back-nestjs:entities]
import { faker } from '@faker-js/faker';
import { DataSource } from 'typeorm';
import { User, UserRole } from '../../modules/users/entities/user.entity';

export function createUser(ds: DataSource, overrides: Partial<User> = {}): Promise<User> {
  const repo = ds.getRepository(User);
  return repo.save(
    repo.create({
      username: faker.internet.username().toLowerCase(),
      email: faker.internet.email().toLowerCase(),
      passwordHash: '',
      role: UserRole.USER,
      ...overrides,
    }),
  );
}
