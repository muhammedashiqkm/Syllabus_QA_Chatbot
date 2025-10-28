import os
import requests
import io
import pypdf
import google.generativeai as genai
import logging
import asyncio
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tenacity import retry, stop_after_attempt, wait_exponential
from app.exceptions import ExternalApiError
from flask import current_app
from openai import OpenAI, AsyncOpenAI

error_logger = logging.getLogger('error')

def configure_genai():
    """Configures the Google AI API key from the app config."""
    api_key = current_app.config.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Google API Key not configured in the application.")
    genai.configure(api_key=api_key)

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3), 
    retry_error_callback=lambda _: None
)
def get_pdf_text(pdf_url: str) -> str | None:
    """Downloads a PDF from a URL and extracts its text content."""
    try:
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status() 
        pdf_file = io.BytesIO(response.content)
        pdf_reader = pypdf.PdfReader(pdf_file)
        text = "".join(page.extract_text() or "" for page in pdf_reader.pages)
        return text.replace('\x00', '')
    except requests.exceptions.RequestException as e:
        error_logger.error(f"Error downloading PDF from {pdf_url}: {e}")
        return None
    except Exception as e:
        error_logger.error(f"Error processing PDF from {pdf_url}: {e}")
        return None


def get_text_chunks(text: str) -> list[str]:
    """Splits a long text into smaller, manageable chunks."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=current_app.config['TEXT_CHUNK_SIZE'],
        chunk_overlap=current_app.config['TEXT_CHUNK_OVERLAP'],
        length_function=len
    )
    chunks = text_splitter.split_text(text)
    return chunks


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generates vector embeddings for a batch of texts using Google AI. (Sync for Celery)"""
    try:
        model_name = current_app.config.get("EMBEDDING_MODEL_NAME")
        result = genai.embed_content(
            model=model_name,
            content=texts,
            task_type="retrieval_document"
        )
        return result['embedding']
    except Exception as e:
        error_logger.error(f"Error getting batch embedding from GenAI: {e}", exc_info=True)
        raise ExternalApiError("The embedding service failed.") from e

async def get_single_embedding_async(text: str) -> list[float]:
    """Generates a vector embedding for a single text query asynchronously."""
    try:
        model_name = current_app.config.get("EMBEDDING_MODEL_NAME")
        result = await genai.embed_content_async(
            model=model_name,
            content=text,
            task_type="retrieval_query"
        )
        return result['embedding']
    except Exception as e:
        error_logger.error(f"Error getting single embedding from GenAI (async): {e}", exc_info=True)
        raise ExternalApiError("The embedding service failed.") from e


def get_system_prompt() -> str:
    """Returns the system prompt (rules) for the AI."""
    return """
    You are a helpful AI assistant designed to analyze and synthesize information. Follow these rules precisely:

1.  *Your Core Purpose:* Your main role is to answer questions by synthesizing information found in the 'Knowledge Base'.

2.  *Answering About Yourself:* If asked about your identity or purpose, answer based on the definition in Rule #1.

3.  *Answering About the Content:* Your primary goal is to synthesize a comprehensive answer from the provided 'Knowledge Base'.
    - *Directness:* *NEVER* start your answer with phrases like "Based on the text," "According to the provided context," or any similar reference to the source material. Answer the question directly as if you know the information yourself.
    - *Combine Information:* You MUST combine related pieces of information from the context to formulate a complete and helpful answer. Do not just quote the document.
    - *No Direct Definition:* If the user asks for a definition (e.g., "what is X?") and a formal definition is not present, create a descriptive summary of X based on all the available information in the context.
    - *Handling Insufficient Information:* If the context mentions the topic but does not contain enough detail to answer the question thoroughly, first state what is known, and then clarify that a complete answer or definition is not available in the provided text.
    - *Safety Net:* If the 'Knowledge Base' contains no relevant information about the question's subject at all, then and only then should you respond with the exact phrase: "I don't have the information in my knowledge base."

4.  *Communication Language:*
    - You MUST respond only in English.
    - If a user communicates in any other language, you MUST reply only with the exact sentence below (and nothing else):
    "I'm sorry, I can only communicate in English."

5.  *Tone and Interaction Guidelines:*
    - Maintain a professional, warm, and loyal tone throughout every interaction.

6.  *Output Format:*
    - All responses MUST be formatted in clean, readable HTML suitable for direct web display.
    - Use appropriate tags for structure, such as `<p>` for paragraphs, `<ul>` and `<li>` for lists, and `<strong>` for emphasis.
    - Do NOT include `<html>`, `<head>`, or `<body>` tags. Provide only the content that would go inside the `<body>`.
    """

def get_user_prompt_content(context: str, chat_history: str, question: str) -> str:
    """Formats the user-facing part of the prompt."""
    return f"""
    Knowledge Base:
    {context}

    Chat History:
    {chat_history}

    Human: {question}
    AI:
    """

async def _get_gemini_response_async(system_prompt: str, user_prompt: str) -> str:
    """Gets a response from the Google Gemini model asynchronously."""
    try:
        model_name = current_app.config["GEMINI_MODEL_NAME"]
        model = genai.GenerativeModel(model_name)
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        response = await model.generate_content_async(full_prompt)
        return response.text
    except Exception as e:
        error_logger.error(f"Error getting response from GenAI (async): {e}", exc_info=True)
        raise ExternalApiError("The Gemini service failed.") from e

async def _get_openai_compatible_response_async(system_prompt: str, user_prompt: str, api_key: str, base_url: str | None, model_name: str) -> str:
    """Gets a response from an OpenAI-compatible API asynchronously."""
    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        error_logger.error(f"Error getting response from OpenAI-compatible API ({model_name}) (async): {e}", exc_info=True)
        raise ExternalApiError(f"The {model_name} service failed.") from e

async def get_model_response_async(system_prompt: str, user_prompt: str, model_provider: str) -> str:
    """
    Routes the prompt to the correct LLM provider and returns a response asynchronously.
    """
    if model_provider == "gemini":
        return await _get_gemini_response_async(system_prompt, user_prompt)
    
    elif model_provider == "openai":
        api_key = current_app.config["OPENAI_API_KEY"]
        model_name = current_app.config["OPENAI_MODEL_NAME"]
        if not api_key:
            raise ExternalApiError("OpenAI API key is not configured.")
        return await _get_openai_compatible_response_async(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            api_key=api_key,
            base_url=None,
            model_name=model_name
        )
    
    elif model_provider == "deepseek":
        api_key = current_app.config["DEEPSEEK_API_KEY"]
        model_name = current_app.config["DEEPSEEK_MODEL_NAME"]
        base_url = current_app.config["DEEPSEEK_BASE_URL"]
        if not api_key:
            raise ExternalApiError("DeepSeek API key is not configured.")
        return await _get_openai_compatible_response_async(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            api_key=api_key,
            base_url=base_url,
            model_name=model_name
        )
    
    else:
        raise ValueError(f"Unknown model provider: {model_provider}")