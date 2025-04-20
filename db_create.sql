-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Proposal master table (Stores high-level proposal metadata)
CREATE TABLE IF NOT EXISTS proposal_master (
    proposal_id TEXT PRIMARY KEY,
    proposal_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Proposal inputs table (Stores input sections for AI processing)
CREATE TABLE IF NOT EXISTS proposal_inputs (
    proposal_id TEXT,
    section_name TEXT,
    content TEXT,
    reviewed INTEGER DEFAULT 0,
    PRIMARY KEY (proposal_id, section_name),
    FOREIGN KEY (proposal_id) REFERENCES proposal_master(proposal_id)
);

-- Proposal details table (Stores AI-generated proposal sections)
CREATE TABLE IF NOT EXISTS proposals_details (
    proposal_id TEXT,
    section_name TEXT,
    content TEXT,
    reviewed INTEGER DEFAULT 0,
    PRIMARY KEY (proposal_id, section_name)
);

-- Pricing data (Role-based standard pricing)
CREATE TABLE IF NOT EXISTS pricing (
    role TEXT PRIMARY KEY,
    rate INTEGER
);

-- Resource Pyramid table (Effort allocation per project type)
CREATE TABLE IF NOT EXISTS resource_pyramid (
    project_type TEXT,
    category TEXT,
    manager_percentage REAL,
    developer_percentage REAL,
    qa_percentage REAL,
    PRIMARY KEY (project_type, category)
);

-- Proposal feedback table (Stores human feedback for AI review)
CREATE TABLE IF NOT EXISTS proposal_feedback (
    proposal_id TEXT,
    section_name TEXT,
    feedback TEXT,
    PRIMARY KEY (proposal_id, section_name),
    FOREIGN KEY (proposal_id) REFERENCES proposal_master(proposal_id)
);

-- Proposal chat table (Stores chat messages between AI and users)
CREATE TABLE IF NOT EXISTS proposal_chat (
    proposal_id TEXT,
    role TEXT CHECK(role IN ('user', 'assistant')),
    message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- Insert sample data into proposal_master
INSERT INTO proposal_master (proposal_id, proposal_name) VALUES 
    ('123e4567-e89b-12d3-a456-426614174000', 'AI Banking Chatbot'),
    ('987f6543-e21d-65a4-b987-876543210999', 'Cloud Migration Strategy');

-- Insert sample data into proposal_inputs (Initial proposal sections)
INSERT INTO proposal_inputs (proposal_id, section_name, content) VALUES 
    ('123e4567-e89b-12d3-a456-426614174000', 'Introduction', 'This proposal aims to build an AI-powered chatbot for banking queries.'),
    ('987f6543-e21d-65a4-b987-876543210999', 'Solution Overview', 'The cloud migration strategy focuses on moving legacy banking infrastructure to AWS.');

-- Insert sample data into proposals_details (Finalized proposal sections)
INSERT INTO proposals_details (proposal_id, section_name, content, reviewed) VALUES 
    ('123e4567-e89b-12d3-a456-426614174000', 'Executive Summary', 'Our AI Banking Chatbot is designed to improve customer service efficiency.'),
    ('987f6543-e21d-65a4-b987-876543210999', 'Technical Architecture', 'The system leverages AWS Lambda, S3, and EC2 for high scalability.');

-- Insert sample data into pricing (Role-based pricing details)
INSERT INTO pricing (role, rate) VALUES 
    ('Project Manager', 1200),
    ('Developers', 1000),
    ('QA Engineers', 800),
    ('Solution Architect', 1500);

-- Insert sample data into resource_pyramid (Resource allocation percentages)
INSERT INTO resource_pyramid (project_type, category, manager_percentage, developer_percentage, qa_percentage) VALUES 
    ('Software Development', 'Web App', 0.10, 0.70, 0.20),
    ('Data Science', 'AI Model', 0.15, 0.60, 0.25),
    ('Cloud Migration', 'Enterprise System', 0.20, 0.50, 0.30);
