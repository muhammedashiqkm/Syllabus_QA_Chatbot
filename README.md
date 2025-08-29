

# \#\# 🧠 Syllabus QA Chatbot

This project is a sophisticated Retrieval-Augmented Generation (RAG) chatbot application. It's designed to answer questions based on a knowledge base of PDF documents, which are categorized by syllabus, class, and subject.

The application features a secure, token-based REST API for user interactions and a full-featured admin panel for managing the knowledge base. Long-running tasks, like processing and embedding documents, are handled asynchronously by a Celery worker.

-----

### \#\# ✨ Features

  * **REST API**: Secure endpoints for user registration, login, and chat interactions.
  * **Admin Panel**: A user-friendly interface to manage syllabuses, classes, subjects, and the documents that form the knowledge base.
  * **RAG Pipeline**: Implements a full RAG workflow: PDF parsing, text chunking, vector embedding, and context-aware answer generation using Google's Generative AI models.
  * **Asynchronous Background Processing**: Uses Celery and Redis to process new documents without blocking the admin interface.
  * **Vector Search**: Leverages the `pgvector` extension for PostgreSQL to perform efficient semantic searches.
  * **Containerized**: Fully containerized with Docker and Docker Compose for easy setup and deployment.

-----

### \#\# 🚀 Getting Started

Follow these instructions to get the application running locally.

### \#\#\# Prerequisites

  * **Docker**
  * **Docker Compose**

### \#\#\# Installation

1.  **Clone the repository**:

    ```bash
    git clone <your-repository-url>
    cd <your-project-directory>
    ```

2.  **Create the environment file**:
    Copy the example environment file and fill in your specific credentials.

    ```bash
    cp .env.example .env
    ```

    Now, edit the `.env` file with your details (database URL, API keys, secret keys, etc.).

3.  **Enable pgvector in your Database**:
    Before starting the application, you must enable the `pgvector` extension in your PostgreSQL database. Connect to your database as a superuser and run the following SQL command:

    ```sql
    CREATE EXTENSION IF NOT EXISTS vector;
    ```

4.  **Build and run the application**:
    This command will build the Docker images and start all services (`web`, `worker`, `redis`, `memcached`) in the background.

    ```bash
    docker-compose up --build -d
    ```

5.  **Run database migrations**:
    Apply the database schema to your database.

    ```bash
    docker-compose exec web flask db upgrade
    ```

6.  **Create an Admin User**:
    Use the built-in CLI command to create your first admin user for the admin panel.

    ```bash
    docker-compose exec web flask create-admin <your_admin_username> '<your_strong_password>'
    ```

-----

### \#\# 🔐 Admin Panel

The admin panel is the control center for managing the chatbot's knowledge base.

  * **Access**: Navigate to `http://localhost:5000/admin` in your browser.
  * **Authentication**: Log in using the admin credentials you created in the setup step.
  * **Usage**: From the panel, you can:
      * Create and manage **Syllabuses**, **Classes**, and **Subjects**.
      * Add new **Documents** by providing a source PDF URL and linking it to the created categories. Adding or updating a document automatically triggers the background embedding process.

-----

### \#\# 🔑 API Authentication (Access Token)

The API is secured using JSON Web Tokens (JWT). To access protected endpoints, you must first obtain an access token.

1.  **Log In**: Send a `POST` request to the `/api/login` endpoint with a registered user's credentials.
2.  **Receive Token**: The response will contain an `access_token`.
3.  **Authorize Requests**: For all subsequent requests to protected endpoints, include the token in the `Authorization` header.
    ```
    Authorization: Bearer <your_access_token>
    ```

-----

### \#\# 📡 API Endpoints

All endpoints are prefixed with `/api`.

### \#\#\# Authentication

#### **`POST /register`**

Registers a new user for the API.

  * **Request Body**:
    ```json
    {
        "username": "newuser",
        "password": "strongpassword123",
        "registration_secret": "your_secret_from_.env"
    }
    ```
  * **Success Response** (`201 Created`):
    ```json
    {
        "message": "User 'newuser' registered successfully."
    }
    ```
  * **Error Response** (`409 Conflict`):
    ```json
    {
        "error": "Username already exists."
    }
    ```

#### **`POST /login`**

Logs in a user and returns a JWT access token.

  * **Request Body**:
    ```json
    {
        "username": "newuser",
        "password": "strongpassword123"
    }
    ```
  * **Success Response** (`200 OK`):
    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
    ```
  * **Error Response** (`401 Unauthorized`):
    ```json
    {
        "error": "Invalid username or password"
    }
    ```

### \#\#\# Chat Interaction

#### **`GET /categories`**

Retrieves a list of all available syllabuses, classes, and subjects. (Requires Authentication)

  * **Request Body**: None
  * **Success Response** (`200 OK`):
    ```json
    {
        "syllabuses": ["CBSE", "ICSE"],
        "classes": ["Class 10", "Class 12"],
        "subjects": ["Mathematics", "Physics"]
    }
    ```

#### **`POST /chat`**

Submits a question to the chatbot for a specific document category. (Requires Authentication)

  * **Request Body**:
    ```json
    {
        "chatbot_user_id": "session_abc_123",
        "question": "What is Newton's second law?",
        "syllabus": "CBSE",
        "class": "Class 12",
        "subject": "Physics"
    }
    ```
  * **Success Response** (`200 OK`):
    ```json
    {
        "answer": "Newton's second law of motion states that the acceleration of an object is directly proportional to the net force acting on it and inversely proportional to its mass."
    }
    ```
  * **Error Response** (`404 Not Found`):
    ```json
    {
        "error": "Document matching the specified criteria not found."
    }
    ```

#### **`POST /clear_session`**

Clears the chat history for a specific session ID. (Requires Authentication)

  * **Request Body**:
    ```json
    {
        "chatbot_user_id": "session_abc_123"
    }
    ```
  * **Success Response** (`200 OK`):
    ```json
    {
        "message": "Successfully cleared session.",
        "records_deleted": 15
    }
    ```
