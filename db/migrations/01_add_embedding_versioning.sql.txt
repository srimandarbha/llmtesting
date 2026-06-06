-- Database migration to add embedding model versioning

-- 1. Add model_name and model_version to operational_knowledge_embeddings
ALTER TABLE operational_knowledge_embeddings 
ADD COLUMN model_name VARCHAR(255) DEFAULT 'all-MiniLM-L6-v2',
ADD COLUMN model_version VARCHAR(50) DEFAULT '1.0';

-- 2. Add model_name and model_version to rhokp_knowledge
ALTER TABLE rhokp_knowledge 
ADD COLUMN model_name VARCHAR(255) DEFAULT 'all-MiniLM-L6-v2',
ADD COLUMN model_version VARCHAR(50) DEFAULT '1.0';

-- 3. Update indices if necessary (optional for exact match filtering, but good for performance)
CREATE INDEX IF NOT EXISTS idx_operational_embeddings_model 
ON operational_knowledge_embeddings(model_name, model_version);

CREATE INDEX IF NOT EXISTS idx_rhokp_knowledge_model 
ON rhokp_knowledge(model_name, model_version);
