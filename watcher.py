#!/usr/bin/env python3
"""
Stablecoin Watcher
-------------------
Checks CoinGecko for stablecoins not seen before, scores them on a
risk (safety) and hype (community/sentiment) framework, and sends a
Telegram message for any new coin that clears MIN_RISK_SCORE.
 
State (which coins have already been seen/alerted) is kept in
seen_coins.json so the same coin isn't re-alerted every run.
 
Env vars required:
  TELEGRAM_BOT_TOKEN   - from @BotFather
  TELEGRAM_CHAT_ID     - your chat id (see setup guide)
Optional:
  MIN_RISK_SCORE        - float 0-10, default 5.0. Only coins scoring
                           at/above this get a Telegram alert.
  ALWAYS_ALERT_NEW_COINS - "true"/"false", default "false". If true,
                           every newly-seen coin gets a message
                           regardless of score (useful at first to
                           sanity check the pipeline).
"""
 
import json
import os
import sys
import time
import urllib.request
import urllib.parse
 
COINGECKO_MARKETS_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&category=stablecoins&order=market_cap_desc"
    "&per_page=250&page=1&sparkline=false"
)
COINGECKO_DETAIL_URL = "https://api.coingecko.com/api/v3/coins/{id}"
SEEN_FILE = os.path.join(os.path.dirname(__file__), "seen_coins.json")
 
MIN_RISK_SCORE = float(os.environ.get("MIN_RISK_SCORE", "5.0"))
ALWAYS_ALERT_NEW = os.environ.get("ALWAYS_ALERT_NEW_COINS", "false").lower() == "true"
 
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
 
 
def http_get_json(url, retries=3):
    req = urllib.request.Request(url, headers={"User-Agent": "stablecoin-watcher/1.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt == retries - 1:
                print(f"[warn] request failed after {retries} tries: {url} ({e})", file=sys.stderr)
                return None
            time.sleep(3)
    return None
 
 
def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return json.load(f)
    return {}
 
 
def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f, indent=2, sort_keys=True)
 
 
def score_risk(coin, detail):
    """0-10 scale, higher = safer. Uses free, publicly available data."""
    mcap = coin.get("market_cap") or 0
    vol = coin.get("total_volume") or 0
    price = coin.get("current_price") or 0
 
    # Market cap tier
    if mcap >= 100_000_000:
        mcap_score = 10
    elif mcap >= 20_000_000:
        mcap_score = 7
    elif mcap >= 5_000_000:
        mcap_score = 4
    else:
        mcap_score = 1
 
    # Liquidity depth relative to size (volume/mcap ratio)
    ratio = (vol / mcap) if mcap else 0
    if ratio >= 0.10:
        liq_score = 10
    elif ratio >= 0.03:
        liq_score = 6
    else:
        liq_score = 2
 
    # Peg deviation from $1.00 (current snapshot, not full history —
    # this script can't backtest years of price history on a free tier,
    # so treat this as a live-peg check, not a historical guarantee)
    dev = abs(price - 1.0) if price else 1.0
    if dev <= 0.005:
        peg_score = 10
    elif dev <= 0.02:
        peg_score = 6
    elif dev <= 0.05:
        peg_score = 3
    else:
        peg_score = 0
 
    return round((mcap_score + liq_score + peg_score) / 3, 1)
 
 
def score_hype(detail):
    """0-10 scale using CoinGecko community/sentiment fields when available."""
    if not detail:
        return 0.0
    community = (detail.get("community_score") or 0)  # roughly 0-100
    sentiment_up = (detail.get("sentiment_votes_up_percentage") or 0)  # 0-100
    community_scaled = min(community / 10, 10)
    sentiment_scaled = sentiment_up / 10
    return round((community_scaled + sentiment_scaled) / 2, 1)
 
 
def tier_label(score, kind):
    if kind == "risk":
        return "Low risk" if score >= 7.5 else "Medium risk" if score >= 5 else "High risk"
    return "High hype" if score >= 7.5 else "Moderate hype" if score >= 5 else "Low hype"
 
 
def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[error] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — skipping send.", file=sys.stderr)
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[error] telegram send failed: {e}", file=sys.stderr)
        return False
 
 
def main():
    markets = http_get_json(COINGECKO_MARKETS_URL)
    if not markets:
        print("[error] could not fetch stablecoin market data, aborting run.")
        sys.exit(1)
 
    seen = load_seen()
    new_alerts = 0
 
    for coin in markets:
        coin_id = coin.get("id")
        if not coin_id or coin_id in seen:
            continue
 
        detail = http_get_json(COINGECKO_DETAIL_URL.format(id=coin_id))
        time.sleep(1.5)  # be polite to the free API rate limit
 
        risk = score_risk(coin, detail)
        hype = score_hype(detail)
        seen[coin_id] = {
            "name": coin.get("name"),
            "risk": risk,
            "hype": hype,
            "first_seen": time.strftime("%Y-%m-%d"),
        }
 
        should_alert = ALWAYS_ALERT_NEW or risk >= MIN_RISK_SCORE
        if should_alert:
            msg = (
                f"🪙 *New stablecoin detected: {coin.get('name')} ({coin.get('symbol','').upper()})*\n\n"
                f"Safety score: *{risk}/10* ({tier_label(risk,'risk')})\n"
                f"Hype score: *{hype}/10* ({tier_label(hype,'hype')})\n"
                f"Market cap: ${mcap_fmt(coin.get('market_cap'))}\n"
                f"24h volume: ${mcap_fmt(coin.get('total_volume'))}\n"
                f"Current price: ${coin.get('current_price')}\n\n"
                f"_Not financial advice — verify reserve attestations directly before acting._"
            )
            if send_telegram(msg):
                new_alerts += 1
                print(f"[info] alerted on {coin_id} (risk={risk}, hype={hype})")
 
    save_seen(seen)
    print(f"[info] run complete. {new_alerts} new alert(s) sent. {len(seen)} coins tracked total.")
 
 
def mcap_fmt(n):
    if not n:
        return "0"
    return f"{n:,.0f}"
 
 
if __name__ == "__main__":
    main()
