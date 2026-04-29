# Windmill Workspace Inventory

Generated: 2025-01-01

## Overview

| Category | Count |
|----------|-------|
| Scripts | 12 |
| Flows | 1 |
| Apps | 1 |
| Resources | 6 |
| Schedules | 1 |
| Folders | 1 |

---

## Scripts (12)

### Shared Utilities (`f/shared/`)

| Path | Description |
|------|-------------|
| `f/shared/llm_utils` | LLM clients for OpenRouter/OpenAI with retry logic |
| `f/shared/fal_utils` | FAL.ai utilities |
| `f/shared/__init__` | Shared module initialization |

### Transcription (`f/transcriber/`)

| Path | Description | Resource |
|------|-------------|----------|
| `f/transcriber/transcribe` | Audio/video transcription via Deepgram API with diarization | `u/theatmacreator/deepgram` |

### Content Processing (`f/post_*/`, `f/title_*/`, `f/image_*/`)

| Path | Description | Resource |
|------|-------------|----------|
| `f/post_splitter/split_posts` | Splits text into separate posts (delimiter: `@@@@@`) | `u/theatmacreator/finer_c_openrouter` |
| `f/post_generator/generate_post` | Generates ready-to-publish post from theses | `u/theatmacreator/finer_c_openrouter` |
| `f/title_generator/generate_titles` | Generates titles for posts | `u/theatmacreator/finer_c_openrouter` |
| `f/image_prompts/generate_image_prompts` | Generates image ideas/prompts | `u/theatmacreator/finer_c_openrouter` |

### Baserow Integration (`f/baserow_*/`)

| Path | Description | Resource |
|------|-------------|----------|
| `f/baserow_post/create_post` | Creates post in Baserow | `u/theatmacreator/baserow_api` |
| `f/baserow_ideas/save_idea` | Saves idea to Baserow | `u/theatmacreator/baserow_api` |

### Image Generation (`f/fal_image_generator/`)

| Path | Description | Resource |
|------|-------------|----------|
| `f/fal_image_generator/generate_image` | Image generation via FAL.ai | `u/theatmacreator/fal` |

### Publishing (`f/publisher/`)

| Path | Description | Resource | Schedule |
|------|-------------|----------|----------|
| `f/publisher/publish_to_telegram` | Publishes posts from Baserow to Telegram | `u/theatmacreator/content_forge_bot` | `0 15 * * *` UTC |

### Bots (`f/content_forge/`)

| Path | Description | Resource |
|------|-------------|----------|
| `f/content_forge/content_forge_bot` | Content Forge bot | `u/theatmacreator/content_forge_bot` |

---

## Flows (1)

| Path | Description | Steps |
|------|-------------|-------|
| `f/flows/create_posts_from_transcript__flow` | End-to-end: transcription → posts → Baserow | 1. `transcribe` → 2. `split_posts` → 3. Loop: `generate_post` + `generate_titles` + `generate_image_prompts` + `create_post` |

---

## Apps (1)

| Path | Description |
|------|-------------|
| `f/apps/transcriber__app` | Transcription app (empty, needs setup) |

---

## Resources (6)

| Path | Type | Description |
|------|------|-------------|
| `u/theatmacreator/finer_c_openrouter` | `c_openrouter` | OpenRouter API key (X-Title: Windmill) |
| `u/theatmacreator/deepgram` | — | Deepgram API for transcription |
| `u/theatmacreator/baserow_api` | `c_baserow` | Baserow API token |
| `u/theatmacreator/fal` | `c_fal` | FAL.ai for image generation |
| `u/theatmacreator/content_forge_bot` | — | Telegram Bot API token |
| `u/theatmacreator/telegram_client_api` | — | Telegram Client API |

---

## Schedules (1)

| Script | Schedule | Timezone |
|--------|----------|----------|
| `f/publisher/publish_to_telegram` | Daily at 15:00 | UTC |

---

## Folders (1)

| Name | Owner | Extra Permissions |
|------|-------|-------------------|
| `test_folder` | `u/theatmacreator` | `u/theatmacreator: true` |

---

## Dependency Graph

```
                    ┌─────────────────────────────────────────┐
                    │   create_posts_from_transcript__flow   │
                    └─────────────────────────────────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         │                            │                            │
         ▼                            ▼                            ▼
┌─────────────────┐        ┌──────────────────┐        ┌─────────────────┐
│   transcribe    │        │  split_posts     │        │   (for loop)    │
│   (Deepgram)    │──text──▶│  (OpenRouter)    │──posts─▶│                 │
└─────────────────┘        └──────────────────┘        └────────┬────────┘
                                                                      │
                         ┌────────────────────────────────────────────┼────────────────────────────────────────────┐
                         │                                            │                                            │
                         ▼                                            ▼                                            ▼
              ┌──────────────────┐                    ┌──────────────────┐                    ┌──────────────────┐
              │ generate_post    │                    │ generate_titles  │                    │generate_image_   │
              │ (OpenRouter)     │                    │ (OpenRouter)     │                    │prompts (OpenR.)  │
              └──────────────────┘                    └──────────────────┘                    └────────┬─────────┘
                                                                                                                  │
                                                                                                                  ▼
                                                                                                    ┌──────────────────────┐
                                                                                                    │   create_post        │
                                                                                                    │   (Baserow API)      │
                                                                                                    └──────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────────────────────────┐
    │                         SCHEDULED TASK                                                  │
    │  publish_to_telegram (0 15 * * *) ────▶ Baserow ────▶ Telegram                         │
    └─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
f/
├── shared/
│   ├── __init__.py
│   ├── llm_utils.py
│   └── fal_utils.py
├── transcriber/
│   └── transcribe.py
├── post_splitter/
│   └── split_posts.py
├── post_generator/
│   └── generate_post.py
├── title_generator/
│   └── generate_titles.py
├── image_prompts/
│   └── generate_image_prompts.py
├── baserow_post/
│   └── create_post.py
├── baserow_ideas/
│   └── save_idea.py
├── fal_image_generator/
│   └── generate_image.py
├── publisher/
│   └── publish_to_telegram.py
├── content_forge/
│   └── content_forge_bot.py
├── flows/
│   └── create_posts_from_transcript__flow/
│       └── flow.yaml
└── apps/
    └── transcriber__app/

u/
└── theatmacreator/
    ├── finer_c_openrouter.resource.yaml
    ├── deepgram.resource.yaml
    ├── baserow_api.resource.yaml
    ├── fal.resource.yaml
    ├── content_forge_bot.resource.yaml
    └── telegram_client_api.resource.yaml
```
