Of course. Here is the updated `README.md` file, focusing specifically on the database setup, migration command, and the JSON REST API documentation.

-----

# AI Chatbot API Setup & Documentation

This guide provides the essential steps to set up the application environment and documents the JSON REST API endpoints.

-----

## 🔧 Database Setup & Migration

### Step 1: Enable the Vector Extension in PostgreSQL

This application requires a **PostgreSQL** database with the **`pgvector`** extension enabled. This extension is crucial for storing and searching AI-generated text embeddings.

Connect to your PostgreSQL database instance and execute the following SQL command:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Step 2: Configure Environment and Run Services

1.  Create a `.env` file in the project root. Use the example below, ensuring the `DATABASE_URL` points to your database from Step 1.

    ```env
    # Flask and JWT Configuration
    SECRET_KEY='a_very_strong_random_secret_key'
    JWT_SECRET_KEY='another_very_strong_random_secret_key'

    # Secret key required to use the /register API endpoint
    REGISTRATION_SECRET_KEY='a_secret_phrase_for_registration'

    # --- IMPORTANT ---
    # Database Connection URL (ensure it points to your DB with pgvector)
    DATABASE_URL='postgresql://user:password@host:port/dbname'

    # Rate Limiter Storage URI (points to the memcached service in docker-compose)
    RATELIMIT_STORAGE_URI='memcached://memcached:11211'

    # Google AI API Key
    GOOGLE_API_KEY='your_google_ai_api_key'

    # Comma-separated list of allowed origins for CORS
    CORS_ORIGINS='http://localhost:3000,http://127.0.0.1:3000'
    ```

### Step 3: Run the Database Migration Command
```bash
flask db upgrade
```

### Step 4:  Build and start the application containers using Docker Compose

```bash
    docker-compose up --build -d
```


-----

## 📖 JSON REST API and Responses

The API base URL is `http://localhost:5000/api`. Protected endpoints require a `Bearer` token in the `Authorization` header.

### `/register`

  * **Method**: `POST`
  * **Auth**: None
  * **Request Body**:
    ```json
    {
      "username": "api_user",
      "password": "a_strong_password",
      "registration_secret": "the_secret_phrase_from_your_env",
      "is_admin": "True/False"
    }
    if is admin True accees to admin panel and create access_token
    
    else only create access_token

    ```
  * **Success Response (`201 Created`)**:
    ```json
    {
      "message": "User 'api_user' registered successfully."
    }
    ```

### `/login`

  * **Method**: `POST`
  * **Auth**: None
  * **Request Body**:
    ```json
    {
      "username": "api_user",
      "password": "a_strong_password"
    }
    ```
  * **Success Response (`200 OK`)**:
    ```json
    {
      "access_token": "ey..."
    }
    ```

### `/chat`

  * **Method**: `POST`
  * **Auth**: JWT Required
  * **Request Body**:
    ```json
    {
      "chatbot_user_id": "unique_session_id_for_user",
      "question": "What is Newton's first law of motion?",
      "syllabus": "CBSE",
      "class": "10",
      "subject": "Science"
    }
    ```
  * **Success Response (`200 OK`)**:
    ```json
    {
      "answer": "An object at rest stays at rest and an object in motion stays in motion with the same speed and in the same direction unless acted upon by an unbalanced force."
    }
    ```
  * **Error Response (`404 Not Found`)**:
    ```json
    {
      "error": "Document matching the specified criteria not found."
    }
    ```

### `/clear_session`

  * **Method**: `POST`
  * **Auth**: JWT Required
  * **Request Body**:
    ```json
    {
      "chatbot_user_id": "unique_session_id_to_clear"
    }
    ```
  * **Success Response (`200 OK`)**:
    ```json
    {
      "message": "Successfully cleared session.",
      "records_deleted": 15
    }
    ```
