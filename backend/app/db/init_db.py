from app.db.session import engine
from app.models.models import Base

def init_db():
    Base.metadata.create_all(bind=engine)
    print("All tables created successfully in Neon Postgres.")

if __name__ == "__main__":
    init_db()