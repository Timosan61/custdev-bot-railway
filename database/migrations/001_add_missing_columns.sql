-- Миграция для добавления недостающих колонок в базу данных Supabase
-- Выполните эти запросы в SQL Editor на https://supabase.com/dashboard/project/ouecjeglnqwfmdqxflhk/editor

-- 1. Добавление колонки researcher_telegram_id в таблицу interviews
ALTER TABLE interviews 
ADD COLUMN IF NOT EXISTS researcher_telegram_id BIGINT;

-- 2. Добавление колонок брифа в таблицу interviews
ALTER TABLE interviews
ADD COLUMN IF NOT EXISTS name TEXT,
ADD COLUMN IF NOT EXISTS industry TEXT,
ADD COLUMN IF NOT EXISTS target TEXT,
ADD COLUMN IF NOT EXISTS hypotheses TEXT,
ADD COLUMN IF NOT EXISTS style TEXT,
ADD COLUMN IF NOT EXISTS success_metric TEXT,
ADD COLUMN IF NOT EXISTS constraints TEXT,
ADD COLUMN IF NOT EXISTS existing_data TEXT,
ADD COLUMN IF NOT EXISTS instruction TEXT;

-- 3. Добавление индекса для быстрого поиска по researcher_telegram_id
CREATE INDEX IF NOT EXISTS idx_interviews_researcher_telegram_id 
ON interviews(researcher_telegram_id);

-- 4. Добавление полей в таблицу user_sessions
ALTER TABLE user_sessions
ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active',
ADD COLUMN IF NOT EXISTS summary TEXT,
ADD COLUMN IF NOT EXISTS answers JSONB DEFAULT '[]'::jsonb;

-- 5. Миграция существующих данных из fields в новые колонки
UPDATE interviews 
SET 
    researcher_telegram_id = COALESCE(researcher_telegram_id, (fields->>'researcher_telegram_id')::BIGINT),
    name = COALESCE(name, fields->>'name'),
    industry = COALESCE(industry, fields->>'industry'),
    target = COALESCE(target, fields->>'target'),
    hypotheses = COALESCE(hypotheses, fields->>'hypotheses'),
    style = COALESCE(style, fields->>'style'),
    success_metric = COALESCE(success_metric, fields->>'success_metric'),
    constraints = COALESCE(constraints, fields->>'constraints'),
    existing_data = COALESCE(existing_data, fields->>'existing_data'),
    instruction = COALESCE(instruction, fields->>'instruction')
WHERE fields IS NOT NULL;