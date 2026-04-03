-- ATLAS Control System - PostgreSQL Schema
-- V3.2: Migration from render_tracking.json
--
-- Creates tables for shots, scenes, and stats with proper indexing
-- for high-volume (9000+ shot) episode production

-- Create database if not exists (run manually first time):
-- CREATE DATABASE atlas_control;

-- Shots table - core render tracking
CREATE TABLE IF NOT EXISTS shots (
    shot_id VARCHAR(100) PRIMARY KEY,
    scene_id VARCHAR(100),
    project VARCHAR(200),
    episode VARCHAR(200),
    status VARCHAR(50) DEFAULT 'new',
    video_path TEXT,
    image_path TEXT,
    nano_prompt TEXT,
    ltx_motion_prompt TEXT,
    shot_size VARCHAR(20),  -- WS, MS, MCU, CU, ECU
    duration INTEGER,       -- seconds
    duration_bucket VARCHAR(20),
    coverage_type VARCHAR(50),
    characters TEXT[],      -- Array of character names
    location VARCHAR(200),
    lighting VARCHAR(200),
    camera VARCHAR(200),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Scenes table - tracks scene completion and stitching
CREATE TABLE IF NOT EXISTS scenes (
    scene_id VARCHAR(100) PRIMARY KEY,
    project VARCHAR(200),
    episode VARCHAR(200),
    scene_title VARCHAR(500),
    status VARCHAR(50) DEFAULT 'in_progress',
    stitched_path TEXT,
    shot_count INTEGER DEFAULT 0,
    total_duration INTEGER DEFAULT 0,  -- seconds
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stats table - aggregated statistics
CREATE TABLE IF NOT EXISTS render_stats (
    id SERIAL PRIMARY KEY,
    stat_key VARCHAR(100) UNIQUE NOT NULL,
    stat_value INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Projects table - track all projects
CREATE TABLE IF NOT EXISTS projects (
    project_name VARCHAR(200) PRIMARY KEY,
    genre VARCHAR(100),
    director_profile VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Image metadata table - separate from shots for performance
CREATE TABLE IF NOT EXISTS image_metadata (
    shot_id VARCHAR(100) PRIMARY KEY REFERENCES shots(shot_id) ON DELETE CASCADE,
    review_prompt TEXT,
    video_prompt_override TEXT,
    director_notes TEXT,
    dinov2_guideline TEXT,
    dinov2_notes TEXT,
    dialogue_entries JSONB,
    dialogue_text TEXT,
    continuity_prompt TEXT,
    lock_final BOOLEAN DEFAULT FALSE,
    image_generations INTEGER DEFAULT 0,
    video_generations INTEGER DEFAULT 0,
    image_cost_total_usd DECIMAL(10,4) DEFAULT 0,
    video_cost_total_usd DECIMAL(10,4) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_shots_scene_id ON shots(scene_id);
CREATE INDEX IF NOT EXISTS idx_shots_project ON shots(project);
CREATE INDEX IF NOT EXISTS idx_shots_status ON shots(status);
CREATE INDEX IF NOT EXISTS idx_shots_created_at ON shots(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_shots_shot_size ON shots(shot_size);

CREATE INDEX IF NOT EXISTS idx_scenes_project ON scenes(project);
CREATE INDEX IF NOT EXISTS idx_scenes_status ON scenes(status);

-- Full-text search on prompts
CREATE INDEX IF NOT EXISTS idx_shots_nano_prompt_gin ON shots USING gin(to_tsvector('english', nano_prompt));

-- Initialize default stats
INSERT INTO render_stats (stat_key, stat_value) VALUES
    ('total_generated', 0),
    ('working', 0),
    ('needs_regen', 0),
    ('ready_for_video', 0),
    ('image_pending', 0),
    ('scenes_stitched', 0)
ON CONFLICT (stat_key) DO NOTHING;

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_shots_updated_at ON shots;
CREATE TRIGGER update_shots_updated_at
    BEFORE UPDATE ON shots
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_scenes_updated_at ON scenes;
CREATE TRIGGER update_scenes_updated_at
    BEFORE UPDATE ON scenes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_image_metadata_updated_at ON image_metadata;
CREATE TRIGGER update_image_metadata_updated_at
    BEFORE UPDATE ON image_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
