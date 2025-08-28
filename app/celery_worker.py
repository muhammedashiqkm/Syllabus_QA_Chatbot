from celery import Celery
from app.tasks import process_document_embedding
from app.exceptions import ExternalApiError

celery = Celery(__name__, broker='redis://redis:6379/0', backend='redis://redis:6379/0')


@celery.task(autoretry_for=(ExternalApiError,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def process_document_embedding_task(document_id):
    """
    Celery task wrapper for document embedding.
    This task will now automatically retry if an ExternalApiError occurs.
    """
    from app import create_app
    app = create_app()
    with app.app_context():
        process_document_embedding(document_id)