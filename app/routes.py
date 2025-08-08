import logging
import secrets
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from marshmallow import ValidationError
from app.models import db, User, Subject, DocumentChunk, ChatHistory
from app.schemas import UserRegisterSchema, UserLoginSchema, AddSubjectSchema, ChatSchema, ClearSessionSchema
from app.exceptions import ApiError
from app import utils, limiter

# Get logger instances
app_logger = logging.getLogger('app')
error_logger = logging.getLogger('error')
security_logger = logging.getLogger('security')

# Create a Blueprint
api_bp = Blueprint('api', __name__)

# --- Authentication Endpoints ---

@api_bp.route("/register", methods=["POST"])
@limiter.limit("5 per hour") # Stricter rate limit for registration
def register():
    """
    User registration endpoint.
    Validates input, checks for existing user, creates a new user.
    """
    try:
        data = UserRegisterSchema().load(request.get_json())
    except ValidationError as err:
        raise ApiError(f"Validation failed: {err.messages}", 400)

    username = data['username']
    password = data['password']

    if User.query.filter_by(username=username).first():
        security_logger.warning(f"Registration attempt for existing username: {username}")
        raise ApiError("Username already exists.", 409) # 409 Conflict

    new_user = User(username=username)
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()
    
    security_logger.info(f"New user registered: {username}")
    return jsonify({"message": f"User {username} registered successfully"}), 201

@api_bp.route("/login", methods=["POST"])
@limiter.limit("10 per hour") # Stricter rate limit for login
def login():
    """
    User login endpoint.
    Validates input, checks credentials, returns JWT access token.
    """
    try:
        data = UserLoginSchema().load(request.get_json())
    except ValidationError as err:
        raise ApiError(f"Validation failed: {err.messages}", 400)

    username = data['username']
    password = data['password']
    
    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
    
        expires = current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
        access_token = create_access_token(identity=username, expires_delta=expires)
        
        security_logger.info(f"Successful login for user: {username}")
        return jsonify(access_token=access_token)
    
    security_logger.warning(f"Failed login attempt for username: {username}")
    raise ApiError("Invalid username or password", 401)



@api_bp.route("/add_subject", methods=["POST"])
@jwt_required()
def add_subject():
    """
    Processes a new PDF. Any authenticated user can add a document.
    """
    username = get_jwt_identity()
    app_logger.info(f"User '{username}' initiated add_subject.")
    
    try:
        data = AddSubjectSchema().load(request.get_json())
        pdf_url = data["subjecturl"]
    except ValidationError as err:
        raise ApiError(f"Validation failed: {err.messages}", 400)

    try:
        raw_text = utils.get_pdf_text(pdf_url)
        if not raw_text:
            raise ApiError("Could not extract text from the PDF.", 500)

        text_chunks = utils.get_text_chunks(raw_text)
        subject_key = secrets.token_hex(16)
        
        # --- MODIFIED ---
        # The new subject is no longer linked to a user.
        new_subject = Subject(
            subject_key=subject_key,
            source_url=pdf_url
        )
        db.session.add(new_subject)
        db.session.flush()

        embeddings = utils.get_embeddings_batch(text_chunks)
        if not embeddings:
            db.session.rollback()
            raise ApiError("Failed to generate embeddings for the document.", 500)

        chunks_to_add = [
            DocumentChunk(subject_id=new_subject.id, content=content, embedding=embeddings[i])
            for i, content in enumerate(text_chunks)
        ]
        db.session.bulk_save_objects(chunks_to_add)
        db.session.commit()
        
        return jsonify({
            "message": "Subject added successfully",
            "subjectkey": subject_key
        }), 201

    except Exception as e:
        db.session.rollback()
        error_logger.error(f"Error in /add_subject for user '{username}': {e}", exc_info=True)
        raise ApiError("An internal error occurred while adding the subject.", 500)

@api_bp.route("/chat", methods=["POST"])
@jwt_required()
def chat():
    """
    Handles a chat question, including previous conversation history for context.
    """
    auth_user_username = get_jwt_identity()

    try:
        data = ChatSchema().load(request.get_json())
        chatbot_user_id = data["chatbot_user_id"]
        question = data["question"]
        subject_key = data["subjectkey"]
    except ValidationError as err:
        raise ApiError(f"Validation failed: {err.messages}", 400)

    try:
        subject = Subject.query.filter_by(subject_key=subject_key).first()
        if not subject:
            raise ApiError("Subject not found.", 404)

        # --- MODIFIED ---
        # 1. Fetch recent chat history for the current session to provide context.
        recent_history = db.session.query(ChatHistory).filter(
            ChatHistory.user_id == chatbot_user_id,
            ChatHistory.subject_key == subject_key
        ).order_by(
            ChatHistory.created_at.desc()  # Get the most recent first
        ).limit(10).all()
        
        # The history is in reverse chronological order, so we reverse it back.
        recent_history.reverse()

        # 2. Format the history into a simple string for the prompt.
        formatted_history = "\n".join([f"Human: {h.question}\nAI: {h.answer}" for h in recent_history])

        question_embedding = utils.get_single_embedding(question)
        relevant_chunks = DocumentChunk.query.filter(DocumentChunk.subject_id == subject.id).order_by(DocumentChunk.embedding.l2_distance(question_embedding)).limit(5).all()
        context = "\n".join([chunk.content for chunk in relevant_chunks])
        
        model, prompt_template = utils.get_conversational_chain()

        # 3. Pass the formatted history to the prompt template.
        prompt = prompt_template.format(
            context=context,
            chat_history=formatted_history,
            question=question
        )
        
        response = model.generate_content(prompt)
        answer = response.text
        
        history_entry = ChatHistory(
            user_id=chatbot_user_id,
            subject_key=subject_key,
            question=question,
            answer=answer
        )
        db.session.add(history_entry)
        db.session.commit()
        
        return jsonify({"answer": answer})

    except Exception as e:
        db.session.rollback()
        if isinstance(e, ApiError):
            raise e
        error_logger.error(f"Error in /chat for user '{auth_user_username}': {e}", exc_info=True)
        raise ApiError("An internal error occurred during chat processing.", 500)


@api_bp.route("/clear_session", methods=["POST"])
@jwt_required()
def clear_session():
    """
    Clears all chat history for a given chatbot session ID,
    which is provided in the request body.
    """
    auth_user_username = get_jwt_identity()
    
    try:
        # Validate and get the chatbot_user_id from the request body
        data = ClearSessionSchema().load(request.get_json())
        chatbot_user_id = data["chatbot_user_id"]
    except ValidationError as err:
        raise ApiError(f"Validation failed: {err.messages}", 400)

    try:
        # The query now targets the user ID from the request body
        num_deleted = ChatHistory.query.filter_by(user_id=chatbot_user_id).delete()
        db.session.commit()
        
        app_logger.info(f"Auth user '{auth_user_username}' cleared {num_deleted} records for session user '{chatbot_user_id}'.")
        return jsonify({
            "message": f"Successfully cleared session for user '{chatbot_user_id}'.",
            "records_deleted": num_deleted
        })
    except Exception as e:
        db.session.rollback()
        error_logger.error(f"Error in /clear_session by auth user '{auth_user_username}' for session '{chatbot_user_id}': {e}", exc_info=True)
        raise ApiError("An internal error occurred while clearing the session.", 500)