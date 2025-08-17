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

## OpenAPI Type Generation

### Overview
The backend automatically generates OpenAPI specifications that are consumed by the frontend for type-safe API interactions. This eliminates manual type synchronization and ensures frontend types stay in sync with backend changes.

### API Models (`models.py`)
- **Single Source of Truth**: Pydantic models in `models.py` define all API contracts
- **Automatic Documentation**: FastAPI generates OpenAPI spec from these models
- **Validation**: Pydantic provides request/response validation and serialization

### OpenAPI Spec Generation
- **Static Generation**: Use `scripts/generate_openapi.py` to generate `openapi.json` without running the server
- **Command**: `PYTHONPATH=. python scripts/generate_openapi.py`
- **Output**: `openapi.json` in project root
- **CI/CD Friendly**: No server dependencies for type generation

### Type Safety Workflow
1. **Modify API Models**: Update Pydantic models in `models.py`
2. **Generate OpenAPI Spec**: Run `python scripts/generate_openapi.py`
3. **Build Frontend**: Frontend build automatically generates TypeScript types from `openapi.json`
4. **Build Validation**: TypeScript compilation catches API contract mismatches

### Best Practices
- **Keep models.py updated**: This is the authoritative source for API contracts
- **Use descriptive docstrings**: They appear in generated documentation
- **Leverage Pydantic validation**: Add field validators for robust API contracts
- **Test API changes**: Ensure frontend builds successfully after model changes

## Development Commands
- Run backend: `python scripts/run_backend.py`
- Generate migration: `alembic revision -m "description"`
- Apply migrations: `alembic upgrade head`
- Generate OpenAPI spec: `python scripts/generate_openapi.py`
