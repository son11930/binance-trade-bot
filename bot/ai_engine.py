import os
import json
import requests
import logging
from google import genai
from google.genai import types
import defusedxml.ElementTree as ET_defused
import concurrent.futures
import html
from dotenv import load_dotenv

from .database import LogRepository, sanitize_text

load_dotenv()

def sanitize_error(error: Exception) -> str:
    return sanitize_text(str(error))

# Initialize client globally to avoid repeated initialization overhead
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Global thread pool for AI tasks to avoid overhead and freezing
ai_executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

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

    bullish_prompt = f"""
    You are the Bullish Analyst for the asset {sanitized_symbol}.
    Your goal is to find momentum and reasons to BUY based on this data:
    
    <news_headlines>
    {sanitized_news}
    </news_headlines>
    {tech_context}
    
    1. Look for volume confirmation and momentum.
    2. Assess multi-timeframe alignment.
    3. Identify Reward-to-Risk (R:R) targets.
    
    Provide a concise analysis focusing ONLY on why this is a strong setup.
    """

    bearish_prompt = f"""
    You are the Bearish Risk Manager for the asset {sanitized_symbol}.
    Your goal is to actively invalidate this trade and find risks:
    
    <news_headlines>
    {sanitized_news}
    </news_headlines>
    {tech_context}
    
    1. Look for fake-outs, bull traps, and stop hunts.
    2. Check for regime conflict (e.g. buying top of range in Sideways).
    3. Check for bearish divergence.
    4. Consider broader market correlation risks.
    
    Provide a concise analysis focusing ONLY on why this trade might fail.
    """

    models_to_try = ['gemini-3.5-flash', 'gemini-2.5-flash', 'gemini-flash-latest']
    
    def _call_model(m_name, p, conf):
        return client.models.generate_content(model=m_name, contents=p, config=conf)
        
    def _get_analysis(prompt_text):
        conf = types.GenerateContentConfig()
        for m in models_to_try:
            try:
                future = ai_executor.submit(_call_model, m, prompt_text, conf)
                res = future.result(timeout=20)
                return res.text
            except concurrent.futures.TimeoutError:
                logging.error(f"AI analysis timeout with {m} (10s)")
                continue
            except Exception as e:
                logging.error(f"AI analysis error with {m}: {sanitize_error(e)}")
                continue
        return "No analysis available."

    try:
        bull_future = ai_executor.submit(_get_analysis, bullish_prompt)
        bear_future = ai_executor.submit(_get_analysis, bearish_prompt)
        
        bull_analysis = bull_future.result()
        bear_analysis = bear_future.result()
    except Exception as e:
        logging.error(f"AI Committee error: {sanitize_error(e)}")
        bull_analysis = "No analysis available."
        bear_analysis = "No analysis available."

    chief_prompt = f"""
    You are the Chief Strategist evaluating a potential trade for {sanitized_symbol}.
    You have received the following reports from your committee:
    
    <bullish_analysis>
    {bull_analysis}
    </bullish_analysis>
    
    <bearish_analysis>
    {bear_analysis}
    </bearish_analysis>
    
    <raw_data>
    {sanitized_news}
    {tech_context}
    </raw_data>
    
    Focus on Expected Value (EV). Do the upside targets outweigh the downside risks?
    Provide an actionable Risk Score. Higher risk = smaller position.
    If you BUY, define strict invalidation levels.
    Determine the ideal position size based on Expected Value and risk. Return an allocation_percentage between 10 and 40. (e.g. highly confident/low risk = 40, moderate = 20, high risk = 10).
    
    Output a strictly valid JSON object with the following schema:
    {{
        "decision": "BUY" or "HOLD",
        "risk_score": integer between 0 and 100,
        "allocation_percentage": integer between 10 and 40,
        "reason": "short explanation based on the debate"
    }}
    """
    
    for model_name in models_to_try:
        try:
            config = types.GenerateContentConfig(response_mime_type="application/json")
            future = ai_executor.submit(_call_model, model_name, chief_prompt, config)
            response = future.result(timeout=25) # 25s timeout for Chief
            
            import json
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            
            result = json.loads(raw_text.strip())
            
            if all(k in result for k in ("decision", "risk_score", "allocation_percentage", "reason")):
                result["committee_debate"] = {
                    "bullish_analysis": bull_analysis,
                    "bearish_analysis": bear_analysis
                }
                return result
            else:
                raise ValueError(f"Malformed schema returned: {result}")
                
        except concurrent.futures.TimeoutError:
            logging.error(f"Chief AI error with {model_name}: TIMEOUT (15s)")
            continue
        except Exception as e:
            logging.error(f"Chief AI error with {model_name}: {sanitize_error(e)}")
            continue

    try:
        LogRepository.log_event("ERROR", "CIRCUIT BREAKER: AI Committee failed or timed out. Defaulting to HOLD.")
    except Exception:
        pass
        
    return {
        "decision": "HOLD", 
        "risk_score": 100, 
        "reason": "Circuit Breaker: Committee failed.",
        "committee_debate": {
            "bullish_analysis": "Error communicating with AI.",
            "bearish_analysis": "Error communicating with AI."
        }
    }
