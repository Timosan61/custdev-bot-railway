# Режимы работы бота: Direct и n8n

Бот поддерживает два режима работы с LLM:
- **Direct** - прямые вызовы OpenAI API (по умолчанию)
- **n8n** - вызовы через n8n workflows

## Настройка режимов

### 1. Direct режим (по умолчанию)

Установите в `.env`:
```env
AGENT_MODE=direct
```

Это режим работает как раньше - все вызовы LLM происходят напрямую из кода бота.

### 2. n8n режим

Установите в `.env`:
```env
AGENT_MODE=n8n

# Настройки n8n
N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook
N8N_API_KEY=your_n8n_api_key

# Настройки API сервера
API_ENABLED=true
API_HOST=0.0.0.0
API_PORT=8000
API_SECRET_KEY=your_secure_api_key_here
```

#### Запуск в n8n режиме:

1. **Запустите API сервер** (в отдельном терминале):
   ```bash
   python start_api.py
   ```

2. **Запустите бота** (в другом терминале):
   ```bash
   python -m src.main
   ```

## API Endpoints для n8n

API сервер предоставляет следующие endpoints:

### Для ResearcherAgent:
- `POST /api/v1/analyze-answer` - анализ качества ответа
- `POST /api/v1/generate-clarification` - генерация уточняющего вопроса
- `POST /api/v1/generate-brief` - создание интервью-брифа
- `POST /api/v1/generate-instruction` - генерация инструкции

### Для RespondentAgent:
- `POST /api/v1/generate-first-question` - первый вопрос респонденту
- `POST /api/v1/generate-next-question` - следующий вопрос
- `POST /api/v1/generate-summary` - резюме интервью

## Настройка n8n workflows

### 1. Создайте webhook в n8n:
- Добавьте Webhook node
- Установите метод POST
- Скопируйте URL webhook

### 2. Обработка запросов:
- Получите данные из webhook
- Используйте OpenAI node для обработки
- Верните результат через Respond to Webhook node

### Пример workflow для analyze-answer:

```json
{
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "path": "analyze-answer",
        "httpMethod": "POST"
      }
    },
    {
      "name": "OpenAI",
      "type": "@n8n/n8n-nodes-langchain.openai",
      "parameters": {
        "model": "gpt-4o",
        "prompt": "{{ $json.prompt }}"
      }
    },
    {
      "name": "Respond",
      "type": "n8n-nodes-base.respondToWebhook",
      "parameters": {
        "responseBody": {
          "result": "{{ $json.result }}"
        }
      }
    }
  ]
}
```

## Переключение между режимами

Просто измените `AGENT_MODE` в `.env` и перезапустите бота:
- `AGENT_MODE=direct` - прямые вызовы
- `AGENT_MODE=n8n` - через n8n

## Преимущества каждого режима

### Direct:
- Простота настройки
- Минимальная задержка
- Не требует дополнительных сервисов

### n8n:
- Визуальная настройка логики
- Легкое изменение промптов без перезапуска
- Мониторинг и логирование запросов
- A/B тестирование
- Возможность добавления дополнительной логики

## Безопасность

При использовании n8n режима:
1. Используйте HTTPS для webhook
2. Установите надежный API_SECRET_KEY
3. Ограничьте доступ к API по IP если возможно
4. Регулярно меняйте ключи доступа