import os
import requests
import io
import pypdf
import google.generativeai as genai
import logging
from langchain.text_splitter import RecursiveCharacterTextSplitter
from flask import current_app

error_logger = logging.getLogger('error')

# --- AI Model Configuration ---
def configure_genai():
    """Configures the Google AI API key from the app config."""
    api_key = current_app.config.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Google API Key not configured in the application.")
    genai.configure(api_key=api_key)

# --- PDF Processing ---
def get_pdf_text(pdf_url: str) -> str | None:
    """
    Downloads a PDF from a URL and extracts its text content.
    """
    try:
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status() 
        
        pdf_file = io.BytesIO(response.content)
        pdf_reader = pypdf.PdfReader(pdf_file)
        
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or "" 
        
        return text.replace('\x00', '')

    except requests.exceptions.RequestException as e:

        error_logger.error(f"Error downloading PDF from {pdf_url}: {e}")
        return None
    except Exception as e:
        
        error_logger.error(f"Error processing PDF from {pdf_url}: {e}")
        return None


# --- Text Chunking ---
def get_text_chunks(text: str) -> list[str]:
    """
    Splits a long text into smaller, manageable chunks.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_text(text)
    return chunks


# --- AI Model Interactions ---
def get_embeddings_batch(texts: list[str]) -> list[list[float]] | None:
    """
    Generates vector embeddings for a batch of texts using Google AI.
    """
    try:
        configure_genai()
        model_name = current_app.config.get("EMBEDDING_MODEL_NAME")
        result = genai.embed_content(
            model = model_name,
            content=texts,
            task_type="retrieval_document"
        )
        return result['embedding']
    except Exception as e:
        error_logger.error(f"Error getting batch embedding from GenAI: {e}", exc_info=True)
        return None

def get_single_embedding(text: str) -> list[float] | None:
    """
    Generates a vector embedding for a single text query.
    """
    try:
        configure_genai()
        model_name = current_app.config.get("EMBEDDING_MODEL_NAME")
        result = genai.embed_content(
            model=model_name,
            content=text,
            task_type="retrieval_query"
        )
        return result['embedding']
    except Exception as e:
        error_logger.error(f"Error getting single embedding from GenAI: {e}", exc_info=True)
        return None


def get_conversational_chain():
    """
    Creates the prompt template and loads the generative model for Q&A.
    """
    configure_genai()
    prompt_template = """
    You are a helpful AI assistant with a specific role. Follow these rules precisely:

    1.  *Your Core Purpose:* Your main role is to answer questions based on the information provided in the 'Knowledge Base' (which contains syllabus information). You should be helpful and concise.

    2.  *Answering About Yourself:* If the user asks about you, your role, your purpose, or your identity, you MUST answer based on the definition in Rule #1. For example, if asked "what is your purpose?", you should say something like, "My purpose is to act as a helpful assistant that answers questions based on the provided syllabus information."

    3.  *Answering About the Content:* For all other questions, you must base your answer strictly on the 'Knowledge Base' and the 'Chat History'.
        - Do not use phrases like "based on the document" or "according to the context".
        - If the answer is not in the 'Knowledge Base', you MUST respond with the exact phrase: "I don't have the information in my knowledge base."

    Knowledge Base:
    {context}

    Chat History:
    {chat_history}

    Human: {question}
    AI:
    """
    model_name = current_app.config.get("LLM_MODEL_NAME")
    model = genai.GenerativeModel(model_name)
    return model, prompt_template