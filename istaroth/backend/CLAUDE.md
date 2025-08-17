# Backend Development Guide

## Database & Migration Management

### Schema Management
- Uses **Alembic** for database migrations
- Migration Config: `alembic.ini`
- SQLAlchemy models defined in `db_models.py`
- Migration files in `migrations/versions/`

### Workflow
1. Modify SQLAlchemy models in `db_models.py`
2. Generate migration: `alembic revision -m "description"`
3. Edit migration file to define upgrade/downgrade logic
4. Apply migration: `alembic upgrade head`

## API Structure
- FastAPI application in `app.py`
- Routers organized in `routers/` directory
- Database and other dependencies in `dependencies.py`
- Request and response models in `models.py`

## Development Commands
- Run backend: `python scripts/run_backend.py`
- Generate migration: `alembic revision -m "description"`
- Apply migrations: `alembic upgrade head`
