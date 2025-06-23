-- Добавление колонки instruction в таблицу interviews
ALTER TABLE interviews 
ADD COLUMN IF NOT EXISTS instruction TEXT;

-- Обновление RLS политик для interviews
DROP POLICY IF EXISTS "Users can view own interviews" ON interviews;
DROP POLICY IF EXISTS "Users can update own interviews" ON interviews;

CREATE POLICY "Users can view own interviews" ON interviews
    FOR SELECT USING (true);

CREATE POLICY "Users can update own interviews" ON interviews
    FOR UPDATE USING (true);

-- Убедимся, что RLS включен
ALTER TABLE interviews ENABLE ROW LEVEL SECURITY;