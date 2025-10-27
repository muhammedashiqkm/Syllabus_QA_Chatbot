from asgiref.wsgi import WsgiToAsgi
from app import create_app

# Create the standard Flask app (WSGI)
flask_app = create_app()

# Wrap the Flask app to make it an ASGI-compatible app
app = WsgiToAsgi(flask_app)