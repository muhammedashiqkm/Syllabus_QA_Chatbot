import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required
from marshmallow import ValidationError
from app.models import db, User, Document, DocumentChunk, ChatHistory, Syllabus, ClassModel, Subject
from app.schemas import UserRegisterSchema, UserLoginSchema, ChatSchema, ClearSessionSchema
from app.exceptions import ApiError
from app import utils, limiter

# Get logger instances
app_logger = logging.getLogger('app')
error_logger = logging.getLogger('error')
security_logger = logging.getLogger('security')

# Create a Blueprint
api_bp = Blueprint('api', __name__)


# Health Check
@api_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for Docker."""
    return jsonify({"status": "healthy"}), 200

# --- Authentication Endpoints ---
@api_bp.route("/register", methods=["POST"])
@limiter.limit("10 per hour")
def register():
    """
    User registration endpoint.
    Allows creating a user and optionally setting them as an admin in the request.
    """
    try:
        data = UserRegisterSchema().load(request.get_json())
    except ValidationError as err:
        raise ApiError(f"Validation failed: {err.messages}", 400)


    # Check for the registration secret
    if data['registration_secret'] != current_app.config['REGISTRATION_SECRET_KEY']:
        security_logger.warning(f"Invalid registration secret provided by IP: {request.remote_addr}")
        raise ApiError("Not authorized to perform this action.", 403)

    username = data['username']
    if User.query.filter_by(username=username).first():
        security_logger.warning(f"Registration attempt for existing username: {username}")
        raise ApiError("Username already exists.", 409)

    # Create the new user
    new_user = User(username=username)
    new_user.set_password(data['password'])
    
    # Set the admin status directly from the request data
    # The 'is_admin' field defaults to False if not provided, thanks to `load_default` in the schema
    new_user.is_admin = data['is_admin']

    db.session.add(new_user)
    db.session.commit()

    # Log the event based on whether an admin was created
    if new_user.is_admin:
        security_logger.critical(f"Admin user '{username}' created via API request.")
    else:
        security_logger.info(f"New user registered: {username}")

    return jsonify({"message": f"User '{username}' registered successfully."}), 201



@api_bp.route("/login", methods=["POST"])
@limiter.limit("10 per hour")
def login():
    """User login endpoint."""
    try:
        data = UserLoginSchema().load(request.get_json())
    except ValidationError as err:
        raise ApiError(f"Validation failed: {err.messages}", 400)

    user = User.query.filter_by(username=data['username']).first()
    if user and user.check_password(data['password']):
        expires = current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
        access_token = create_access_token(identity=user.username, expires_delta=expires)
        security_logger.info(f"Successful login for user: {user.username}")
        return jsonify(access_token=access_token)
    
    security_logger.warning(f"Failed login attempt for username: {data['username']}")
    raise ApiError("Invalid username or password", 401)


# --- Chat Endpoints ---

@api_bp.route("/categories", methods=["GET"])
@jwt_required()
def get_categories():
    """
    Provides a complete list of all available syllabuses, classes, and subjects.
    Requires authentication.
    """ 
    try:
        # Query each table and get a sorted list of names
        syllabuses = [s.name for s in Syllabus.query.order_by(Syllabus.name).all()]
        classes = [c.name for c in ClassModel.query.order_by(ClassModel.name).all()]
        subjects = [s.name for s in Subject.query.order_by(Subject.name).all()]

        response = {
            "syllabuses": syllabuses,
            "classes": classes,
            "subjects": subjects
        }
        
        return jsonify(response)
        
    except Exception as e:
        # Log the error in case the database query fails
        error_logger.error(f"Error in /categories: {e}", exc_info=True)
        raise ApiError("An internal error occurred while fetching categories.", 500)


@api_bp.route("/chat", methods=["POST"])
@jwt_required()
def chat():
    """Handles a chat question against a categorized document."""
    try:
        data = ChatSchema().load(request.get_json())
    except ValidationError as err:
        raise ApiError(f"Validation failed: {err.messages}", 400)

    try:
        # Find the document based on the provided categories
        document = db.session.query(Document).join(Syllabus).join(ClassModel).join(Subject).filter(
            Syllabus.name == data['syllabus'],
            ClassModel.name == data['class_name'], 
            Subject.name == data['subject']
        ).first()

        if not document:
            raise ApiError("Document matching the specified criteria not found.", 404)

        # Fetch recent chat history
        recent_history = db.session.query(ChatHistory).filter(
            ChatHistory.chatbot_user_id == data['chatbot_user_id']
        ).order_by(ChatHistory.created_at.desc()).limit(10).all()
        recent_history.reverse()
        formatted_history = "\n".join([f"Human: {h.question}\nAI: {h.answer}" for h in recent_history])

        # Find relevant chunks using vector search
        question_embedding = utils.get_single_embedding(data['question'])
        if not question_embedding:
            raise ApiError("Could not generate embedding for the question.", 500)

        relevant_chunks = DocumentChunk.query.filter(
            DocumentChunk.document_id == document.id
        ).order_by(DocumentChunk.embedding.l2_distance(question_embedding)).limit(5).all()
        context = "\n".join([chunk.content for chunk in relevant_chunks])
        
        # Generate the answer
        model, prompt_template = utils.get_conversational_chain()
        prompt = prompt_template.format(
            context=context,
            chat_history=formatted_history,
            question=data['question']
        )
        
        response = model.generate_content(prompt)
        answer = response.text
        
        # Save the new history entry
        history_entry = ChatHistory(
            chatbot_user_id=data['chatbot_user_id'],
            question=data['question'],
            answer=answer
        )
        db.session.add(history_entry)
        db.session.commit()
        
        return jsonify({"answer": answer})

    except Exception as e:
        db.session.rollback()
        if isinstance(e, ApiError):
            raise e
        error_logger.error(f"Error in /chat: {e}", exc_info=True)
        raise ApiError("An internal error occurred during chat processing.", 500)


@api_bp.route("/clear_session", methods=["POST"])
@jwt_required()
def clear_session():
    """Clears all chat history for a given chatbot session ID."""
    try:
        data = ClearSessionSchema().load(request.get_json())
    except ValidationError as err:
        raise ApiError(f"Validation failed: {err.messages}", 400)

    try:
        num_deleted = ChatHistory.query.filter_by(chatbot_user_id=data["chatbot_user_id"]).delete()
        db.session.commit()
        
        app_logger.info(f"Cleared {num_deleted} records for session user '{data['chatbot_user_id']}'.")
        return jsonify({
            "message": f"Successfully cleared session.",
            "records_deleted": num_deleted
        })
    except Exception as e:
        db.session.rollback()
        error_logger.error(f"Error in /clear_session: {e}", exc_info=True)
        raise ApiError("An internal error occurred while clearing the session.", 500)