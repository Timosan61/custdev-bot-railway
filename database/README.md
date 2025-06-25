# Database Structure

## Tables

### interviews
Stores research interview data
- `id` (UUID) - Primary key
- `status` (TEXT) - Interview status: draft, in_progress, completed
- `fields` (JSONB) - Research brief fields
- `researcher_telegram_id` (BIGINT) - Telegram ID of researcher
- `created_at` (TIMESTAMP) - Creation timestamp
- `updated_at` (TIMESTAMP) - Last update timestamp

Note: Additional fields (name, industry, target, etc.) are planned to be added at the top level after migration.

### user_sessions  
Stores user session data for both researchers and respondents
- `id` (UUID) - Primary key
- `user_id` (BIGINT) - Telegram user ID
- `session_type` (TEXT) - Type: researcher or respondent
- `interview_id` (UUID) - Related interview ID
- `state` (JSONB) - Session state data
- `status` (TEXT) - Session status: active, completed
- `summary` (TEXT) - Interview summary (for respondents)
- `answers` (JSONB) - Array of respondent answers
- `created_at` (TIMESTAMP) - Creation timestamp
- `updated_at` (TIMESTAMP) - Last update timestamp

### respondent_answers
Stores individual respondent answers (currently not used)
- `id` (UUID) - Primary key
- `interview_id` (UUID) - Related interview ID
- `user_id` (BIGINT) - Respondent Telegram ID
- `question_text` (TEXT) - Question text
- `answer_text` (TEXT) - Answer text
- `created_at` (TIMESTAMP) - Creation timestamp

## Migrations

Run migrations in order from the `migrations/` folder:

1. `001_add_missing_columns.sql` - Adds missing columns to existing tables
2. `002_cleanup_unused.sql` - Optional cleanup of duplicate data in JSONB fields

Execute these in your Supabase SQL Editor.