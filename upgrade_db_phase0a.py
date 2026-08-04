import os
import sqlalchemy
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL_SPOT = os.getenv("DATABASE_URL_SPOT", "sqlite:///./trades_spot.db")
DATABASE_URL_FUTURES = os.getenv("DATABASE_URL_FUTURES", "sqlite:///./trades_futures.db")

def upgrade_db_phase0a(url):
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    print(f"Connecting to {url}...")
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            # Add execution_mode
            try:
                conn.execute(text("ALTER TABLE trades ADD COLUMN execution_mode VARCHAR"))
                print(" -> Added 'execution_mode' to trades")
            except Exception as e:
                if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower() or 'operationalerror' in str(e).lower():
                    print(" -> 'execution_mode' already exists or error ignored.")
                else:
                    print(f" -> Error adding 'execution_mode': {e}")
            
            # Add deployment_id
            try:
                conn.execute(text("ALTER TABLE trades ADD COLUMN deployment_id VARCHAR"))
                print(" -> Added 'deployment_id' to trades")
            except Exception as e:
                if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower() or 'operationalerror' in str(e).lower():
                    print(" -> 'deployment_id' already exists in trades or error ignored.")
                else:
                    print(f" -> Error adding 'deployment_id' to trades: {e}")

            # Add strategy_id
            try:
                conn.execute(text("ALTER TABLE trades ADD COLUMN strategy_id VARCHAR"))
                print(" -> Added 'strategy_id' to trades")
            except Exception as e:
                if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower() or 'operationalerror' in str(e).lower():
                    print(" -> 'strategy_id' already exists in trades or error ignored.")
                else:
                    print(f" -> Error adding 'strategy_id' to trades: {e}")
            
            try:
                conn.commit()
            except:
                pass
    except Exception as e:
        print(f"Failed to connect or upgrade {url}: {e}")

if __name__ == "__main__":
    print("==============================")
    print("Phase 0A DB Upgrade: Spot DB...")
    upgrade_db_phase0a(DATABASE_URL_SPOT)
    print("==============================")
    print("Phase 0A DB Upgrade: Futures DB...")
    upgrade_db_phase0a(DATABASE_URL_FUTURES)
    print("==============================")
    print("Phase 0A Upgrade complete.")
