import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

try:
    response = client.models.generate_content(
        model='gemini-3.5-flash',
        contents='Output JSON {"status": "ok"}',
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    print("Success:", response.text)
except Exception as e:
    import traceback
    traceback.print_exc()
