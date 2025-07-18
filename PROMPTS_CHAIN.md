# Цепочка промптов CustDev Bot

## Обзор архитектуры промптов

Бот использует серию промптов для управления диалогом между исследователями и респондентами. Все промпты находятся в директории `src/prompts/`.

## 1. Промпты для исследователя (ResearcherAgent)

### 1.1 field_analyzer.txt
**Назначение**: Анализ качества ответов исследователя на вопросы о параметрах исследования

**Входные данные**:
- `field_name` - название поля (name, industry, target и т.д.)
- `field_description` - описание поля
- `question` - заданный вопрос
- `answer` - ответ пользователя

**Выходные данные** (JSON):
```json
{
  "is_complete": true/false,
  "confidence": 0.0-1.0,
  "missing_aspects": ["аспект1", "аспект2"],
  "extracted_value": "извлеченное значение или null"
}
```

**Особенности**:
- Строгая проверка для обязательных полей
- Отклонение ответов типа "не знаю", "незнаю"
- Проверка минимальной длины для критичных полей

### 1.2 clarification_generator.txt
**Назначение**: Генерация уточняющих вопросов когда ответ неполный

**Входные данные**:
- `field_name` - название поля
- `original_question` - изначальный вопрос
- `answer` - неполный ответ
- `missing_aspects` - недостающие аспекты
- `conversation_history` - история диалога

**Выходные данные**: Текст уточняющего вопроса

### 1.3 interview_brief_generator.txt
**Назначение**: Создание структурированного брифа исследования

**Входные данные**:
- `answers` - JSON со всеми собранными ответами

**Выходные данные**: Markdown документ с брифом, включающий:
1. Краткую сводку об исследовании
2. Детали исследования
3. Первое сообщение респонденту (используется как instruction)
4. Рекомендации по проведению

### 1.4 instruction_generator.txt
**Назначение**: Генерация инструкции для респондентов (fallback если бриф не сгенерировался)

**Входные данные**:
- `fields` - собранные поля исследования

**Выходные данные**: Текст приветственного сообщения для респондентов

## 2. Промпты для респондента (RespondentAgent)

### 2.1 first_question_generator.txt
**Назначение**: Генерация первого вопроса интервью

**Входные данные**:
- `instruction` - инструкция из брифа
- `tone` - тон общения (из поля style)
- `industry` - индустрия/ниша
- `target` - целевая аудитория

**Выходные данные**: Текст первого вопроса

### 2.2 next_question_generator.txt
**Назначение**: Генерация следующего вопроса на основе предыдущих ответов

**Входные данные**:
- `instruction` - инструкция из брифа
- `conversation_history` - история диалога
- `current_context` - текущий контекст
- `tone` - тон общения

**Выходные данные**: Текст следующего вопроса

**Особенности**:
- Учитывает контекст всего диалога
- Адаптирует вопросы под ответы респондента
- Следит за глубиной проработки темы

### 2.3 answer_extractor.txt
**Назначение**: Извлечение структурированных данных из ответов

**Входные данные**:
- `conversation` - полная история диалога

**Выходные данные** (JSON):
```json
{
  "key_insights": ["инсайт1", "инсайт2"],
  "pain_points": ["боль1", "боль2"],
  "needs": ["потребность1", "потребность2"],
  "objections": ["возражение1", "возражение2"],
  "quotes": ["цитата1", "цитата2"]
}
```

### 2.4 interview_summary_generator.txt
**Назначение**: Создание финального резюме интервью

**Входные данные**:
- `conversation` - полная история диалога
- `extracted_data` - извлеченные структурированные данные
- `instruction` - изначальная инструкция

**Выходные данные**: Структурированное резюме интервью в Markdown

## 3. Логика работы с промптами

### Для исследователя:
1. Каждый ответ проверяется через `field_analyzer.txt`
2. Если ответ неполный - генерируется уточнение через `clarification_generator.txt`
3. После сбора всех полей создается бриф через `interview_brief_generator.txt`
4. Из брифа извлекается instruction для респондентов

### Для респондента:
1. Первый вопрос генерируется через `first_question_generator.txt`
2. Последующие вопросы - через `next_question_generator.txt`
3. После каждых 3-5 вопросов данные извлекаются через `answer_extractor.txt`
4. В конце создается резюме через `interview_summary_generator.txt`

## 4. Ключевые особенности

### Адаптивность:
- Промпты учитывают контекст и историю диалога
- Вопросы адаптируются под стиль общения (tone)
- Глубина вопросов зависит от качества ответов

### Валидация:
- Строгая проверка обязательных полей
- Отклонение неинформативных ответов
- Запрос уточнений при необходимости

### Структурированность:
- Четкий формат входных/выходных данных
- JSON для данных, Markdown для документов
- Единообразная структура промптов

## 5. Расширение и модификация

При добавлении новых промптов следуйте структуре:
1. Четкое описание контекста (=== CONTEXT ===)
2. Ясная постановка задачи (=== TASK ===)
3. Явные правила и ограничения (=== RULES ===)
4. Примеры если необходимо (=== EXAMPLES ===)
5. Формат вывода (=== OUTPUT FORMAT ===)

Все промпты должны быть самодостаточными и не требовать внешнего контекста кроме переданных переменных.