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

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GLOBAL_API_LOCK = threading.Lock()
LAST_API_CALL = 0

GROQ_API_LOCK = threading.Lock()
LAST_GROQ_CALL = 0

def _call_model(m_name, p, conf=None, is_json=True):
    if m_name.startswith("groq-"):
        global LAST_GROQ_CALL
        with GROQ_API_LOCK:
            now = time.time()
            elapsed = now - LAST_GROQ_CALL
            if elapsed < 2.0: # 30 RPM
                time.sleep(2.0 - elapsed)
            LAST_GROQ_CALL = time.time()
        
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            raise ValueError("GROQ_API_KEY is not set in .env")
            
        model_id = m_name[5:]
        if model_id == "qwen-32b-preview" or model_id == "qwen-2.5-32b":
            model_id = "qwen-2.5-32b" # standard groq model id
            
        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": p}]
        }
        if is_json:
            payload["response_format"] = {"type": "json_object"}
            
        resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        
        class DummyResponse:
            pass
        dummy = DummyResponse()
        dummy.text = resp.json()["choices"][0]["message"]["content"]
        return dummy
    else:
        global LAST_API_CALL
        with GLOBAL_API_LOCK:
            now = time.time()
            elapsed = now - LAST_API_CALL
            if elapsed < 4.0:
                time.sleep(4.0 - elapsed)
            LAST_API_CALL = time.time()
            
        if not conf:
            if is_json:
                conf = types.GenerateContentConfig(response_mime_type="application/json")
        return client.models.generate_content(model=m_name, contents=p, config=conf)

def filter_crypto_news(news_list: list) -> str:
    """
    Layer 2: Assign Impact Score and pick top 3
    """
    if not news_list:
        return "No recent news."
        
    prompt = "You are a crypto news screener. Rate each news item's impact on the market from 1-100.\n"
    for i, n in enumerate(news_list):
        prompt += f"Item {i}: {n}\n"
    prompt += "\nReturn a JSON object with a list 'scored_news' containing objects with 'index' and 'score'. Example: {\"scored_news\":[{\"index\":0,\"score\":85}]}"
    
    models = ['groq-llama-3.1-8b-instant', 'gemini-1.5-flash', 'groq-qwen-2.5-32b']
    for m in models:
        try:
            resp = _call_model(m, prompt, is_json=True)
            data = json.loads(resp.text)
            scores = data.get("scored_news", [])
            # Sort by score desc
            scores.sort(key=lambda x: x.get("score", 0), reverse=True)
            top_indices = [x["index"] for x in scores[:3]]
            top_news = [news_list[i] for i in top_indices if i < len(news_list)]
            return "\n".join(top_news)
        except Exception as e:
            continue
            
    return "\n".join(news_list[:3]) # Fallback to top 3 chronological

def fetch_crypto_news(limit: int = 5) -> str:
    """
    Fetches the latest crypto news headlines from multiple sources and applies Layer 2 filtering.
    """
    try:
        news_items = []
        # Source 1: CoinTelegraph
        url1 = "https://cointelegraph.com/rss"
        headers = {"User-Agent": "Mozilla/5.0"}
        r1 = requests.get(url1, headers=headers, timeout=10)
        if r1.status_code == 200:
            root = ET_defused.fromstring(r1.content)
            for item in root.findall('./channel/item')[:limit]:
                title = item.find('title').text if item.find('title') is not None else ""
                desc = item.find('description').text if item.find('description') is not None else ""
                clean_desc = html.unescape(desc).replace('<p>', '').replace('</p>', '').replace('\n', ' ').strip()
                summary = clean_desc[:250] + "..." if len(clean_desc) > 250 else clean_desc
                news_items.append(f"CoinTelegraph: {title} - {summary}")
                
        # Future: Add more sources here (CryptoPanic, Twitter)
        
        return filter_crypto_news(news_items)
    except Exception as e:
        logging.exception(f"Error fetching news: {e}")
        return "No recent news available due to error."

def analyze_sentiment(news_text: str, symbol: str, tech_data: dict = None, market_type: str = 'spot') -> dict:
    if not news_text or news_text.startswith("No recent news"):
        return {"decision": "HOLD", "risk_score": 50, "reason": "No news available for analysis.", "model_used": "NONE", "is_error": False, "committee_debate": {"bullish_analysis": "", "bearish_analysis": ""}}
        
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
    Funding_Rate: {tech_data.get('funding_rate', 'N/A')}
    Long_Short_Ratio: {tech_data.get('long_short_ratio', 'N/A')}
    Fear_Greed_Index: {tech_data.get('fear_greed_index', 'N/A')}
    </technical_context>
        """

    decision_options = '"BUY" or "HOLD" or "SELL"' if market_type == 'spot' else '"LONG" or "SHORT" or "HOLD"'

    chief_prompt = f"""
    You are the Chief Quantitative Strategist evaluating a potential trade for {sanitized_symbol} on {market_type.upper()}.
    Your goal is to conduct an internal debate and then provide a final actionable decision based on Expected Value (EV).
    Look for contrarian signals (e.g. Extreme Greed + High Positive Funding Rate = Risk of Long Squeeze).
    
    <raw_data>
    News:
    {sanitized_news}
    
    {tech_context}
    </raw_data>
    
    Step 1. Conduct a Bullish Analysis: Find momentum, volume confirmation, and reasons to go LONG/BUY.
    Step 2. Conduct a Bearish Analysis: Actively invalidate the trade. Look for fake-outs, bull traps, divergence, and reasons to go SHORT/SELL.
    Step 3. Weigh the Expected Value.
    Step 4. Determine an actionable Risk Score. Higher risk = smaller position.
    Step 5. If acting, determine the allocation_percentage between 10 and 40.
    
    Output a strictly valid JSON object with the following schema:
    {{
        "bullish_analysis": "short bullish case",
        "bearish_analysis": "short bearish case",
        "decision": {decision_options},
        "risk_score": integer between 0 and 100,
        "allocation_percentage": integer between 10 and 40,
        "reason": "short explanation for the final decision"
    }}
    """

    models_to_try = [
        'groq-llama-3.3-70b-versatile',
        'gemini-1.5-flash',
        'groq-qwen-2.5-32b',
        'groq-llama-3.1-8b-instant'
    ]
    
    last_error = "Unknown Error"
    for model_name in models_to_try:
        for attempt in range(2):
            try:
                response = _call_model(model_name, chief_prompt, is_json=True)
                
                raw_text = response.text.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                elif raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                
                result = json.loads(raw_text.strip())
                
                if all(k in result for k in ("decision", "risk_score", "allocation_percentage", "reason", "bullish_analysis", "bearish_analysis")):
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
