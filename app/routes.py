import logging
import asyncio
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required
from marshmallow import ValidationError
from app.models import db, User, Document, DocumentChunk, ChatHistory, Syllabus, ClassModel, Subject
from app.schemas import UserLoginSchema, ChatSchema, ClearSessionSchema
from app.exceptions import ApiError, ExternalApiError
from app import utils, limiter

# Get logger instances
app_logger = logging.getLogger('app')
error_logger = logging.getLogger('error')
security_logger = logging.getLogger('security')

api_bp = Blueprint('api', __name__)


def _get_document_sync(syllabus, class_name, subject):
    """Synchronous DB function to be run in a thread."""
    return db.session.query(Document).join(Syllabus).join(ClassModel).join(Subject).filter(
        Syllabus.name == syllabus,
        ClassModel.name == class_name, 
        Subject.name == subject
    ).first()

def _get_chat_history_sync(chatbot_user_id, limit):
    """Synchronous DB function to be run in a thread."""
    recent_history = db.session.query(ChatHistory).filter(
        ChatHistory.chatbot_user_id == chatbot_user_id
    ).order_by(ChatHistory.created_at.desc()).limit(limit).all()
    recent_history.reverse()
    return recent_history

def _get_relevant_chunks_sync(document_id, embedding):
    """Synchronous DB function to be run in a thread."""
    return DocumentChunk.query.filter(
        DocumentChunk.document_id == document_id
    ).order_by(DocumentChunk.embedding.l2_distance(embedding)).limit(5).all()

def _add_chat_history_sync(entry):
    """Synchronous DB function to be run in a thread."""
    try:
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e 

def _clear_chat_history_sync(chatbot_user_id):
    """Synchronous DB function to be run in a thread."""
    try:
        num_deleted = ChatHistory.query.filter_by(chatbot_user_id=chatbot_user_id).delete()
        db.session.commit()
        return num_deleted
    except Exception as e:
        db.session.rollback()
        raise e
        

@api_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for Docker."""
    return jsonify({"status": "healthy"}), 200


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
    """Provides a complete list of all available syllabuses, classes, and subjects.""" 
    try:
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
        error_logger.error(f"Error in /categories: {e}", exc_info=True)
        raise ApiError("An internal error occurred while fetching categories.", 500)


@api_bp.route("/chat", methods=["POST"])
@jwt_required()
async def chat():  
    """Handles a chat question against a categorized document."""
    try:
        data = ChatSchema().load(request.get_json())

       
        model_provider = data['model']
        app_logger.info(f"Chat request for session {data['chatbot_user_id']} using model: {model_provider}")

        document = await asyncio.to_thread(
            _get_document_sync, 
            data['syllabus'], 
            data['class_name'], 
            data['subject']
        )

        if not document:
            raise ApiError("Document matching the specified criteria not found.", 404)

        history_limit = current_app.config.get('CHAT_HISTORY_LIMIT', 10)
        recent_history = await asyncio.to_thread(
            _get_chat_history_sync, 
            data['chatbot_user_id'], 
            history_limit
        )
        formatted_history = "\n".join([f"Human: {h.question}\nAI: {h.answer}" for h in recent_history])

        
        question_embedding = await utils.get_single_embedding_async(data['question'])
        
        relevant_chunks = await asyncio.to_thread(
            _get_relevant_chunks_sync, 
            document.id, 
            question_embedding
        )
        context = "\n".join([chunk.content for chunk in relevant_chunks])
        
        system_prompt = utils.get_system_prompt()
        user_prompt = utils.get_user_prompt_content(
            context=context,
            chat_history=formatted_history,
            question=data['question']
        )
        
        answer = await utils.get_model_response_async(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_provider=model_provider
        )
        
        history_entry = ChatHistory(
            chatbot_user_id=data['chatbot_user_id'],
            question=data['question'],
            answer=answer
        )

        await asyncio.to_thread(_add_chat_history_sync, history_entry)
        
        return jsonify({"answer": answer})


    except ValidationError as err:
        raise ApiError(f"Validation failed: {err.messages}", 400)

    except ExternalApiError as e:
        error_logger.error(f"External API service failed: {e}", exc_info=True)
        raise ApiError(f"The AI service failed: {e}", 503)

    except Exception as e:
        if isinstance(e, ApiError):
            raise e
        error_logger.error(f"Error in /chat: {e}", exc_info=True)
        raise ApiError("An internal error occurred during chat processing.", 500)


@api_bp.route("/clear_session", methods=["POST"])
@jwt_required()
async def clear_session(): 
    """Clears all chat history for a given chatbot session ID."""
    try:
        data = ClearSessionSchema().load(request.get_json())
        
        num_deleted = await asyncio.to_thread(
            _clear_chat_history_sync, 
            data["chatbot_user_id"]
        )
        
        app_logger.info(f"Cleared {num_deleted} records for session user '{data['chatbot_user_id']}'.")
        return jsonify({
            "message": "Successfully cleared session.",
            "records_deleted": num_deleted
        })
    except Exception as e:
        error_logger.error(f"Error in /clear_session: {e}", exc_info=True)
        raise ApiError("An internal error occurred while clearing the session.", 500)