import logging
import time
from flask import current_app, flash, request, Response
from flask_admin import Admin, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from flask_admin.model.template import macro
from app.models import db, Syllabus, ClassModel, Subject, Document
from app import utils

# Get logger instances
app_logger = logging.getLogger('app')
error_logger = logging.getLogger('error')

def process_document_embedding(document_id, app_context):
    """The background task for processing a document."""
    with app_context:
        start_time = time.time()
        doc = None
        try:
            # --- Set status to PROCESSING ---
            doc = Document.query.get(document_id)
            if not doc:
                error_logger.error(f"Document with ID {document_id} not found for embedding.")
                return

            doc.processing_status = 'PROCESSING'
            doc.processing_error = None # Clear previous errors
            db.session.commit()
            app_logger.info(f"Set status to PROCESSING for Document ID: {document_id}")

            # 1. Get PDF Text
            raw_text = utils.get_pdf_text(doc.source_url)
            if not raw_text:
                raise ValueError("Could not extract text from PDF. Check URL and PDF format.")

            # 2. Get Text Chunks
            text_chunks = utils.get_text_chunks(raw_text)

            # 3. Get Embeddings
            embeddings = utils.get_embeddings_batch(text_chunks)
            if not embeddings:
                raise ValueError("Failed to generate embeddings from the AI model.")

            # 4. Create and Save DocumentChunk Objects
            from app.models import DocumentChunk
            chunks_to_add = [
                DocumentChunk(document_id=doc.id, content=content, embedding=embeddings[i])
                for i, content in enumerate(text_chunks)
            ]
            db.session.bulk_save_objects(chunks_to_add)

            # --- Set status to COMPLETED ---
            end_time = time.time()
            doc.processing_status = 'COMPLETED'
            doc.processing_time_ms = int((end_time - start_time) * 1000)
            db.session.commit()
            app_logger.info(f"Successfully processed. Status set to COMPLETED for Document ID: {doc.id}")

        except Exception as e:
            db.session.rollback()
            error_logger.critical(f"Critical error in embedding background task for doc {document_id}: {e}", exc_info=True)
            if doc:
                # --- Set status to FAILED and save the error ---
                doc.processing_status = 'FAILED'
                doc.processing_error = str(e)
                db.session.commit()
                app_logger.error(f"Status set to FAILED for Document ID: {doc.id}")


class AdminModelView(ModelView):
    """ Custom ModelView to enforce Basic Auth. """
    def is_accessible(self):
        auth = request.authorization
        if not auth or not (
            auth.username == current_app.config['ADMIN_USERNAME'] and
            auth.password == current_app.config['ADMIN_PASSWORD']
        ):
            return False
        return True

    def inaccessible_callback(self, name, **kwargs):
        return Response(
            'Could not verify your access level for that URL.\n'
            'You have to login with proper credentials', 401,
            {'WWW-Authenticate': 'Basic realm="Login Required"'}
        )

class MyAdminIndexView(AdminIndexView):
    """ Custom AdminIndexView to enforce Basic Auth. """
    def is_accessible(self):
        auth = request.authorization
        if not auth or not (
            auth.username == current_app.config['ADMIN_USERNAME'] and
            auth.password == current_app.config['ADMIN_PASSWORD']
        ):
            return False
        return True

    def inaccessible_callback(self, name, **kwargs):
        return Response(
            'Could not verify your access level for that URL.\n'
            'You have to login with proper credentials', 401,
            {'WWW-Authenticate': 'Basic realm="Login Required"'}
        )


class DocumentView(AdminModelView):
    """Custom view for the Document model in the admin panel."""
    column_list = ['id', 'subject', 'processing_status', 'processing_error', 'processing_time_ms', 'created_at']
    column_searchable_list = ['source_url', 'subject.name', 'class_model.name', 'syllabus.name']
    column_filters = ['processing_status', 'subject', 'class_model', 'syllabus', 'created_at']
    column_formatters = {
        'processing_time_ms': macro('render_processing_time')
    }

    list_template = 'admin/document_list.html'

    def after_model_change(self, form, model, is_created):
        """This function is called after a new document is created via the admin panel."""
        if is_created:
            app_logger.info(f"Document created: {model.id}. Triggering embedding process.")
            executor = current_app.config['EXECUTOR']
            app_context = current_app.app_context()
            executor.submit(process_document_embedding, model.id, app_context)
            flash(f"Document processing has started for {model.id}. Refresh to see status updates.", 'success')

def setup_admin(app):
    """Initializes the admin panel."""
    admin = Admin(app, name='Chatbot Admin', template_mode='bootstrap3', index_view=MyAdminIndexView())

    admin.add_view(AdminModelView(Syllabus, db.session, category="Content Management"))
    admin.add_view(AdminModelView(ClassModel, db.session, name="Classes", category="Content Management"))
    admin.add_view(AdminModelView(Subject, db.session, category="Content Management"))
    admin.add_view(DocumentView(Document, db.session, category="Content Management"))