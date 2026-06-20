import os
import json
import requests
import logging
import time
import threading
from google import genai
from google.genai import types
import defusedxml.ElementTree as ET_defused
import html
from dotenv import load_dotenv

from .database import LogRepository, sanitize_text

load_dotenv()

def sanitize_error(error: Exception) -> str:
    return sanitize_text(str(error))

# Initialize client globally to avoid repeated initialization overhead
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Global lock to enforce 4-second delay (15 RPM limit)
GLOBAL_API_LOCK = threading.Lock()
LAST_API_CALL = 0

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
        
        root = ET_defused.fromstring(response.content)
            
        headlines = []
        for item in root.findall('./channel/item')[:limit]:
            title_node = item.find('title')
            title = title_node.text if title_node is not None else "No Title"
            desc_node = item.find('description')
            desc = desc_node.text if desc_node is not None else "No Description"
            
            clean_desc = html.unescape(desc).replace('<p>', '').replace('</p>', '').replace('\n', ' ').strip()
            # Truncate aggressively to save context window tokens
            summary = clean_desc[:250] + "..." if len(clean_desc) > 250 else clean_desc
            headlines.append(f"{title}: {summary}")
        return "\n".join(headlines)
    except Exception as e:
        logging.exception(f"Error fetching news from CoinTelegraph: {e}")
        return "No recent news available due to error."

def analyze_sentiment(news_text: str, symbol: str, tech_data: dict = None) -> dict:
    """
    Uses an AI Committee (Bullish, Bearish, Chief Strategist) to evaluate a trade.
    """
    if not news_text or news_text.startswith("No recent news"):
        return {"decision": "HOLD", "risk_score": 50, "reason": "No news available for analysis."}
        
    sanitized_news = html.escape(news_text)
    sanitized_symbol = html.escape(symbol)
    
    tech_context = ""
    if tech_data:
        vol_surge_fmt = f"{tech_data.get('vol_surge_multiplier', 1.0):.1f}x Normal Volume"
        tech_context = f"""
    <technical_context>
    Current Strategy: {tech_data.get('strategy_used', 'UNKNOWN')}
    ADX: {tech_data.get('adx', 'N/A')}
    RSI: {tech_data.get('rsi', 'N/A')}
    MACD_Histogram: {tech_data.get('macd_histogram', 'N/A')}
    ATR: {tech_data.get('atr', 'N/A')}
    Bollinger_Band_Width: {tech_data.get('bb_width', 'N/A')}
    Distance_to_SMA_200 (%): {tech_data.get('dist_sma_200', 'N/A')}
    Volume_Surge_Multiplier: {vol_surge_fmt}
    </technical_context>
        """

    chief_prompt = f"""
    You are the Chief Crypto Strategist evaluating a potential trade for {sanitized_symbol}.
    Your goal is to conduct an internal debate (Bullish vs Bearish) and then provide a final actionable decision based on Expected Value (EV).
    
    <raw_data>
    News:
    {sanitized_news}
    
    {tech_context}
    </raw_data>
    
    Step 1. Conduct a Bullish Analysis: Find momentum, volume confirmation, and reasons to BUY.
    Step 2. Conduct a Bearish Analysis: Actively invalidate the trade. Look for fake-outs, bull traps, divergence, and regime conflicts.
    Step 3. Weigh the Expected Value. Do the upside targets outweigh the downside risks?
    Step 4. Determine an actionable Risk Score. Higher risk = smaller position.
    Step 5. If BUY, determine the allocation_percentage between 10 and 40 (e.g. highly confident/low risk = 40, moderate = 20, high risk = 10).
    
    Output a strictly valid JSON object with the following schema:
    {{
        "bullish_analysis": "short bullish case",
        "bearish_analysis": "short bearish case",
        "decision": "BUY" or "HOLD",
        "risk_score": integer between 0 and 100,
        "allocation_percentage": integer between 10 and 40,
        "reason": "short explanation for the final decision"
    }}
    """

    models_to_try = ['gemini-3.1-flash-lite', 'gemini-3.5-flash', 'gemini-2.5-flash']
    
    def _call_model(m_name, p, conf):
        global LAST_API_CALL
        with GLOBAL_API_LOCK:
            now = time.time()
            elapsed = now - LAST_API_CALL
            if elapsed < 4.0:
                time.sleep(4.0 - elapsed)
            LAST_API_CALL = time.time()
            
        return client.models.generate_content(model=m_name, contents=p, config=conf)
    
    last_error = "Unknown Error"
    for model_name in models_to_try:
        for attempt in range(2):
            try:
                config = types.GenerateContentConfig(response_mime_type="application/json")
                response = _call_model(model_name, chief_prompt, config)
                
                import json
                raw_text = response.text.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                elif raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                
                result = json.loads(raw_text.strip())
                
                if all(k in result for k in ("decision", "risk_score", "allocation_percentage", "reason", "bullish_analysis", "bearish_analysis")):
                    # Reformat to match what main.py expects and escape to prevent XSS
                    bull = html.escape(str(result.pop("bullish_analysis")))
                    bear = html.escape(str(result.pop("bearish_analysis")))
                    result["reason"] = html.escape(str(result.get("reason", "")))
                    result["committee_debate"] = {
                        "bullish_analysis": bull,
                        "bearish_analysis": bear
                    }
                    result["model_used"] = model_name
                    result["is_error"] = False
                    return result
                else:
                    raise ValueError(f"Malformed schema returned: {result}")
                    
            except Exception as e:
                err_str = str(e)
                last_error = err_str
                if "429" in err_str or "quota" in err_str.lower() or "too many" in err_str.lower():
                    logging.warning(f"Rate limited on {model_name}, attempt {attempt+1}. Sleeping 5s...")
                    time.sleep(5)
                    continue
                logging.error(f"AI error with {model_name}: {sanitize_error(e)}")
                break

    try:
        LogRepository.log_event("ERROR", f"CIRCUIT BREAKER: AI Committee failed. Details: {sanitize_text(last_error)[:100]}...")
    except Exception:
        pass
        
    return {
        "decision": "HOLD", 
        "risk_score": 100, 
        "reason": f"API Error: {sanitize_error(Exception(last_error))}",
        "committee_debate": {
            "bullish_analysis": "Error communicating with AI.",
            "bearish_analysis": "Error communicating with AI."
        },
        "model_used": "NONE",
        "is_error": True
    }
