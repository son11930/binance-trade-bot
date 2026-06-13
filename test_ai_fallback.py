import os
from dotenv import load_dotenv

# Set mock environment BEFORE importing modules
os.environ["GEMINI_API_KEY"] = "mock_key_for_testing"

# Mock the genai client
import google.genai as genai
from google.genai import types

class MockClient:
    class Models:
        def generate_content(self, model, contents, config):
            if model == "gemini-3.5-flash":
                raise Exception("429 RESOURCE_EXHAUSTED Quota Exceeded")
            elif model == "gemini-3.1-flash-lite":
                class MockResponse:
                    text = '{"decision": "BUY", "risk_score": 25, "reason": "Good news"}'
                return MockResponse()
            else:
                raise Exception("Unknown model")
                
    def __init__(self, api_key):
        self.models = self.Models()

genai.Client = MockClient

import bot.ai_engine as ai_engine
import bot.database as db

# Setup test DB
db.init_db()

print("Testing AI Fallback Logic...")
print("Expecting 3.5 to fail, and 3.1 to succeed.")

result = ai_engine.analyze_sentiment("Bitcoin hits 100k", "BTCUSDT")
print(f"Result: {result}")

if result.get("decision") == "BUY":
    print("✅ Fallback Test Passed!")
else:
    print("❌ Fallback Test Failed!")

# Check logs
print("Checking System Logs...")
logs = db.LogRepository.get_latest_logs(10)
for log in logs:
    if "gemini-3.5-flash failed" in log['message']:
        print(f"✅ Found warning log: {log['message']}")
