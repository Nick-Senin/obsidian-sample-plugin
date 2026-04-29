# Windmill Workspace

Автоматизация контента и транскрибации на базе [Windmill](https://www.windmill.dev/).

## Архитектура

Слоистая структура: **shared** → **transformations** → **projects**

```
f/
├── shared/                     # Инфраструктурные утилиты
│   ├── llm_utils.py            # LLM-клиенты (OpenRouter), retry-логика
│   ├── fal_utils.py            # FAL.ai утилиты
│   ├── telegram_bot_helper.py  # Telegram webhook-бот хелпер
│   └── obsidian_local_rest_api/# Obsidian REST API (health check, setup)
│
├── transformations/            # Атомарные операции (~45 модулей)
│   ├── transcriber/            #   Транскрибация (Deepgram, Gigaam)
│   ├── post_splitter/          #   Разбиение текста на посты
│   ├── post_generator/         #   Генерация постов
│   ├── title_generator/        #   Генерация заголовков
│   ├── image_prompts/          #   Промпты для изображений
│   ├── fal_image_generator/    #   Генерация картинок (FAL.ai)
│   ├── baserow_post/           #   Записи в Baserow
│   ├── scrape_url/             #   Скрейпинг URL
│   ├── yt_transcript/          #   YouTube транскрипты
│   ├── style_transfer/         #   Стилевой перенос
│   ├── extract_entities/       #   Извлечение сущностей
│   ├── telegram_publisher/     #   Публикация в Telegram
│   └── ...                     #   И другие
│
├── prj_content_forge/          # Проект: Content Forge
│   ├── flows/                  #   Флоу создания и публикации контента
│   ├── publisher/              #   Публикация (Telegram, X)
│   ├── content_forge_bot/      #   Telegram-бот
│   ├── baserow/                #   Интеграция с Baserow
│   └── obs_websocket_listener/ #   OBS WebSocket listener
│
├── prj_process_to_protocol/    # Проект: Протоколирование встреч
│   └── flows/
│       └── analyze_transcript__flow/
│
└── prj_transcriber/            # Проект: Транскрибатор
    └── apps/
        └── transcriber__app/
```

## Проекты

### Content Forge (`prj_content_forge`)
End-to-end пайплайн создания контента: транскрибация → разбиение на посты → генерация текста/заголовков/изображений → публикация в Telegram/X.

Основной флоу: `create_posts_from_transcript` — транскрибация аудио, разбивка на посты, генерация контента, сохранение в Baserow.

Расписание: автоматическая публикация в Telegram ежедневно в 15:00 UTC.

### Process to Protocol (`prj_process_to_protocol`)
Анализ транскриптов встреч и генерация протоколов. Поддерживает несколько шаблонов встреч (консультации, маркетинг, разработка, кастдевы и др.).

### Transcriber (`prj_transcriber`)
UI-приложение для транскрибации аудио/видео через Deepgram.

## Ресурсы

| Ресурс | Тип | Описание |
|--------|-----|----------|
| OpenRouter | API Token | LLM-доступ (Gemini, Claude и др.) |
| Baserow | API Token | База данных контента |
| FAL.ai | API Token | Генерация изображений |
| X API | API Token | Публикация в X (Twitter) |
| Obsidian Local REST API | API Key | Интеграция с Obsidian |
| Deepgram | API Key | Транскрибация |
| Telegram Client | API Key | Telegram User API |
| Firecrawl | API Key | Скрейпинг |

## Инструкции

Полные инструкции для работы — в [`CLAUDE.md`](./CLAUDE.md).
