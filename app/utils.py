import os
import requests
import io
import pypdf
import google.generativeai as genai
import logging
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.exceptions import ExternalApiError
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

# --- Text Chunking ---
def get_text_chunks(text: str) -> list[str]:
    """Splits a long text into smaller, manageable chunks."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_text(text)
    return chunks

# --- AI Model Interactions ---
def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generates vector embeddings for a batch of texts using Google AI."""
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
        # Raise the custom exception instead of returning None
        raise ExternalApiError("The embedding service failed.") from e

def get_single_embedding(text: str) -> list[float]:
    """Generates a vector embedding for a single text query."""
    try:
        model_name = current_app.config.get("EMBEDDING_MODEL_NAME")
        result = genai.embed_content(
            model=model_name,
            content=text,
            task_type="retrieval_query"
        )
        return result['embedding']
    except Exception as e:
        error_logger.error(f"Error getting single embedding from GenAI: {e}", exc_info=True)
        # Raise the custom exception instead of returning None
        raise ExternalApiError("The embedding service failed.") from e

def get_conversational_chain():
    """Creates the prompt template and loads the generative model for Q&A."""
    prompt_template = """
    You are a helpful AI assistant designed to analyze and synthesize information. Follow these rules precisely:

1.  *Your Core Purpose:* Your main role is to answer questions by synthesizing information found in the 'Knowledge Base'.

2.  *Answering About Yourself:* If asked about your identity or purpose, answer based on the definition in Rule #1.

3.  *Answering About the Content:* Your primary goal is to synthesize a comprehensive answer from the provided 'Knowledge Base'.
    - *Directness:* *NEVER* start your answer with phrases like "Based on the text," "According to the provided context," or any similar reference to the source material. Answer the question directly as if you know the information yourself.
    - *Combine Information:* You MUST combine related pieces of information from the context to formulate a complete and helpful answer. Do not just quote the document.
    - *No Direct Definition:* If the user asks for a definition (e.g., "what is X?") and a formal definition is not present, create a descriptive summary of X based on all the available information in the context.
    - *Handling Insufficient Information:* If the context mentions the topic but does not contain enough detail to answer the question thoroughly, first state what is known, and then clarify that a complete answer or definition is not available in the provided text.
    - *Safety Net:* If the 'Knowledge Base' contains no relevant information about the question's subject at all, then and only then should you respond with the exact phrase: "I don't have the information in my knowledge base."

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