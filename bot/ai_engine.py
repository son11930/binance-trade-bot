import os
import json
import requests
import logging
import xml.etree.ElementTree as ET
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if api_key and api_key != "your_gemini_api_key_here":
    genai.configure(api_key=api_key)

def fetch_crypto_news(limit: int = 5) -> str:
    """
    Fetches the latest crypto news headlines from CoinTelegraph RSS.
    """
    try:
        url = "https://cointelegraph.com/rss"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        headlines = []
        for item in root.findall('./channel/item')[:limit]:
            title = item.find('title').text
            headlines.append(title)
        return "\n".join(headlines)
    except Exception as e:
        logging.exception("Error fetching news from CoinTelegraph")
        return "No recent news available due to error."

def analyze_sentiment(news_text: str) -> dict:
    """
    Uses Gemini 3.5 Flash to analyze news sentiment and return a Risk Score.
    """
    if not news_text or news_text.startswith("No recent news"):
        return {"decision": "HOLD", "risk_score": 50, "reason": "No news available for analysis."}
        
    # Initialize the model with JSON response type
    model = genai.GenerativeModel(
        model_name="gemini-3.5-flash",
        generation_config={"response_mime_type": "application/json"}
    )
    
    prompt = f"""
    You are an expert cryptocurrency trading AI. Analyze the following recent news headlines:
    
    {news_text}
    
    Based on these headlines, evaluate the risk of buying Bitcoin right now.
    Consider major hacks, regulatory crackdowns, or macroeconomic crashes as high risk (>40).
    General positive or neutral news should be low risk (<40).
    
    Output a strictly valid JSON object with the following schema:
    {{
        "decision": "BUY" or "HOLD",
        "risk_score": integer between 0 and 100,
        "reason": "short explanation of the sentiment"
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        result = json.loads(response.text)
        return result
    except Exception as e:
        logging.exception("AI Analysis error")
        return {"decision": "HOLD", "risk_score": 100, "reason": "Error during AI analysis."}
