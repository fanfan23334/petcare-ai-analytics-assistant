-- ============================================================
-- PetCare AI Analytics Assistant - Database Schema
-- 宠物医院智能数据分析助手 - 数据库结构
-- MySQL 8.0+  utf8mb4
-- ============================================================

CREATE DATABASE IF NOT EXISTS petcare_db
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE petcare_db;

-- ------------------------------------------------------------
-- 1. owners 客户表：宠物主人（医院客户）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS owners (
    owner_id   INT          NOT NULL AUTO_INCREMENT COMMENT '客户ID',
    name       VARCHAR(50)  NOT NULL                COMMENT '姓名',
    phone      VARCHAR(20)  NOT NULL                COMMENT '联系电话',
    email      VARCHAR(100) NULL                    COMMENT '邮箱',
    address    VARCHAR(200) NULL                    COMMENT '家庭住址',
    city       VARCHAR(50)  NOT NULL                COMMENT '所在城市',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
    PRIMARY KEY (owner_id),
    UNIQUE KEY uk_owners_phone (phone),
    KEY idx_owners_city (city)
) ENGINE=InnoDB COMMENT='客户表：宠物主人，医院服务的对象';

-- ------------------------------------------------------------
-- 2. doctors 医生表：医院兽医（服务提供方）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS doctors (
    doctor_id INT           NOT NULL AUTO_INCREMENT COMMENT '医生ID',
    name      VARCHAR(50)   NOT NULL                COMMENT '姓名',
    specialty VARCHAR(50)   NOT NULL                COMMENT '专科方向：内科/外科/皮肤科/牙科/眼科/心脏科/骨科/营养科',
    title     VARCHAR(30)   NOT NULL                COMMENT '职称：主任医师/副主任医师/主治医师',
    phone     VARCHAR(20)   NULL                    COMMENT '联系电话',
    hire_date DATE          NOT NULL                COMMENT '入职日期',
    salary    DECIMAL(10,2) NOT NULL                COMMENT '月薪（元）',
    status    ENUM('active','on_leave') NOT NULL DEFAULT 'active' COMMENT '在职状态',
    PRIMARY KEY (doctor_id),
    KEY idx_doctors_specialty (specialty),
    KEY idx_doctors_status (status)
) ENGINE=InnoDB COMMENT='医生表：兽医，收入/工作量分析的主体';

-- ------------------------------------------------------------
-- 3. pets 宠物表：患者（owner 拥有的宠物）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pets (
    pet_id     INT           NOT NULL AUTO_INCREMENT COMMENT '宠物ID',
    owner_id   INT           NOT NULL                COMMENT '所属客户ID',
    name       VARCHAR(50)   NOT NULL                COMMENT '宠物昵称',
    species    ENUM('cat','dog','bird','rabbit','hamster','reptile','other')
                              NOT NULL                COMMENT '物种：cat猫/dog狗/bird鸟/rabbit兔/hamster仓鼠/reptile爬宠/other其他',
    breed      VARCHAR(50)   NULL                    COMMENT '品种（如 英短/金毛）',
    gender     ENUM('male','female') NOT NULL        COMMENT '性别：male公/female母',
    birth_date DATE          NULL                    COMMENT '出生日期（可推算年龄）',
    weight     DECIMAL(5,2)  NULL                    COMMENT '体重(kg)',
    neutered   TINYINT(1)    NOT NULL DEFAULT 0      COMMENT '是否绝育：1是/0否',
    created_at DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '建档时间',
    PRIMARY KEY (pet_id),
    KEY idx_pets_owner (owner_id),
    KEY idx_pets_species (species),
    CONSTRAINT fk_pets_owner FOREIGN KEY (owner_id) REFERENCES owners (owner_id)
) ENGINE=InnoDB COMMENT='宠物表：患者，owner -> pet 一对多';

-- ------------------------------------------------------------
-- 4. appointments 预约表：预约排期（doctor 工作量来源）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS appointments (
    appointment_id   INT          NOT NULL AUTO_INCREMENT COMMENT '预约ID',
    pet_id           INT          NOT NULL                COMMENT '宠物ID',
    doctor_id        INT          NOT NULL                COMMENT '医生ID',
    appointment_date DATE         NOT NULL                COMMENT '预约日期',
    appointment_time TIME         NOT NULL                COMMENT '预约时段',
    reason           VARCHAR(200) NULL                    COMMENT '预约原因（如 疫苗/绝育/皮肤病复诊）',
    status           ENUM('booked','completed','cancelled','no_show')
                                   NOT NULL DEFAULT 'booked' COMMENT '状态：booked已预约/completed已完成/cancelled已取消/no_show爽约',
    created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '预约创建时间',
    PRIMARY KEY (appointment_id),
    KEY idx_appointments_date (appointment_date),
    KEY idx_appointments_status (status),
    KEY idx_appointments_doctor (doctor_id),
    KEY idx_appointments_pet (pet_id),
    CONSTRAINT fk_appointments_pet FOREIGN KEY (pet_id) REFERENCES pets (pet_id),
    CONSTRAINT fk_appointments_doctor FOREIGN KEY (doctor_id) REFERENCES doctors (doctor_id)
) ENGINE=InnoDB COMMENT='预约表：医生工作量、预约情况分析的数据来源';

-- ------------------------------------------------------------
-- 5. medical_records 诊疗记录表：就诊过程与诊断
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS medical_records (
    record_id      INT           NOT NULL AUTO_INCREMENT COMMENT '记录ID',
    pet_id         INT           NOT NULL                COMMENT '宠物ID',
    doctor_id      INT           NOT NULL                COMMENT '接诊医生ID',
    appointment_id INT           NULL                    COMMENT '关联预约ID（可为空：急诊/复诊直录）',
    record_date    DATE          NOT NULL                COMMENT '就诊日期',
    diagnosis      VARCHAR(200)  NOT NULL                COMMENT '诊断结果（如 猫瘟/皮肤真菌感染）',
    treatment      VARCHAR(500)  NULL                    COMMENT '治疗方案',
    medicine       VARCHAR(500)  NULL                    COMMENT '用药情况',
    notes          VARCHAR(500)  NULL                    COMMENT '医嘱/备注',
    PRIMARY KEY (record_id),
    KEY idx_records_pet (pet_id),
    KEY idx_records_doctor (doctor_id),
    KEY idx_records_date (record_date),
    CONSTRAINT fk_records_pet FOREIGN KEY (pet_id) REFERENCES pets (pet_id),
    CONSTRAINT fk_records_doctor FOREIGN KEY (doctor_id) REFERENCES doctors (doctor_id),
    CONSTRAINT fk_records_appointment FOREIGN KEY (appointment_id) REFERENCES appointments (appointment_id)
) ENGINE=InnoDB COMMENT='诊疗记录表：疾病分布、诊疗量分析的数据来源';

-- ------------------------------------------------------------
-- 6. bills 账单表：收费明细（收入分析核心）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bills (
    bill_id        INT            NOT NULL AUTO_INCREMENT COMMENT '账单ID',
    pet_id         INT            NOT NULL                COMMENT '宠物ID',
    doctor_id      INT            NOT NULL                COMMENT '负责医生ID',
    record_id      INT            NULL                    COMMENT '关联诊疗记录ID（疫苗/美容等可独立收费，可为空）',
    item_type      ENUM('consultation','examination','surgery','medicine',
                        'vaccine','hospitalization','grooming')
                                     NOT NULL             COMMENT '收费类型：consultation诊查费/examination检查费/surgery手术费/medicine药品费/vaccine疫苗费/hospitalization住院费/grooming美容费',
    item_desc      VARCHAR(200)   NOT NULL                COMMENT '收费项目描述（如 血常规检查/猫三联疫苗）',
    amount         DECIMAL(10,2)  NOT NULL                COMMENT '金额（元）',
    billed_date    DATE           NOT NULL                COMMENT '收费日期',
    pay_status     ENUM('paid','unpaid','refunded')
                                     NOT NULL DEFAULT 'paid' COMMENT '支付状态：paid已支付/unpaid未支付/refunded已退款',
    payment_method ENUM('cash','wechat','alipay','card')  NULL COMMENT '支付方式：现金/微信/支付宝/银行卡',
    PRIMARY KEY (bill_id),
    KEY idx_bills_doctor (doctor_id),
    KEY idx_bills_pet (pet_id),
    KEY idx_bills_date (billed_date),
    KEY idx_bills_paystatus (pay_status),
    CONSTRAINT fk_bills_pet FOREIGN KEY (pet_id) REFERENCES pets (pet_id),
    CONSTRAINT fk_bills_doctor FOREIGN KEY (doctor_id) REFERENCES doctors (doctor_id),
    CONSTRAINT fk_bills_record FOREIGN KEY (record_id) REFERENCES medical_records (record_id)
) ENGINE=InnoDB COMMENT='账单表：收入分析的核心数据';
