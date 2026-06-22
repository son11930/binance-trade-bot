import requests
import json
from .logger import log_msg
import html
import defusedxml.ElementTree as ET_defused
from .ai_engine import _call_model

def filter_crypto_news(news_list: list) -> str:
    if not news_list:
        return "No recent news."
        
    prompt = "You are a crypto news screener. Rate each news item's impact on the market from 1-100.\n"
    for i, n in enumerate(news_list):
        prompt += f"Item {i}: {n}\n"
    prompt += "\nReturn a JSON object with a list 'scored_news' containing objects with 'index' and 'score'. Example: {\"scored_news\":[{\"index\":0,\"score\":85}]}"
    
    models = ['groq-llama-3.1-8b-instant', 'gemini-1.5-flash', 'groq-mixtral-8x7b-32768']
    for m in models:
        try:
            resp = _call_model(m, prompt, is_json=True)
            data = json.loads(resp.text)
            scores = data.get("scored_news", [])
            scores.sort(key=lambda x: x.get("score", 0), reverse=True)
            top_indices = [x["index"] for x in scores[:3]]
            top_news = [news_list[i] for i in top_indices if i < len(news_list)]
            return "\n".join(top_news) if top_news else "\n".join(news_list[:3])
        except Exception as e:
            log_msg("ERROR", f"filter_crypto_news model {m} failed: {e}")
            continue
    return "\n".join(news_list[:3])

def fetch_crypto_news(limit: int = 5) -> str:
    try:
        news_items = []
        headers = {"User-Agent": "Mozilla/5.0"}
        
        # Source 1: CoinTelegraph
        try:
            r1 = requests.get("https://cointelegraph.com/rss", headers=headers, timeout=10)
            if r1.status_code == 200:
                root = ET_defused.fromstring(r1.content)
                for item in root.findall('./channel/item')[:limit]:
                    title = item.find('title').text if item.find('title') is not None else ""
                    desc = item.find('description').text if item.find('description') is not None else ""
                    clean_desc = html.unescape(desc).replace('<p>', '').replace('</p>', '').replace('\n', ' ').strip()
                    summary = clean_desc[:250] + "..." if len(clean_desc) > 250 else clean_desc
                    news_items.append(f"CoinTelegraph: {title} - {summary}")
        except Exception:
            pass
                
        # Source 2: CoinDesk
        try:
            r2 = requests.get("https://www.coindesk.com/arc/outboundfeeds/rss/", headers=headers, timeout=10)
            if r2.status_code == 200:
                root2 = ET_defused.fromstring(r2.content)
                for item in root2.findall('./channel/item')[:limit]:
                    title = item.find('title').text if item.find('title') is not None else ""
                    news_items.append(f"CoinDesk: {title}")
        except Exception:
            pass

        # Source 3: CryptoSlate
        try:
            r3 = requests.get("https://cryptoslate.com/feed/", headers=headers, timeout=10)
            if r3.status_code == 200:
                root3 = ET_defused.fromstring(r3.content)
                for item in root3.findall('./channel/item')[:limit]:
                    title = item.find('title').text if item.find('title') is not None else ""
                    news_items.append(f"CryptoSlate: {title}")
        except Exception:
            pass
        
        return filter_crypto_news(news_items)
    except Exception as e:
        log_msg("ERROR", f"Error fetching news: {e}")
        return "No recent news available due to error."
