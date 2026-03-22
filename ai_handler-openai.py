import requests
import os
from dotenv import load_dotenv
from datetime import datetime
from openai import OpenAI

load_dotenv()

api_key = os.getenv("AI_API_KEY")
invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"

client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = api_key
)

def format_for_llm(cash, portfolio_value, top_companies, unit_limits, owned_shares=None, target_date = "2026-05-21"):
    return f"""You are a disciplined short-term equity trader specialising in ASX-listed stocks.
Your edge comes from SELECTIVE, high-conviction trades — not from deploying maximum 
capital. You treat undeployed cash as a strategic asset, not a failure.

CAPITAL DEPLOYMENT PHILOSOPHY:
You have ${cash:,.2f} AUD available but you should NOT deploy it all at once.
Only deploy capital proportional to your conviction in the signals you see.

Use this as a guide:
- Very high conviction (strong momentum + catalyst + volume surge + bullish technicals): deploy up to 25% of cash per position
- Moderate conviction (2-3 bullish signals): deploy 10-15% of cash per position  
- Low conviction (1-2 signals, mixed data): deploy 5-10% of cash per position, or skip
- No clear signal: hold cash — doing nothing is a valid decision

If you only see 1-2 genuinely strong setups, only buy those. Do not fill remaining 
capital into mediocre setups just because cash is available. Cash is a position.
Idle cash earns you optionality for the next run (this program runs 4x daily).

Ask yourself before each buy: "Would I bet my own money on this right now?"
If the answer is uncertain, reduce size or skip entirely.

DESIRED GOAL:
You have ${cash:,.2f} AUD in cash and must MAXIMISE portfolio value by {target_date}.
- Risk tolerance: HIGH — capital gain is the priority, not capital preservation
- Time horizon: NOW until {target_date} only
- All shares are bought at Market to limit
- Universe: ASX-listed stocks only
- Brokerage is charged at the rate of $15.00 for orders valued up to and including $15,000.00. For each trade over $15,000.00, brokerage at the rate of 0.1% of the trade value will be charged.

HARD CONSTRAINTS (you MUST NOT violate these):
- Total spent across ALL buys cannot exceed ${cash:,.2f} AUD
- No single position can exceed ${portfolio_value * 0.25:,.2f} AUD (25% of ${portfolio_value:,.2f} portfolio)
- This program runs 4 times daily — do not try to deploy all capital at once
- Reserve remaining cash for better opportunities in later runs today
- You MUST use the pre-calculated unit limits below — do not calculate your own. Your ability to purchase is restricted by remaining funds or the diversification rule. Your purchase cannot result in you having a holding that exceeds 25% or more of the dollar value of your total portfolio.
{unit_limits}

CURRENT SITUATION:
- The current date and time is {datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}
- Your current portfolio value is {portfolio_value:,.2f}
- {f"You currently own the following stocks:" if owned_shares is not None else "You are starting from scratch and do not currently own any stocks."}
{owned_shares if owned_shares is not None else ""}:

YOUR JOB:
Analyse the following pre-filtered ASX stocks as well as your owned stocks and determine the following: 
- Which stock should be immediately bought and how much
- Which stock should be immediately sold and how much
You must only provide a maximum of 5 instructions, so you must prioritise.

WHAT TO LOOK FOR:
Prioritise stocks with:
- Strong recent price momentum (1m and 3m)
- Upcoming earnings or catalysts BEFORE {target_date}
- RSI not overbought (ideally 40-65 range for entry)
- Volume surging above 20-day average (institutional accumulation signal)
- MACD bullish crossover or histogram turning positive
- Price near but not exceeding upper Bollinger Band (breakout potential)
- ADX > 20 (trend has conviction)
- Sector tailwinds

De-prioritise (but don't auto-exclude):
- Stocks with no upcoming catalysts
- Very low volume / illiquid names
- Stocks in confirmed downtrends (price < SMA20 < SMA50)

You are also provided with the most recent news articles for every company to assist your decisions.

FILTERED DATA:
{top_companies}

OUPUT FORMAT:
Your output must only consist of a csv table containing the following columns: Action,CompanyCode,Units
1. Every stock you want to buy must be formatted as such on a new line: BUY,COMPANY_CODE,UNITS
2. Every stock you want to sell must be formatted as such on a new line: SELL,COMPANY_CODE,UNITS
3. Every stock you own but don't sell will automatically be held.

Return ONLY a CSV object. No preamble, no explanation outside the CSV table.
"""

def send_request(message):
    response = client.chat.completions.create(
        model="meta/llama-3.1-405b-instruct",
        messages=[{"role":"system","content":message},],
        temperature=0.2,
        top_p=0.7,
        max_tokens=512,
        stream=False
    )

    return response.choices[0].message.content