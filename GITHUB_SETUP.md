# Инструкция по публикации на GitHub

## 1. Создайте новый репозиторий на GitHub

1. Перейдите на https://github.com/new
2. Название репозитория: `custdev-bot`
3. Описание: "Telegram бот для проведения кастдев-интервью с поддержкой голосовых сообщений"
4. Сделайте репозиторий приватным или публичным по вашему усмотрению
5. НЕ инициализируйте репозиторий с README, .gitignore или лицензией
6. Нажмите "Create repository"

## 2. Подключите локальный репозиторий к GitHub

После создания репозитория выполните эти команды:

```bash
# Замените YOUR_USERNAME на ваш GitHub username
git remote add origin https://github.com/YOUR_USERNAME/custdev-bot.git

# Переименуйте ветку в main (GitHub теперь использует main вместо master)
git branch -M main

# Отправьте код на GitHub
git push -u origin main
```

## 3. Настройка секретов (если репозиторий публичный)

Если вы сделали репозиторий публичным, убедитесь что:

1. Файл `.env` добавлен в `.gitignore` (уже сделано)
2. В README указано, что нужно создать свой `.env` файл
3. Не публикуйте реальные API ключи

## 4. Добавьте описание и топики

На странице репозитория:
1. Нажмите на шестеренку возле "About"
2. Добавьте описание
3. Добавьте топики: `telegram-bot`, `customer-development`, `voice-recognition`, `gpt-4`, `supabase`

## 5. Создайте Release (опционально)

```bash
git tag -a v1.0.0 -m "Первый релиз CustDev Bot"
git push origin v1.0.0
```

## Альтернативный способ через GitHub CLI

Если у вас установлен GitHub CLI:

```bash
# Авторизация
gh auth login

# Создание репозитория
gh repo create custdev-bot --private --source=. --remote=origin --push

# Или публичный
gh repo create custdev-bot --public --source=. --remote=origin --push
```

## Структура проекта для GitHub

```
custdev-bot/
├── src/                    # Исходный код бота
├── data/                   # Данные и SQL схемы
├── .gitignore             # Игнорируемые файлы
├── README.md              # Описание проекта
├── requirements.txt       # Python зависимости
├── CLAUDE.md             # Правила для Claude
├── LICENSE               # Лицензия (добавьте по желанию)
└── .github/              # GitHub специфичные файлы
    └── workflows/        # GitHub Actions (если нужна CI/CD)
```