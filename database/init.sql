-- ============================================================
-- 投融资知识库管理平台 - MySQL 8 初始化脚本
-- 覆盖技能 01~05 涉及的全部数据表
-- 执行：mysql -u root -p < database/init.sql
-- ============================================================

-- 关键：声明客户端连接字符集为 utf8mb4，避免中文种子数据被二次编码（mojibake）
SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS `investment_finance`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `investment_finance`;

-- ------------------------------------------------------------
-- 02 组织与权限：内部员工
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
  `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `username`      VARCHAR(64)     NOT NULL COMMENT '登录名',
  `password_hash` VARCHAR(128)    NOT NULL COMMENT '密码哈希',
  `display_name`  VARCHAR(64)     NOT NULL COMMENT '姓名',
  `department_id` BIGINT UNSIGNED NULL COMMENT '所属团队/基金/项目组',
  `status`        TINYINT         NOT NULL DEFAULT 1 COMMENT '1 启用 0 停用',
  `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`),
  KEY `idx_department` (`department_id`)
) ENGINE=InnoDB COMMENT='内部员工';

-- ------------------------------------------------------------
-- 02 组织与权限：团队/基金/项目范围（树形）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `departments` (
  `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `parent_id`  BIGINT UNSIGNED NULL COMMENT '父节点',
  `name`       VARCHAR(128)    NOT NULL COMMENT '团队/基金/项目组名称',
  `dept_type`  VARCHAR(32)     NULL COMMENT '分类: team/fund/project/sub',
  `leader_id`  BIGINT UNSIGNED NULL COMMENT '负责人',
  `sort_order` INT             NOT NULL DEFAULT 0,
  `created_at` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_parent` (`parent_id`)
) ENGINE=InnoDB COMMENT='团队/基金/项目范围';

-- 兼容已有库：若 departments 缺 dept_type 列则自动补加
SET @has_col := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='departments' AND COLUMN_NAME='dept_type');
SET @ddl := IF(@has_col=0, 'ALTER TABLE `departments` ADD COLUMN `dept_type` VARCHAR(32) NULL COMMENT ''分类: team/fund/project/sub'' AFTER `name`', 'SELECT 1');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ------------------------------------------------------------
-- 02 组织与权限：角色
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `roles` (
  `id`          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `role_name`   VARCHAR(64)     NOT NULL COMMENT '角色名称',
  `role_code`   VARCHAR(64)     NOT NULL COMMENT '角色编码',
  `description` VARCHAR(255)    NULL,
  `created_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_role_code` (`role_code`)
) ENGINE=InnoDB COMMENT='角色';

-- ------------------------------------------------------------
-- 02 组织与权限：用户-角色关联
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `user_roles` (
  `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`    BIGINT UNSIGNED NOT NULL,
  `role_id`    BIGINT UNSIGNED NOT NULL,
  `created_at` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_role` (`user_id`, `role_id`),
  KEY `idx_role` (`role_id`)
) ENGINE=InnoDB COMMENT='用户角色关联';

-- ------------------------------------------------------------
-- 02 组织与权限：角色-操作权限
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `role_permissions` (
  `id`              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `role_id`         BIGINT UNSIGNED NOT NULL,
  `permission_code` VARCHAR(128)    NOT NULL COMMENT '权限编码，如 knowledge:import',
  `permission_type` VARCHAR(32)     NOT NULL COMMENT 'menu / button',
  `created_at`      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_role_perm` (`role_id`, `permission_code`),
  KEY `idx_perm_code` (`permission_code`)
) ENGINE=InnoDB COMMENT='角色操作权限';

-- ------------------------------------------------------------
-- 01 投融资知识维护：知识单元
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `knowledge_units` (
  `id`               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `unit_code`        VARCHAR(64)     NOT NULL COMMENT '知识单元编号',
  `title`            VARCHAR(255)    NOT NULL,
  `content`          MEDIUMTEXT      NULL COMMENT '正文',
  `summary`          VARCHAR(1000)   NULL COMMENT '摘要',
  `category`         VARCHAR(64)     NULL COMMENT '类别：尽调/投决/协议/投后等',
  `source_file_name` VARCHAR(255)    NULL,
  `file_type`        VARCHAR(16)     NULL COMMENT 'pdf/markdown/word/txt',
  `file_size`        BIGINT UNSIGNED NULL,
  -- 投融资扩展字段
  `industry`         VARCHAR(64)     NULL COMMENT '行业赛道',
  `financing_round`  VARCHAR(32)     NULL COMMENT '融资轮次',
  `amount`           DECIMAL(18,2)   NULL COMMENT '融资金额',
  `currency`         VARCHAR(8)      NULL COMMENT '币种',
  `valuation`        DECIMAL(18,2)   NULL COMMENT '估值',
  `region`           VARCHAR(64)     NULL COMMENT '地区',
  `deal_stage`       VARCHAR(32)     NULL COMMENT '项目阶段：尽调/投决/投后等',
  `confidential_level` TINYINT       NOT NULL DEFAULT 1 COMMENT '保密级别 1~5',
  -- 通用字段
  `status`           VARCHAR(32)     NOT NULL DEFAULT 'active' COMMENT '状态：active/archived/draft',
  `version`          INT             NOT NULL DEFAULT 1 COMMENT '版本号',
  `index_status`     VARCHAR(16)     NOT NULL DEFAULT 'pending' COMMENT '向量索引状态 pending/indexed/failed',
  `vector_synced_at` DATETIME        NULL COMMENT '向量同步时间',
  `creator_id`       BIGINT UNSIGNED NULL,
  `created_at`       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_unit_code` (`unit_code`),
  KEY `idx_industry` (`industry`),
  KEY `idx_deal_stage` (`deal_stage`),
  KEY `idx_status` (`status`),
  KEY `idx_index_status` (`index_status`)
) ENGINE=InnoDB COMMENT='投融资知识单元';

-- ------------------------------------------------------------
-- 02 组织与权限：知识单元数据权限（四维）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `unit_permissions` (
  `id`          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `unit_id`     BIGINT UNSIGNED NOT NULL,
  `target_type` VARCHAR(16)     NOT NULL COMMENT 'global / department / role / user',
  `target_id`   BIGINT UNSIGNED NOT NULL COMMENT '全局公开时 target_id=0',
  `created_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_unit` (`unit_id`),
  KEY `idx_target` (`target_type`, `target_id`)
) ENGINE=InnoDB COMMENT='知识单元数据权限';

-- ------------------------------------------------------------
-- 03/04 问答会话与访问日志
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `qa_sessions` (
  `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `session_id` CHAR(36)        NOT NULL,
  `user_id`    BIGINT UNSIGNED NOT NULL,
  `title`      VARCHAR(255)    NULL COMMENT '会话标题（取首问）',
  `created_at` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_session` (`session_id`),
  KEY `idx_user` (`user_id`)
) ENGINE=InnoDB COMMENT='问答会话';

CREATE TABLE IF NOT EXISTS `qa_messages` (
  `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `session_id` CHAR(36)        NOT NULL,
  `role`       VARCHAR(16)     NOT NULL COMMENT 'user / assistant',
  `content`    MEDIUMTEXT      NULL,
  `created_at` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_session` (`session_id`)
) ENGINE=InnoDB COMMENT='问答消息';

CREATE TABLE IF NOT EXISTS `qa_access_logs` (
  `id`                        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `session_id`                CHAR(36)        NULL,
  `user_id`                   BIGINT UNSIGNED NOT NULL,
  `question`                  TEXT            NULL,
  `answer`                    MEDIUMTEXT      NULL,
  `recalled_unit_ids_json`    JSON            NULL,
  `authorized_unit_ids_json`  JSON            NULL,
  `unauthorized_unit_ids_json` JSON           NULL,
  `prompt_tokens`             INT UNSIGNED    NULL,
  `completion_tokens`         INT UNSIGNED    NULL,
  `total_tokens`              INT UNSIGNED    NULL,
  `response_time_ms`          INT UNSIGNED    NULL,
  `created_at`                DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user` (`user_id`),
  KEY `idx_created` (`created_at`)
) ENGINE=InnoDB COMMENT='问答访问日志';

-- ------------------------------------------------------------
-- 05 知识沉淀：FAQ
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `faqs` (
  `id`             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `question`       VARCHAR(500)    NOT NULL,
  `answer`         MEDIUMTEXT      NULL,
  `category`       VARCHAR(64)     NULL COMMENT '尽调/条款/合规等',
  `related_unit_id` BIGINT UNSIGNED NULL,
  `source_type`    VARCHAR(32)     NOT NULL DEFAULT 'manual' COMMENT 'manual / auto_mined',
  `status`         VARCHAR(32)     NOT NULL DEFAULT 'pending_review' COMMENT 'pending_review / published / rejected',
  `hit_count`      INT UNSIGNED    NOT NULL DEFAULT 0,
  `reviewer_id`    BIGINT UNSIGNED NULL,
  `reviewed_at`    DATETIME        NULL,
  `created_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_status` (`status`),
  KEY `idx_category` (`category`)
) ENGINE=InnoDB COMMENT='FAQ';

-- ------------------------------------------------------------
-- 05 知识沉淀：知识缺口
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `knowledge_gaps` (
  `id`                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `question_pattern`     VARCHAR(500)    NOT NULL COMMENT '缺口问题模式',
  `sample_questions_json` JSON           NULL,
  `ask_count`            INT UNSIGNED    NOT NULL DEFAULT 1,
  `last_asked_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `status`               VARCHAR(32)     NOT NULL DEFAULT 'unresolved' COMMENT 'unresolved / resolved / ignored',
  `resolved_unit_id`     BIGINT UNSIGNED NULL,
  `created_at`           DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`           DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB COMMENT='知识缺口';

-- ============================================================
-- 种子数据
-- ============================================================

-- 团队/基金/项目范围
INSERT INTO `departments` (`id`, `parent_id`, `name`, `sort_order`) VALUES
  (1, NULL, '投资部', 1),
  (2, 1, '一期基金', 1),
  (3, 1, '二期基金', 2);

-- 角色：投资经理、投委会、风控、法务、财务、运营
INSERT INTO `roles` (`id`, `role_name`, `role_code`, `description`) VALUES
  (1, '系统管理员', 'admin', '维护用户、团队、角色与权限'),
  (2, '投资经理', 'investment_manager', '维护所负责项目、标的与融资需求'),
  (3, '投资总监/合伙人', 'investment_partner', '查看授权项目组合、投决材料与业务看板'),
  (4, '投委会成员', 'ic_member', '查看进入投决流程的项目资料、尽调结论与风险意见'),
  (5, '风控', 'risk_control', '查看尽调、合规材料，维护风险知识'),
  (6, '法务', 'legal', '查看协议、合规材料'),
  (7, '财务', 'finance', '查看财务材料'),
  (8, '运营/IR', 'ir_operation', '维护融资需求、资金方信息、投后报告');

-- 初始管理员（密码 admin123 的 bcrypt cost=12 哈希）
INSERT INTO `users` (`id`, `username`, `password_hash`, `display_name`, `department_id`, `status`) VALUES
  (1, 'admin', '$2b$12$yiWGaU2vMKh.xsxV7Hfq8.hMw7d.0y4OsPF81dPguQOkjZ7neVMSa', '系统管理员', 1, 1);

INSERT INTO `user_roles` (`user_id`, `role_id`) VALUES (1, 1);

-- 系统管理员操作权限示例
INSERT INTO `role_permissions` (`role_id`, `permission_code`, `permission_type`) VALUES
  (1, 'dashboard:view', 'menu'),
  (1, 'knowledge:view', 'menu'),
  (1, 'org:dept:manage', 'menu'),
  (1, 'qa:chat', 'menu'),
  (1, 'settlement:gap:view', 'menu'),
  (1, 'org:user:manage', 'button'),
  (1, 'org:role:manage', 'button'),
  (1, 'knowledge:import', 'button'),
  (1, 'knowledge:manage', 'button'),
  (1, 'settlement:faq:review', 'button');
