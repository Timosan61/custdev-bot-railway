-- Опциональная миграция для очистки неиспользуемых данных
-- ВНИМАНИЕ: Эта миграция удаляет дублированные данные из JSONB поля fields
-- Выполняйте только после успешного выполнения миграции 001

-- Удаление дублированных полей из JSONB поля fields
-- (оставляем только те поля, которые не имеют отдельных колонок)
UPDATE interviews
SET fields = fields 
    - 'researcher_telegram_id' 
    - 'name' 
    - 'industry' 
    - 'target' 
    - 'hypotheses' 
    - 'style' 
    - 'success_metric' 
    - 'constraints' 
    - 'existing_data' 
    - 'instruction'
WHERE fields IS NOT NULL;

-- Добавление комментариев к таблицам и колонкам для документации
COMMENT ON TABLE interviews IS 'Таблица с данными исследований (интервью)';
COMMENT ON COLUMN interviews.researcher_telegram_id IS 'Telegram ID исследователя, создавшего интервью';
COMMENT ON COLUMN interviews.name IS 'Имя или обращение к исследователю';
COMMENT ON COLUMN interviews.industry IS 'Сфера деятельности или ниша бизнеса';
COMMENT ON COLUMN interviews.target IS 'Целевая аудитория исследования';
COMMENT ON COLUMN interviews.hypotheses IS 'Гипотезы исследования';
COMMENT ON COLUMN interviews.style IS 'Стиль общения с респондентами';
COMMENT ON COLUMN interviews.success_metric IS 'Метрики успеха исследования';
COMMENT ON COLUMN interviews.constraints IS 'Ограничения исследования';
COMMENT ON COLUMN interviews.existing_data IS 'Существующие данные или исследования';
COMMENT ON COLUMN interviews.instruction IS 'Инструкция для респондентов';
COMMENT ON COLUMN interviews.fields IS 'Дополнительные поля в формате JSONB';

COMMENT ON TABLE user_sessions IS 'Сессии пользователей (исследователей и респондентов)';
COMMENT ON COLUMN user_sessions.status IS 'Статус сессии: active, completed';
COMMENT ON COLUMN user_sessions.summary IS 'Резюме интервью';
COMMENT ON COLUMN user_sessions.answers IS 'Массив ответов респондента в формате JSONB';