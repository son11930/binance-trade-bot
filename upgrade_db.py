import os
import sqlalchemy
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL_SPOT = os.getenv("DATABASE_URL_SPOT", "sqlite:///./trades_spot.db")
DATABASE_URL_FUTURES = os.getenv("DATABASE_URL_FUTURES", "sqlite:///./trades_futures.db")

def upgrade_db(url):
    print(f"Connecting to {url}...")
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            # Add position_side to trades
            try:
                conn.execute(text("ALTER TABLE trades ADD COLUMN position_side VARCHAR"))
                print(" -> Added 'position_side' to trades")
            except Exception as e:
                if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower() or 'operationalerror' in str(e).lower():
                    print(" -> 'position_side' already exists or error ignored.")
                else:
                    print(f" -> Error adding 'position_side': {e}")
            
            # Add market_type to trades
            try:
                conn.execute(text("ALTER TABLE trades ADD COLUMN market_type VARCHAR DEFAULT 'spot'"))
                # For sqlite, adding column with default sets it for existing rows
                # For postgres, adding column with default sets it for existing rows
                print(" -> Added 'market_type' to trades")
            except Exception as e:
                if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower() or 'operationalerror' in str(e).lower():
                    print(" -> 'market_type' already exists in trades or error ignored.")
                else:
                    print(f" -> Error adding 'market_type' to trades: {e}")

            # Add market_type to system_logs
            try:
                conn.execute(text("ALTER TABLE system_logs ADD COLUMN market_type VARCHAR DEFAULT 'spot'"))
                print(" -> Added 'market_type' to system_logs")
            except Exception as e:
                if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower() or 'operationalerror' in str(e).lower():
                    print(" -> 'market_type' already exists in system_logs or error ignored.")
                else:
                    print(f" -> Error adding 'market_type' to system_logs: {e}")
            
            try:
                conn.commit()
            except:
                pass
    except Exception as e:
        print(f"Failed to connect or upgrade {url}: {e}")

print("==============================")
print("Upgrading Spot DB...")
upgrade_db(DATABASE_URL_SPOT)
print("==============================")
print("Upgrading Futures DB...")
upgrade_db(DATABASE_URL_FUTURES)
print("==============================")
print("Upgrade complete.")
