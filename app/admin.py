import logging
import time
from flask import current_app, flash, request, redirect, url_for, session, render_template_string
from flask_admin import Admin, AdminIndexView, BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.model.template import macro
from sqlalchemy import inspect
from app.celery_worker import process_document_embedding_task
from app.models import db, Syllabus, ClassModel, Subject, Document, User, DocumentChunk
from app import utils

# Get logger instances
app_logger = logging.getLogger('app')
error_logger = logging.getLogger('error')
security_logger = logging.getLogger('security')

# --- Login Template ---
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <title>Admin Login</title>
  <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css">
</head>
<body>
<div class="container">
    <div class="row">
        <div class="col-md-4 col-md-offset-4">
            <h2>Admin Login</h2>
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% if messages %}
                {% for category, message in messages %}
                  <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
              {% endif %}
            {% endwith %}
            <form method="post">
                <div class="form-group">
                    <label for="username">Username</label>
                    <input type="text" name="username" class="form-control" required>
                </div>
                <div class="form-group">
                    <label for="password">Password</label>
                    <input type="password" name="password" class="form-control" required>
                </div>
                <button type="submit" class="btn btn-primary">Login</button>
            </form>
        </div>
    </div>
</div>
</body>
</html>
"""

def process_document_embedding(document_id):
    """
    The background task for processing a document.
    REMOVED: `app_context` argument is no longer needed as the Celery task handles it.
    """
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

        # Clear old chunks before adding new ones
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

# --- Session-based authentication views ---
class AuthMixin:
    def is_accessible(self):
        return session.get('admin_logged_in') is True
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('admin_login.index'))

class AdminModelView(AuthMixin, ModelView):
    pass

class MyAdminIndexView(AuthMixin, AdminIndexView):
    pass

class AdminLoginView(BaseView):
    @expose('/', methods=('GET', 'POST'))
    def index(self):
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            admin_user = User.query.filter_by(username=username, is_admin=True).first()
            if admin_user and admin_user.check_password(password):
                session['admin_logged_in'] = True
                session['admin_user'] = username
                security_logger.info(f"Admin user {username} logged in successfully.")
                flash('Logged in successfully.', 'success')
                return redirect(url_for('admin.index'))
            else:
                security_logger.warning(f"Failed admin login attempt for username: {username}")
                flash('Invalid username or password.', 'error')
        return render_template_string(LOGIN_TEMPLATE)
    def is_visible(self):
        return False

class AdminLogoutView(AuthMixin, BaseView):
    @expose('/')
    def index(self):
        user = session.get('admin_user', 'Unknown')
        session.pop('admin_logged_in', None)
        session.pop('admin_user', None)
        security_logger.info(f"Admin user {user} logged out.")
        flash('You have been logged out.', 'success')
        return redirect(url_for('admin_login.index'))


class DocumentView(AdminModelView):
    """Custom view for the Document model in the admin panel."""
    column_list = ['id', 'syllabus', 'class_model', 'subject', 'processing_status','processing_error','processing_time_ms', 'created_at']
    form_excluded_columns = ['chunks', 'created_at', 'processing_status', 'processing_time_ms', 'processing_error']
    column_default_sort = ('created_at', True)
    column_searchable_list = ['source_url', 'subject.name', 'class_model.name', 'syllabus.name']
    column_filters = ['processing_status', 'subject', 'class_model', 'syllabus', 'created_at']
    column_formatters = { 'processing_time_ms': macro('render_processing_time') }
    list_template = 'admin/document_list.html'

    def _flash_duplicate_error(self):
        """Flashes the user-friendly duplicate entry error message."""
        flash(
            "🚫 Entry Already Exists: A document with this exact combination of Syllabus, Class, and Subject already exists.",
            'error'
        )

    def create_model(self, form):
        # ... (no changes in this method)
        return super().create_model(form)

    def update_model(self, form, model):
        """
        Override update_model to check for duplicates and handle URL changes explicitly.
        """
        existing_doc = Document.query.filter_by(
            syllabus=form.syllabus.data,
            class_model=form.class_model.data,
            subject=form.subject.data
        ).first()

        if existing_doc and existing_doc.id != model.id:
            self._flash_duplicate_error()
            return False

        url_changed = form.source_url.data != model.source_url
        form.populate_obj(model)

        if url_changed:
            app_logger.info(f"Source URL changed for Document ID: {model.id}. Triggering re-processing.")
            # Commit changes to the model first (like the new URL)
            self.session.commit()

            # --- MODIFIED: Call the Celery task ---
            process_document_embedding_task.delay(model.id)
            flash("Source URL updated. Old document data cleared. Starting re-processing.", 'info')
        else:
            self.session.commit()

        return True

    def after_model_change(self, form, model, is_created):
        """
        This hook now ONLY handles new document creation.
        """
        if is_created:
            app_logger.info(f"Triggering embedding process for new Document ID: {model.id}.")
            # --- MODIFIED: Call the Celery task ---
            process_document_embedding_task.delay(model.id)
            flash(f"Document processing has started for {model.id}. Refresh to see status updates.", 'success')

def setup_admin(app):
    """Initializes the admin panel."""
    admin = Admin(app, name='Chatbot Admin', template_mode='bootstrap3', index_view=MyAdminIndexView(url="/admin"))
    admin.add_view(AdminModelView(Syllabus, db.session, category="Content Management"))
    admin.add_view(AdminModelView(ClassModel, db.session, name="Classes", category="Content Management"))
    admin.add_view(AdminModelView(Subject, db.session, category="Content Management"))
    admin.add_view(DocumentView(Document, db.session, category="Content Management"))
    admin.add_view(AdminLoginView(name='Login', endpoint='admin_login'))
    admin.add_view(AdminLogoutView(name='Logout', endpoint='logout'))