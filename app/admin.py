import logging
from flask import flash, request, redirect, url_for, session, render_template
from flask_admin import Admin, AdminIndexView, BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.model.template import macro
from app.models import db, Syllabus, ClassModel, Subject, Document, User
from app.celery_worker import process_document_embedding_task

# Get logger instances
app_logger = logging.getLogger('app')
security_logger = logging.getLogger('security')


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
        return render_template('admin/login.html')
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
        existing_doc = Document.query.filter_by(
            syllabus=form.syllabus.data,
            class_model=form.class_model.data,
            subject=form.subject.data
        ).first()

        if existing_doc:
            self._flash_duplicate_error()
            return False

        return super().create_model(form)

    def update_model(self, form, model):
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
            self.session.commit()
            process_document_embedding_task.delay(model.id)
            flash("Source URL updated. Old document data cleared. Starting re-processing.", 'info')
        else:
            self.session.commit()

        return True

    def after_model_change(self, form, model, is_created):
        if is_created:
            app_logger.info(f"Triggering embedding process for new Document ID: {model.id}.")
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