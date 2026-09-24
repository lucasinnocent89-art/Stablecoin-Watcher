Stablecoin Watcher

Automatically checks for new stablecoins every 6 hours and messages you on Telegram when one scores well on safety (reserves, liquidity, peg stability) using free CoinGecko data. Runs entirely on GitHub's free Actions tier — nothing needs to stay on at your end.

Setup (10 minutes, one time)
Create a Telegram bot
Open Telegram, message @BotFather, send /newbot, follow the prompts.
It gives you a token like 123456789:AAExampleToken — save it.
Get your chat ID
Message your new bot anything (e.g. "hi").
Visit https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates in a browser.
Find "chat":{"id":XXXXXXXXX,...} — that number is your chat ID.
Create a GitHub repo
Go to github.com → New repository → name it (e.g. stablecoin-watcher) → Create.
Upload all the files from this folder (drag-and-drop works on the repo's web page, or git push if you're comfortable with git).
Add your secrets
In the repo: Settings → Secrets and variables → Actions → New repository secret.
Add TELEGRAM_BOT_TOKEN = your bot token.
Add TELEGRAM_CHAT_ID = your chat ID.
Turn it on
Go to the Actions tab → you'll see "Stablecoin Watcher" → click "Run workflow" once to test it manually.
Check Telegram — you should get a message if any coin clears the threshold (or nothing, if none currently do — that's normal).
After that it runs automatically every 6 hours.
Tuning it
MIN_RISK_SCORE in .github/workflows/watch.yml (default 5.0 out of 10) — raise it to only hear about safer coins, lower it to catch more/earlier.
ALWAYS_ALERT_NEW_COINS: "true" — set this temporarily to confirm the whole pipeline works end-to-end (you'll get a message for every new coin found, regardless of score).
Cron schedule (0 */6 * * *) — change to run more/less often.
Honest limitations
Free CoinGecko API data only — no proprietary "years of backtesting." Peg-stability scoring is a live snapshot, not full historical depeg data.
Hype scoring uses CoinGecko's community/sentiment fields, which are thinner than paid tools like LunarCrush or Santiment. Good enough as a first filter, not a substitute for reading the coin's actual docs.
This flags candidates worth looking into — it is not investment advice and a high score is not a guarantee the coin is safe or a good buy.
