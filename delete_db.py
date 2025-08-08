from app import create_app, db
    
def delete_all_tables():
        """
        Connects to the database and drops all tables known to the application.
        """
        app = create_app()
        with app.app_context():
            print("Connecting to the database to drop all tables...")
            # This command introspects the database and drops all known tables.
            db.drop_all()
            print("All tables dropped successfully.")
    
if __name__ == "__main__":
        # A simple confirmation step to prevent accidental deletion.
        confirm = input("Are you absolutely sure you want to drop all tables? This action cannot be undone. (yes/no): ")
        if confirm.lower() == 'yes':
            delete_all_tables()
        else:
            print("Operation cancelled.")