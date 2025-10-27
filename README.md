# Syllabus QA Chatbot

This is a comprehensive, production-ready RAG (Retrieval-Augmented Generation) chatbot application built with Flask, Celery, and `pgvector`.

Its core purpose is to allow administrators to upload PDF documents (categorized by Syllabus, Class, and Subject) and API users to "chat" with those specific documents using multiple AI models (Gemini, OpenAI, and DeepSeek).

## Features

  * **Async API:** Built with Flask and served by Uvicorn for asynchronous requests.
  * **Admin Panel:** A secure Flask-Admin interface (`/admin`) for managing documents and categories.
  * **Async PDF Processing:** When a new `Document` is added, a Celery worker downloads, chunks, and creates vector embeddings in the background.
  * **Vector Search:** Uses `pgvector` for efficient, RAG-based context retrieval.
  * **Multi-Model Support:** The `/chat` endpoint can route requests to **Gemini**, **OpenAI**, or **DeepSeek** based on user input.
  * **Secure:** Uses JWT for API authentication and session-based auth for the admin panel.

-----

## Database & Application Setup

### 1\. Run Docker Services

First, build and run all the services (web, worker, redis, memcached) in detached mode:

```sh
docker-compose up --build -d
```

### 2\. Initialize the Database (One-Time Setup)

You must run this command **once** to prepare the PostgreSQL database. This script enables the `vector` extension and creates all your tables.

```sh
docker-compose exec web python create_db.py
```

You should see output like "PostgreSQL 'vector' extension is enabled." and "Database tables created successfully."

### 3\. Create Users


**To Create an Admin User (for the `/admin` panel):**

```sh
docker-compose exec web flask create-admin <your-admin-username> <your-admin-password>
```

-----

## Admin Panel

Access the admin panel by navigating to `/admin` in your browser. Log in with the admin credentials you just created.

Here you can:

  * Create `Syllabus`, `ClassModel`, and `Subject` entries.
  * Create `Document` entries, linking them to a `source_url` (PDF) and the categories. This will automatically trigger the background embedding task.

-----

## API Endpoints

All API endpoints are prefixed with `/api`. All protected endpoints require a Bearer Token in the `Authorization` header.

### `POST /api/login`

Logs in an API user and returns a JSON Web Token (JWT).

**Request Body:**

```json
{
    "username": "your-api-username",
    "password": "your-api-password"
}
```

**Success Response (200):**

```json
{
    "access_token": "your.jwt.token.here"
}
```

**Error Response (401):**

```json
{
    "error": "Invalid username or password"
}
```

-----

### `GET /api/categories`

(Protected) Fetches a list of all available categories for filtering.

**Request Body:**
*None*

**Success Response (200):**

```json
{
    "syllabuses": [
        "Syllabus A",
        "Syllabus B"
    ],
    "classes": [
        "Class 10",
        "Class 12"
    ],
    "subjects": [
        "Physics",
        "Chemistry"
    ]
}
```

-----

### `POST /api/chat`

(Protected) This is the main asynchronous chat endpoint. It finds the relevant document, performs a vector search for context, and sends the prompt to the specified AI model.

**Request Body:**

  * **model**: Must be one of `gemini`, `openai`, or `deepseek`.
  * **class**: Mapped from the JSON key `class`.

<!-- end list -->

```json
{
    "chatbot_user_id": "some-unique-user-session-id",
    "question": "What is the second law of thermodynamics?",
    "syllabus": "Syllabus A",
    "class": "Class 12",
    "subject": "Physics",
    "model": "gemini"
}
```

**Success Response (200):**

```json
{
    "answer": "The second law of thermodynamics states that the total entropy of an isolated system can only increase over time or remain constant..."
}
```

**Error Response (400 - Validation Error):**

```json
{
    "error": "Validation failed: {'model': ['Must be one of: gemini, openai, deepseek.']}"
}
```

**Error Response (404 - Not Found):**

```json
{
    "error": "Document matching the specified criteria not found."
}
```

**Error Response (503 - Service Failure):**

```json
{
    "error": "The AI service failed: OpenAI API key is not configured."
}
```

-----

### `POST /api/clear_session`

(Protected) Asynchronously clears all chat history for a given session ID.

**Request Body:**

```json
{
    "chatbot_user_id": "some-unique-user-session-id"
}
```

**Success Response (200):**

```json
{
    "message": "Successfully cleared session.",
    "records_deleted": 15
}
```

-----

### `GET /api/health`

A simple health check endpoint to confirm the web service is running.

**Request Body:**
*None*

**Success Response (200):**

```json
{
    "status": "healthy"
}
```