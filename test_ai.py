import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
print(f"API Key loaded: {api_key[:5] if api_key else None}...")

try:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model='gemini-1.5-flash',
        contents='Explain quantum mechanics in 10 words.',
        config=types.GenerateContentConfig()
    )
    print("Success:", response.text)
except Exception as e:
    import traceback
    traceback.print_exc()
