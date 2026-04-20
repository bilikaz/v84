// [v84-2][back-nestjs:entities]
import { MigrationInterface, QueryRunner } from "typeorm";

export class Iteration21775911982357 implements MigrationInterface {
    name = 'Iteration21775911982357'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`CREATE TABLE \`users\` (\`id\` varchar(36) NOT NULL, \`username\` varchar(255) NOT NULL, \`email\` varchar(255) NOT NULL, \`password_hash\` varchar(255) NOT NULL, \`role\` enum ('user', 'admin') NOT NULL DEFAULT 'user', \`two_factor_enabled\` tinyint NOT NULL DEFAULT 0, \`two_factor_secret\` varchar(255) NULL, \`created_at\` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), \`updated_at\` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), UNIQUE INDEX \`IDX_fe0bb3f6520ee0469504521e71\` (\`username\`), UNIQUE INDEX \`IDX_97672ac88f789774dd47f7c8be\` (\`email\`), PRIMARY KEY (\`id\`)) ENGINE=InnoDB`);
        await queryRunner.query(`CREATE TABLE \`sessions\` (\`id\` varchar(255) NOT NULL, \`user_id\` varchar(255) NOT NULL, \`refresh_token_hash\` varchar(255) NOT NULL, \`device_name\` varchar(255) NULL, \`device_os\` varchar(255) NULL, \`ip_address\` varchar(255) NULL, \`last_seen_at\` datetime NOT NULL, \`created_at\` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), PRIMARY KEY (\`id\`)) ENGINE=InnoDB`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`DROP TABLE \`sessions\``);
        await queryRunner.query(`DROP INDEX \`IDX_97672ac88f789774dd47f7c8be\` ON \`users\``);
        await queryRunner.query(`DROP INDEX \`IDX_fe0bb3f6520ee0469504521e71\` ON \`users\``);
        await queryRunner.query(`DROP TABLE \`users\``);
    }

}
