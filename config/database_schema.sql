-- ─────────────────────────────────────────────────────────────────────────────
--  Academic Orchestrator — Database Schema
-- ─────────────────────────────────────────────────────────────────────────────

CREATE DATABASE IF NOT EXISTS academic_orchestrator
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE academic_orchestrator;

-- ── Courses ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS courses (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(255)    NOT NULL,
    code            VARCHAR(50),
    instructor      VARCHAR(255),
    semester        VARCHAR(50),
    syllabus_path   TEXT,
    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP
);

-- ── Deadlines ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deadlines (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    course_id       INT             NOT NULL,
    title           VARCHAR(500)    NOT NULL,
    description     TEXT,
    deadline_date   DATETIME        NOT NULL,
    deadline_type   ENUM('assignment','quiz','exam','project','presentation','other')
                                    DEFAULT 'assignment',
    weight_percent  FLOAT,
    is_completed    BOOLEAN         DEFAULT FALSE,
    cron_job_id     VARCHAR(100),   -- tracks the Linux cron entry
    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);

-- ── Notifications Log ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notification_log (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    deadline_id     INT,
    channel         ENUM('discord','email','both'),
    message         TEXT,
    sent_at         DATETIME        DEFAULT CURRENT_TIMESTAMP,
    status          ENUM('sent','failed') DEFAULT 'sent',
    FOREIGN KEY (deadline_id) REFERENCES deadlines(id) ON DELETE SET NULL
);

-- ── Research Sessions ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS research_sessions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    query           TEXT            NOT NULL,
    course_id       INT,
    summary         LONGTEXT,
    sources_json    JSON,           -- array of {url, title, snippet}
    github_repos    JSON,           -- array of {repo, stars, url}
    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL
);

-- ── Team Members ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS team_members (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    github_username VARCHAR(100)    NOT NULL UNIQUE,
    discord_id      VARCHAR(50),
    full_name       VARCHAR(255),
    email           VARCHAR(255),
    added_at        DATETIME        DEFAULT CURRENT_TIMESTAMP
);

-- ── PR Reviews ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pr_reviews (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    pr_number       INT             NOT NULL,
    pr_title        VARCHAR(500),
    author          VARCHAR(100),
    review_summary  LONGTEXT,
    issues_found    JSON,           -- [{severity, line, message}]
    complexity_score FLOAT,
    reviewed_at     DATETIME        DEFAULT CURRENT_TIMESTAMP
);

-- ── Scrum Updates ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scrum_updates (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    member_id       INT,
    issue_number    INT,
    status_note     TEXT,
    message_sent    TEXT,
    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_id) REFERENCES team_members(id) ON DELETE SET NULL
);
