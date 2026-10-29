from alembic import context
from backend.db import Base, engine
from backend import models
from backend import opportunity_models
from backend import autonomy_models
from backend import semantic_intent
from backend import learning_models
from backend import communication_models
from backend import location_budget
from backend import absorption_models
from backend import commercial_review_models
from backend import followup_models
from backend import prospecting_models
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=engine.dialect.name == 'sqlite')
    with context.begin_transaction():
        context.run_migrations()
