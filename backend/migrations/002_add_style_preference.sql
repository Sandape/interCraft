-- Migration 002: Add style_preference to resume_branches
-- Feature: 002-resume-editor-enhancement

ALTER TABLE resume_branches
ADD COLUMN IF NOT EXISTS style_preference VARCHAR(64) NOT NULL DEFAULT 'compact-one-page';

COMMENT ON COLUMN resume_branches.style_preference IS 'Resume style template: compact-one-page or modern-two-column';
