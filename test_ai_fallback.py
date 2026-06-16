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
            if model == "gemini-3.1-flash-lite":
                raise Exception("429 RESOURCE_EXHAUSTED Quota Exceeded")
            elif model == "gemini-2.5-flash":
                class MockResponse:
                    text = '{"decision": "BUY", "risk_score": 25, "allocation_percentage": 20, "reason": "Good news", "bullish_analysis": "Bullish case", "bearish_analysis": "Bearish case"}'
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
print("Expecting 3.1-flash-lite to fail, and 2.5-flash to succeed.")

result = ai_engine.analyze_sentiment("Bitcoin hits 100k", "BTCUSDT")
print(f"Result: {result}")

if result.get("decision") == "BUY" and "committee_debate" in result:
    print("[PASS] Fallback Test Passed!")
else:
    print("[FAIL] Fallback Test Failed!")

# Check logs
print("Checking System Logs...")
logs = db.LogRepository.get_latest_logs(10)
for log in logs:
    if "gemini-3.1-flash-lite" in log['message'] and "Rate limited" in log['message']:
        print(f"[PASS] Found warning log: {log['message']}")
