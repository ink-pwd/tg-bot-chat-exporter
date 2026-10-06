# Project Guidelines

## Project Overview

This project is a Python Telegram bot for analyzing support conversations of Dots
(a restaurant ordering/delivery platform; clients are restaurants, chats are mostly
in Ukrainian and Russian).

The bot works like this:

1. A user adds the bot to a support group chat. That user becomes the chat owner.
2. The bot records every message of the chat itself (the Bot API has no access to history,
   so nothing before the bot was added is available).
3. The owner exports all of their chats for a selected day (today and the 6 previous days)
   in a private chat with the bot, manually or by a daily auto-export.
4. Every export is a JSON file plus an HTML report, sent as one album.
5. The report is built with deterministic NLP, without LLMs.

The project is intended for internal company support analytics.

---

## Core Principles

Follow Clean Architecture principles.

The main rule is:

> Business logic must not depend on Telegram, databases, HTTP clients, NLP libraries, or other infrastructure details.

Dependencies must point inward:

```text
Presentation / Infrastructure
      ↓
Application
      ↓
Domain
```

The Domain must remain independent of all external frameworks and libraries.

Do not introduce abstractions only for the sake of abstractions. Use interfaces/protocols when they protect the application/domain from infrastructure details or make testing substantially easier.

---

## Architecture

```text
src/
├── domain/                business concepts only
│   ├── entities/          support_chat, support_message, conversation, daily export, export_schedule
│   ├── value_objects/     day_range
│   ├── enums/
│   └── business_rule_errors.py
│
├── application/
│   ├── ports/             ALL Protocols the use cases need from outside, one file per topic:
│   │                      repositories, delivery (files, notifier, progress), cache, telegram, analysis
│   ├── dto/               export summary, daily report, analysis results (requests, topics, types)
│   ├── services/          keyed locks, user timezones, personal data masking
│   ├── use_cases/         manage chats, record messages, export, analyze, auto-export
│   └── user_facing_errors.py
│
├── infrastructure/
│   ├── persistence/       SQLAlchemy models, database, mysql_* repositories
│   ├── cache/             Redis export cache
│   ├── telegram/bot/      Bot API actions inside a chat (admins, leave)
│   ├── nlp/               normalization, heuristics, intent model, topic clustering
│   │   └── resources/     dictionaries, taxonomy.toml, intent_model.npz
│   ├── security/          message encryption
│   ├── config/            settings, logging
│   └── periodic_scheduler.py
│
├── presentation/
│   └── telegram/
│       ├── handlers/      private menu, group events
│       ├── keyboards/
│       ├── formatters/    JSON export, HTML report
│       ├── adapters/      aiogram implementations of application ports (delivery, notifier, progress)
│       ├── input/         incoming data → our types (aiogram message, typed time)
│       ├── middlewares/
│       └── bot_texts.py, callback_data.py, dialog_states.py
│
└── main.py                composition root

scripts/                   offline tools (training the intent model), not part of the bot image
migrations/                Alembic
```

### Domain

Contains business concepts and rules. Domain code must NOT import:

* aiogram
* SQLAlchemy
* redis
* scikit-learn, numpy, scipy, pymorphy3
* cryptography
* external APIs
* infrastructure, application or presentation modules

The domain should be testable with pure Python.

### Application

Contains use cases and application-specific workflows. A use case orchestrates operations but does not know implementation details. It depends on abstractions (`Protocol`s in `application/ports`), not concrete implementations.

Every Protocol lives in `application/ports`, including repository interfaces. File names must be unique across the project and say what is inside — prefer several words over a short ambiguous name (`business_rule_errors.py`, `telegram_export_delivery.py`, `mysql_support_chats.py`, `group_chat_events.py`).

The application layer should not know whether the request came from Telegram, HTTP, CLI or tests. Use cases are invoked with plain values (`user_id`, `chat_id`, `date`), never with aiogram objects.

### Infrastructure

Contains implementations of external dependencies (MySQL, Redis, Bot API calls, NLP libraries, encryption). The rest of the application must not depend directly on SQLAlchemy, scikit-learn or aiogram.

### Presentation

Telegram handlers belong to the presentation layer. Handlers should be thin:

1. Receive Telegram updates.
2. Validate/extract input.
3. Call an application use case.
4. Format the result.
5. Send the response.

Do not put business logic inside handlers. Convert aiogram objects into domain objects at the boundary (`input/aiogram_message_conversion.py`); aiogram types must not go deeper.

The report formatter (HTML/JSON) and all user-facing texts belong to presentation. Do not generate Telegram-formatted strings inside the domain or application.

---

# Telegram Architecture

There is only the Telegram Bot (aiogram). There is no user-account client and no login of any kind.

## Private chat with the bot

Used by chat owners: main menu, "My chats", export (7-day picker), auto-export schedule, settings (timezone). Access can be limited with `ALLOWED_USER_IDS`.

## Group chats

* When the bot is added, the user who added it becomes the owner (`my_chat_member`). If that user is not allowed, the bot leaves the chat.
* The bot never writes into a group chat — clients must not notice it. Notifications go to the owner's private chat. Error handlers must not reply in groups.
* The bot needs privacy mode disabled in @BotFather or admin rights, otherwise it only receives commands.
* Supergroup migration keeps the history (internal chat id stays the same, Telegram chat id changes).
* If the bot is removed and re-added by another user, the previous owner's history is deleted.

## Ownership and isolation

Account isolation is the top priority:

* Every user-facing read goes through the owner (`*_owned` repository methods). There is intentionally no "get chat by id" without an owner.
* Callback data (chat ids, days) comes from the client and can be forged — always re-check ownership and limits in the use case.
* The export cache is keyed by user.

---

# Message Storage

Chat messages are sensitive data:

* Text, sender name and forward source are Fernet-encrypted in MySQL (`MESSAGE_ENCRYPTION_KEY`, several keys allowed for rotation).
* Messages are deleted after `MESSAGE_RETENTION_DAYS` (default 7, matching the export window).
* Exports are not stored on the server; Redis keeps only sent `file_id`s and counters.

Never:

* log message contents, encryption keys or tokens;
* commit `.env`, exported reports or labeled datasets with client conversations
  (root-level `*.html` / `*.json` are git-ignored for this reason).

---

# Message Model

A support message contains only information required by the application (`SupportMessage`: id, chat id, sender, text, timestamps, reply-to, forward source, media type, service action). Whether a message is from support is decided at export time: chat admins, the owner and anonymous admins are support; everyone else is a client.

---

# Daily Export

The export use case:

1. Checks the requested day (not in the future, within the 7-day window).
2. Serves a cached result if available.
3. Loads the owner's chats and their stored messages for the day.
4. Marks support messages (admins from the Bot API, saved list as fallback).
5. Builds `DailyConversationExport`, runs the analysis in a thread, delivers JSON + HTML.
6. An empty day is reported as "nothing recorded yet" — no empty files, no caching.

Progress is reported through `ExportProgress` stages (shown as a progress bar).

Do not mix exporting and NLP analysis:

```text
ExportDailyConversations
        ↓
DailyConversationExport
        ↓
AnalyzeDailyQuestions
        ↓
DailyQuestionReport
```

---

# NLP / Question Analysis

LLMs are NOT used. Everything is deterministic.

Pipeline:

```text
Messages of a chat
    ↓
Turns (client messages ≤ 2 min apart; any support message starts a new turn)
    ↓
Requests / clarifications / reminders
    ↓
Personal data masking
    ↓
Request type by the Dots taxonomy (trained TF-IDF + logistic regression)
    ↓
Unclassified requests → topic clustering ("Other topics")
    ↓
Report: categories, top request types, response time, per-chat stats
```

Definitions:

* **Request** — a new client request: a question, an ask, or a media-only message. Only the question sentences of a turn are analyzed.
* **Clarification** — a turn that continues the client's previous request: reply-to, follow-up markers ("а если…", "не получилось"), no own topic, or ≥50% topic overlap within 2 hours. "Ещё вопрос" always starts a new request.
* **Reminder** — "вы тут?", "есть новости?" from a closed phrase list. Better to miss a ping than to drop a real request.
* **Response time** — from a client question to the first substantive support reply (greetings and "секунду, уточню" are not answers; digit-only replies are). Working hours are Mon–Fri 09:00–20:00 in the report timezone.

## Request types

* `infrastructure/nlp/resources/taxonomy.toml` — 14 categories and 90 types from the CEO's yearly support report, with Russian titles and knowledge-base answers. Keys must match the model.
* `intent_model.npz` — vocabularies and weights only, loaded without pickle. Trained offline by `scripts/train_intent_model.py` from the labeled report; the report itself must stay outside the repo.
* Retrain the model after changing `concepts.toml`, `stopwords.txt` or `fillers.txt`.
* Thresholds live in `ModelIntentClassifier` (type ≥ 0.4, category ≥ 0.5).
* The report must clearly separate real support replies from knowledge-base answers.

Keep NLP behind interfaces (`MessageClassifier`, `TopicTokenizer`, `RequestClassifier`, `QuestionClusterer`). The application must not know whether an implementation uses TF-IDF, embeddings or an LLM.

Embeddings were measured (+5–10 pp of correctly typed requests at 1.5–5 GB RAM) and rejected for the 1 GB server. An LLM fallback for low-confidence requests was discussed but not adopted; any change here needs the user's decision.

---

# Reporting

The HTML report follows the style of the CEO's yearly support report, scoped to one day: KPIs (requests, median and p90 first reply, replies within 15 minutes in working hours, unanswered, off-hours share), categories, top request types with real dialogs, other topics, response time by hour, per-chat table, longest waits, definitions.

Phones, emails, passwords and tokens are masked before analysis, so neither quotes nor topic labels can leak them. The JSON export stays complete.

---

# Dependency Injection

Prefer constructor injection. All wiring happens in `main.py`.

Avoid creating dependencies inside business classes (`self.repository = MessageRepository()`).

Avoid global mutable state.

---

# Async

Use async I/O for the Telegram API, database access and Redis.

CPU-heavy NLP processing is synchronous and runs in a thread (`asyncio.to_thread`).

Do not make every function async automatically.

---

# Database and Deployment

* MySQL 8.4 (chosen by the user), Redis, everything in Docker Compose.
* Tables: `bot_users`, `support_chats`, `chat_messages`, `export_schedules`. Database models belong to infrastructure; domain entities must not inherit from SQLAlchemy models.
* One initial Alembic migration; the server is installed from scratch.
* Target server: 1 vCPU, 1 GB RAM (+2 GB swap). MySQL is tuned down (64 MB buffer pool, no performance_schema); each container has its own memory limit and restarts on its own. Keep new dependencies light — check memory before adding anything heavy.

---

# Configuration

Configuration comes from environment variables via `infrastructure/config/environment_settings.py`:

```text
BOT_TOKEN
DATABASE_URL
REDIS_URL
MESSAGE_ENCRYPTION_KEY
MESSAGE_RETENTION_DAYS
ALLOWED_USER_IDS
DEFAULT_TIMEZONE
EXPORT_CONCURRENCY
LOG_LEVEL, LOG_DIR, LOG_RETENTION_DAYS
```

Never hardcode secrets. Never commit `.env`. Keep `.env.example` up to date.

---

# Logging

Logs must be useful for debugging but must not contain sensitive data.

Never log:

* message contents;
* encryption keys;
* bot tokens.

Prefer ids and counters:

```text
Chat connected: chat=1 owner=747133187
Daily export started: user=… day=2026-10-06
Question analysis completed: requests=45 classified=36 intents=28 other_topics=9
```

---

# Error Handling

Infrastructure exceptions are translated into application-level errors (`application/user_facing_errors.py`, `domain/business_rule_errors.py`).

Do not leak raw aiogram/SQLAlchemy exceptions to users. Users get understandable messages from `bot_texts.error_text`, for example:

```text
Сообщения хранятся 7 дней, этот день уже недоступен.
```

Detailed technical information belongs in logs. Errors are only answered in private chats, never in groups.

---

# Testing

There is no test suite in the repository for now — it was removed on the user's request on 2026-10-06. Do not add one unless the user asks.

Verify changes before reporting them as done: lint (`pyflakes`), import check, and ad-hoc scenario scripts outside the repo (fake Bot API session, temporary MySQL/Redis containers). Never require real Telegram API access for checks.

---

# Code Style

Prefer simple, explicit Python.

Do not over-engineer.

Avoid:

* unnecessary factories;
* unnecessary abstract base classes;
* service classes containing one trivial method;
* repositories for every simple in-memory operation;
* excessive DTO nesting;
* framework-specific code leaking into domain;
* dataclass fields, functions or parameters that nothing reads.

Use `Protocol` when an abstraction is actually needed.

Use type hints consistently.

Prefer small functions and classes with one clear responsibility.

Comments and user-facing texts are in Russian; commit messages are in English.

---

# Project Rules

When implementing a new feature:

1. Identify the business use case.
2. Define/update domain models if necessary.
3. Define application ports (Protocols in `application/ports`).
4. Implement the use case.
5. Implement infrastructure adapters.
6. Connect the use case to Telegram handlers.
7. Verify the change (see Testing).
8. Keep framework-specific code at the boundaries.

Before adding a dependency, ask whether the standard library or an existing project dependency is sufficient, and how much memory it costs on the 1 GB server.

Do not introduce an LLM dependency unless deterministic NLP is demonstrably insufficient and the user agrees to sending client texts to a provider.

---

# Important Architectural Rule

The following dependencies are forbidden:

```text
Domain → Telegram
Domain → Database
Domain → NLP libraries
Domain → Infrastructure / Application / Presentation
Application → Infrastructure / Presentation
```
