from sqlalchemy import create_engine, text

# Import the 'create_app' factory and the 'db' instance
from app import create_app, db

def setup_database():
    """
    Creates the database, enables the pgvector extension, and creates all tables.
    This script should be run once before starting the application for the first time.
    """
    
    # Create a Flask app context to access the configuration
    app = create_app()
    
    with app.app_context():
        # Get the database URI from the application's config
        database_uri = app.config['SQLALCHEMY_DATABASE_URI']
        
        # Create a SQLAlchemy engine to connect directly to the database server
        engine = create_engine(database_uri)
        
        # Connect and enable the pgvector extension
        with engine.connect() as connection:
            try:
                print("Attempting to enable the 'vector' extension...")
                # The 'IF NOT EXISTS' clause prevents errors on subsequent runs
                connection.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
                connection.commit()
                print("PostgreSQL 'vector' extension is enabled.")
            except Exception as e:
                print(f"Could not enable pgvector extension. It might already exist or there's a permissions issue. Error: {e}")
                connection.rollback()

        # Create all tables defined in the models (User, Subject, etc.)
        print("Creating all database tables...")
        db.create_all()
        print("Database tables created successfully.")

if __name__ == "__main__":
    setup_database()