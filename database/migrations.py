from database.database import initialize_database


def run_migrations() -> None:
    """Runs the idempotent MVP schema and remains the migration entry point."""
    initialize_database()
