# Database Management

## Migration Commands

```bash
# Run migrations to upgrade database
env/bin/alembic upgrade head

# Create new migration
env/bin/alembic revision --autogenerate -m "Description of changes"

# Show current migration status
env/bin/alembic current

# Show migration history
env/bin/alembic history

# Downgrade to specific revision
env/bin/alembic downgrade <revision_id>
```
