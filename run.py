# Import the application factory from our 'app' package
from app import create_app

# Create the Flask app instance using the factory
# This encapsulates all the setup (config, blueprints, extensions)
app = create_app()

if __name__ == '__main__':
    # This block runs only when the script is executed directly (e.g., "python run.py")
    # It's useful for local development.
    # For production, a WSGI server like Gunicorn will import the 'app' object directly.
    app.run(host='0.0.0.0', port=5001, debug=False)