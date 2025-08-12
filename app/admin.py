import logging
import time
from flask import current_app, flash, request, redirect, url_for, session, render_template_string
from flask_admin import Admin, AdminIndexView, BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.model.template import macro
from app.models import db, Syllabus, ClassModel, Subject, Document, User
from app import utils
from sqlalchemy.exc import IntegrityError # Import the specific exception

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


# --- MODIFIED: Session-based authentication views ---

class AuthMixin:
    """Mixin for session-based authentication in admin views."""
    def is_accessible(self):
        return session.get('admin_logged_in') is True

    def inaccessible_callback(self, name, **kwargs):
        # Redirect to login page if user is not authenticated
        return redirect(url_for('admin_login.index'))

class AdminModelView(AuthMixin, ModelView):
    """ Custom ModelView to enforce session-based auth. """
    pass

class MyAdminIndexView(AuthMixin, AdminIndexView):
    """ Custom AdminIndexView to enforce session-based auth. """
    pass

class AdminLoginView(BaseView):
    @expose('/', methods=('GET', 'POST'))
    def index(self):
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')

            # Find the admin user in the database
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
        # This view should not be visible in the menu
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
    column_list = ['id', 'subject', 'processing_status', 'processing_time_ms', 'created_at']
    column_searchable_list = ['source_url', 'subject.name', 'class_model.name', 'syllabus.name']
    column_filters = ['processing_status', 'subject', 'class_model', 'syllabus', 'created_at']
    column_formatters = {
        'processing_time_ms': macro('render_processing_time')
    }

    list_template = 'admin/document_list.html'

    # This method now handles the unique constraint error and flashes the concise message.
    def create_model(self, form):
        """
            Custom create_model to handle unique constraint violations.
        """
        try:
            model = self.model()
            form.populate_obj(model)
            self.session.add(model)
            self._on_model_change(form, model, True)
            self.session.commit()
            return model
        except IntegrityError as e:
            # Check if it's our specific unique constraint error
            if "_syllabus_class_subject_uc" in str(e.orig):
                self.session.rollback()
                flash('Creation Failed: A document with the same combination of Syllabus, Class, and Subject already exists.', 'error')
                return False
            else:
                # If it's a different integrity error, raise it
                raise e
        except Exception as ex:
            if not self.handle_view_exception(ex):
                flash(f'Failed to create model. {ex}', 'error')
            self.session.rollback()
            return False

    def after_model_change(self, form, model, is_created):
        """This function is called after a new document is created via the admin panel."""
        # The check for is_created is now more robust because create_model can return False
        if is_created and model:
            app_logger.info(f"Document created: {model.id}. Triggering embedding process.")
            executor = current_app.config['EXECUTOR']
            app_context = current_app.app_context()
            executor.submit(process_document_embedding, model.id, app_context)
            flash(f"Document processing has started for {model.id}. Refresh to see status updates.", 'info')

def setup_admin(app):
    """Initializes the admin panel."""
    admin = Admin(app, name='Chatbot Admin', template_mode='bootstrap3', index_view=MyAdminIndexView(url="/admin"))

    # Add model views
    admin.add_view(AdminModelView(Syllabus, db.session, category="Content Management"))
    admin.add_view(AdminModelView(ClassModel, db.session, name="Classes", category="Content Management"))
    admin.add_view(AdminModelView(Subject, db.session, category="Content Management"))
    admin.add_view(DocumentView(Document, db.session, category="Content Management"))
    admin.add_view(AdminModelView(User, db.session, category="User Management")) # Added User management to admin

    # Add auth views
    admin.add_view(AdminLoginView(name='Login', endpoint='admin_login'))
    admin.add_view(AdminLogoutView(name='Logout', endpoint='logout'))