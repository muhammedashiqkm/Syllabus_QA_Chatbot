import logging
import time
from app.models import db, Document, DocumentChunk
from app import utils

app_logger = logging.getLogger('app')
error_logger = logging.getLogger('error')

def process_document_embedding(document_id):
    """The background task for processing a document."""
    start_time = time.time()
    doc = None
    try:
        doc = Document.query.get(document_id)
        if not doc:
            error_logger.error(f"Document with ID {document_id} not found for embedding.")
            return

        doc.processing_status = 'PROCESSING'
        doc.processing_error = None
        db.session.commit()
        app_logger.info(f"Set status to PROCESSING for Document ID: {document_id}")

        raw_text = utils.get_pdf_text(doc.source_url)
        if not raw_text:
            raise ValueError("Could not extract text from PDF. Check URL and PDF format.")

        text_chunks = utils.get_text_chunks(raw_text)
        embeddings = utils.get_embeddings_batch(text_chunks)
        if not embeddings:
            raise ValueError("Failed to generate embeddings from the AI model.")

        DocumentChunk.query.filter_by(document_id=doc.id).delete()
        db.session.commit()

        chunks_to_add = [
            DocumentChunk(document_id=doc.id, content=content, embedding=embeddings[i])
            for i, content in enumerate(text_chunks)
        ]
        db.session.bulk_save_objects(chunks_to_add)

        end_time = time.time()
        doc.processing_status = 'COMPLETED'
        doc.processing_time_ms = int((end_time - start_time) * 1000)
        db.session.commit()
        app_logger.info(f"Successfully processed. Status set to COMPLETED for Document ID: {doc.id}")

    except Exception as e:
        db.session.rollback()
        error_logger.critical(f"Critical error in embedding background task for doc {document_id}: {e}", exc_info=True)
        if doc:
            doc.processing_status = 'FAILED'
            doc.processing_error = str(e)
            db.session.commit()
            app_logger.error(f"Status set to FAILED for Document ID: {doc.id}")