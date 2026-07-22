# Import all models here so that Base.metadata.create_all() and Alembic
# migrations can discover every table. Add new model imports as you add models.

from app.db.database import Base  # noqa
from app.models.user import User  # noqa
