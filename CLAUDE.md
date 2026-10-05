# Project Guidelines

## Project Overview

This project is a Python Telegram bot for analyzing support conversations.

The bot allows a user to:

1. Authorize a Telegram account and create a Telegram session.
2. Retrieve conversations/messages from that authorized account.
3. Export all support conversations for a selected day.
4. Analyze conversations without using LLMs.
5. Determine the most common questions/topics using deterministic NLP algorithms.
6. Return the analysis results through Telegram.

The project is intended for internal company support analytics.

---

## Core Principles

Follow Clean Architecture principles.

The main rule is:

> Business logic must not depend on Telegram, databases, HTTP clients, NLP libraries, or other infrastructure details.

Dependencies must point inward:

```text
Infrastructure
      ↓
Application
      ↓
Domain
```

The Domain must remain independent of all external frameworks and libraries.

Do not introduce abstractions only for the sake of abstractions. Use interfaces/protocols when they protect the application/domain from infrastructure details or make testing substantially easier.

---

## Architecture

Recommended structure:

```text
src/
├── domain/
│   ├── entities/
│   ├── value_objects/
│   ├── enums/
│   └── repositories/
│
├── application/
│   ├── dto/
│   ├── use_cases/
│   └── services/
│
├── infrastructure/
│   ├── telegram/
│   │   ├── bot/
│   │   └── client/
│   ├── persistence/
│   ├── nlp/
│   └── config/
│
├── presentation/
│   └── telegram/
│       ├── handlers/
│       ├── keyboards/
│       └── formatters/
│
└── main.py

tests/
├── unit/
├── integration/
└── e2e/
```

### Domain

Contains business concepts and rules.

Examples:

```text
domain/entities/
    telegram_account.py
    support_message.py
    conversation.py
    question_cluster.py

domain/value_objects/
    telegram_session.py
    message_text.py
    chat_id.py

domain/enums/
    message_type.py

domain/repositories/
    telegram_account_repository.py
    conversation_repository.py
```

Domain code must NOT import:

* aiogram
* Telethon
* Pyrogram
* SQLAlchemy
* scikit-learn
* numpy
* pandas
* external APIs
* infrastructure modules

The domain should be testable with pure Python.

---

## Application Layer

Contains use cases and application-specific business workflows.

Examples:

```text
application/use_cases/
    authorize_telegram_account.py
    export_daily_conversations.py
    analyze_daily_questions.py
    get_daily_report.py
```

A use case orchestrates operations but should not know implementation details.

Example:

```python
class AnalyzeDailyQuestions:
    def __init__(
        self,
        message_repository: MessageRepository,
        question_analyzer: QuestionAnalyzer,
    ):
        ...
```

The use case should depend on abstractions, not concrete implementations.

Avoid putting Telegram-specific logic into use cases.

The application layer should not know whether the request came from:

* Telegram
* HTTP
* CLI
* tests

---

## Infrastructure

Contains implementations of external dependencies.

Examples:

```text
infrastructure/telegram/client/
    telethon_client.py

infrastructure/persistence/
    sqlalchemy/
        models/
        repositories/

infrastructure/nlp/
    tfidf_question_analyzer.py
    text_normalizer.py
```

Infrastructure may depend on external libraries.

For example:

```text
TelethonTelegramClient
    implements
TelegramClient
```

and:

```text
TfidfQuestionAnalyzer
    implements
QuestionAnalyzer
```

The rest of the application must not depend directly on Telethon or scikit-learn.

---

## Presentation

Telegram handlers belong to the presentation layer.

Handlers should be thin.

They should:

1. Receive Telegram updates.
2. Validate/extract input.
3. Call an application use case.
4. Format the result.
5. Send the response.

Do not put business logic inside handlers.

Bad:

```python
@router.callback_query(...)
async def analyze(callback):
    messages = await telethon.get_messages(...)
    ...
    # NLP logic
    ...
```

Good:

```python
@router.callback_query(...)
async def analyze(callback):
    report = await analyze_daily_questions.execute(...)
    await callback.message.answer(format_report(report))
```

---

# Telegram Architecture

There are two different Telegram concerns.

## Telegram Bot

Used for interaction with the user:

* authorization flow
* buttons
* commands
* reports
* status messages

This should be implemented using a bot framework such as `aiogram`.

## Telegram User Client

Used to access the authorized Telegram account and retrieve its conversations.

This should be isolated behind an application interface.

For example:

```python
class TelegramClient(Protocol):

    async def authenticate(...):
        ...

    async def get_messages(...):
        ...

    async def get_dialogs(...):
        ...
```

The concrete implementation can use Telethon.

Do not expose Telethon types outside infrastructure.

Convert external Telegram objects into domain/application DTOs.

---

# Authentication and Sessions

Telegram user sessions are sensitive credentials.

Never:

* commit session files;
* log session strings;
* log authentication codes;
* log passwords;
* send session data to Telegram users;
* store session data in plain application logs.

Session storage must be isolated behind an abstraction.

Example:

```text
TelegramSessionRepository
```

The application should work with a session identifier/reference rather than depending on Telethon's session implementation.

Use environment variables or a secret manager for encryption keys and sensitive configuration.

---

# Message Model

A support message should contain only information required by the application.

Example:

```python
@dataclass
class SupportMessage:
    id: int
    chat_id: int
    sender_id: int
    text: str
    sent_at: datetime
```

Do not pass raw Telethon message objects through the application.

Convert them at the infrastructure boundary.

---

# Daily Export

The daily export use case should:

1. Determine the requested date.
2. Retrieve the authorized Telegram account.
3. Retrieve relevant conversations/messages.
4. Convert them into application/domain objects.
5. Filter messages belonging to the requested day.
6. Return an export/report DTO.

Do not mix exporting and NLP analysis.

For example:

```text
ExportDailyConversations
        ↓
DailyConversationExport
        ↓
AnalyzeDailyQuestions
        ↓
DailyQuestionReport
```

This allows analysis to work independently of Telegram.

---

# NLP / Question Analysis

LLMs are NOT required for the initial implementation.

The first implementation should use deterministic NLP.

Recommended pipeline:

```text
Raw message
    ↓
Text normalization
    ↓
Question detection
    ↓
Tokenization / lemmatization
    ↓
Stop-word removal
    ↓
TF-IDF
    ↓
Cosine similarity
    ↓
Clustering
    ↓
Question frequency
```

Keep NLP behind an interface:

```python
class QuestionAnalyzer(Protocol):

    def analyze(
        self,
        messages: list[SupportMessage],
    ) -> QuestionAnalysisResult:
        ...
```

The application must not know whether the implementation uses:

* TF-IDF
* cosine similarity
* clustering
* another deterministic algorithm
* LLM in the future

---

# Question Detection

Not every support message is necessarily a question.

The first implementation may use deterministic heuristics:

* question mark;
* interrogative words;
* common support-question patterns;
* message length;
* configurable stop phrases.

Do not attempt to build a perfect linguistic classifier in the first version.

The goal is useful support analytics, not academic NLP.

---

# Question Normalization

Normalize messages before comparison.

Possible steps:

```text
"Подскажите, пожалуйста, как изменить способ оплаты?"
                    ↓
"изменить способ оплаты"
```

Normalization may include:

* lowercase;
* punctuation removal;
* whitespace normalization;
* removing greetings;
* removing polite filler phrases;
* removing stop words;
* lemmatization;
* removing very short tokens.

Keep normalization deterministic and testable.

---

# Question Clustering

Do not simply count exact strings.

These should ideally belong to the same cluster:

```text
Как изменить способ оплаты?

Подскажите, где поменять способ оплаты?

Можно поменять способ оплаты?

Как сменить способ оплаты?
```

Use similarity-based grouping.

The exact algorithm can evolve independently from the application layer.

The analyzer should return structured data such as:

```python
@dataclass
class QuestionCluster:
    representative_question: str
    count: int
    examples: list[str]
```

The application can then sort clusters by `count`.

---

# Reporting

The report should contain useful business information.

Example:

```text
Support report — 2026-10-05

Messages: 1,284
Questions: 763
Conversations: 218

Top questions:

1. Способ оплаты — 47
2. Не приходит SMS — 31
3. Отмена бронирования — 24
4. Изменение заказа — 19
5. Добавление сотрудника — 17
```

The report formatter belongs to the presentation layer.

Do not generate Telegram-formatted strings inside the domain.

---

# Dependency Injection

Prefer constructor injection.

Example:

```python
class AnalyzeDailyQuestions:
    def __init__(
        self,
        message_repository: MessageRepository,
        question_analyzer: QuestionAnalyzer,
    ):
        self.message_repository = message_repository
        self.question_analyzer = question_analyzer
```

Avoid:

```python
self.repository = MessageRepository()
```

inside business classes.

Avoid global mutable state.

---

# Async

Use async I/O for:

* Telegram API;
* database access;
* network requests.

CPU-heavy NLP processing may be synchronous.

Do not make every function async automatically.

Use async where there is actual asynchronous I/O.

---

# Database

Use a relational database.

Recommended initial choice:

```text
PostgreSQL
```

Possible entities:

```text
telegram_accounts
telegram_sessions
conversations
messages
daily_reports
```

Database models belong to infrastructure.

Domain entities must not inherit from SQLAlchemy models.

---

# Configuration

Configuration must come from environment variables or a dedicated configuration object.

Example:

```text
BOT_TOKEN
DATABASE_URL
TELEGRAM_API_ID
TELEGRAM_API_HASH
SESSION_ENCRYPTION_KEY
```

Never hardcode secrets.

Never commit `.env`.

Provide `.env.example`.

---

# Logging

Logs must be useful for debugging but must not contain sensitive Telegram data.

Never log:

* Telegram session strings;
* authentication codes;
* Telegram passwords;
* message contents by default;
* access tokens;
* encryption keys.

Prefer:

```text
Account authentication started
Account authenticated
Daily export started
Daily export completed: 1284 messages
Question analysis completed: 763 questions, 42 clusters
```

---

# Error Handling

Infrastructure exceptions should be translated into application-level errors where appropriate.

Do not leak raw Telethon/SQLAlchemy exceptions to Telegram users.

Users should receive understandable messages:

```text
Не удалось авторизовать Telegram-аккаунт.

Проверьте код подтверждения и попробуйте ещё раз.
```

Detailed technical information belongs in logs.

---

# Testing

Prioritize tests for business logic.

Especially test:

* text normalization;
* question detection;
* similarity;
* clustering;
* frequency calculation;
* date filtering;
* authorization workflows;
* report generation.

NLP tests should include realistic variations:

```text
Как изменить способ оплаты?
Подскажите где поменять оплату?
Можно ли сменить способ оплаты?
Где изменить карту для оплаты?
```

Tests must not require real Telegram API access.

Use mocks/fakes for infrastructure.

Integration tests may use a test database.

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
* framework-specific code leaking into domain.

Use `Protocol` when an abstraction is actually needed.

Use type hints consistently.

Prefer small functions and classes with one clear responsibility.

---

# Project Rules

When implementing a new feature:

1. Identify the business use case.
2. Define/update domain models if necessary.
3. Define application interfaces.
4. Implement the use case.
5. Implement infrastructure adapters.
6. Connect the use case to Telegram handlers.
7. Add tests.
8. Keep framework-specific code at the boundaries.

Before adding a dependency, ask whether the standard library or an existing project dependency is sufficient.

Do not introduce an LLM dependency unless deterministic NLP is demonstrably insufficient.

---

# Important Architectural Rule

The following dependency is forbidden:

```text
Domain → Telegram
Domain → Database
Doma
```
