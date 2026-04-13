from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime
import time
import os

load_dotenv()

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("AI_API_KEY")
)

SYSTEM_PROMPT = """You are a disciplined ASX equity trader. Your performance is judged 
not by how much capital you deploy, but by your win rate and return on invested capital.
A trader who makes 3 well-sized winning trades beats one who makes 15 mediocre ones.
Undeployed cash is not failure — it is discipline."""

def analyse_stocks(top_companies, cash, portfolio_value, owned_shares, target_date):
    
    # give a cash status warning
    if cash <= 0:
        cash_status = "WARNING: You have NO cash available. You may ONLY sell positions — do not recommend any buys."
    elif cash < portfolio_value * 0.10:
        cash_status = f"WARNING: Cash is very low (${cash:,.2f}). Consider whether selling a weak position to free up capital is smarter than buying anything new."
    elif cash < portfolio_value * 0.25:
        cash_status = f"Cash is limited (${cash:,.2f}). Be very selective — only the highest conviction buys are worth it."
    else:
        cash_status = f"Cash available: ${cash:,.2f} AUD"

    owned_str = f"Currently owned positions:\n{owned_shares}" if owned_shares else "No current positions."

    prompt = f"""You are analysing ASX stocks for short-term trades (now until {target_date}).

PORTFOLIO STATE:
- {cash_status}
- Total portfolio value: ${portfolio_value:,.2f} AUD
- Max single position: ${portfolio_value * 0.25:,.2f} AUD (25% rule)
- {owned_str}

CRITICAL RULE: If cash is 0 or negative, you MUST NOT recommend any buys.
Your only options when cash is exhausted are:
1. Hold everything
2. Sell a weak/losing position to free up cash for a better opportunity

STOCK DATA:
{top_companies}

YOUR TASK:
First, check your cash. If it is <= 0, skip straight to assessing owned positions for sells.

Otherwise, go through each stock and assess it. For each one, note:
1. What signals are present (momentum, RSI, MACD, volume, news)
2. Whether those signals are genuinely convincing or mediocre
3. A conviction rating: HIGH / MEDIUM / LOW / SKIP

Then select your top picks (aim for 2-4 maximum) and for each determine:
- Exactly why you'd buy it right now
- What % of available cash you'd deploy based on conviction:
    HIGH conviction   → up to 20% of cash
    MEDIUM conviction → 8-12% of cash
    LOW conviction    → 4-6% of cash, or skip
    SKIP              → do not buy

Also assess owned positions — if any are underperforming or showing sell signals, 
flag them for sale, especially if cash is low and a better opportunity exists.

Think through this carefully and write your reasoning."""

    response = client.chat.completions.create(
        model="meta/llama-3.1-405b-instruct",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt}
        ],
        temperature=0.3,
        top_p=0.7,
        max_tokens=2048,
        stream=False
    )

    return response.choices[0].message.content


def generate_orders(analysis, unit_limits, cash, portfolio_value, target_date):

    # Hard block buys at the generation step too if no cash
    no_cash_instruction = ""
    if cash <= 0:
        no_cash_instruction = "\nCRITICAL: Cash is $0 or negative. Any BUY lines are FORBIDDEN. Only SELL lines are permitted.\n"

    unit_limits_str = "\n".join(
        f"  {code}: max {units} units"
        for code, units in unit_limits.items()
    )

    prompt = f"""Based on the following trading analysis, generate the final order CSV.

ANALYSIS:
{analysis}

HARD CONSTRAINTS:
- Cash available: ${cash:,.2f} AUD{no_cash_instruction}
- Max per position: ${portfolio_value * 0.25:,.2f} AUD
- You MUST NOT exceed these pre-calculated unit limits:
{unit_limits_str}
- Maximum 5 orders total
- Cannot buy fractional units, always round down
- Do not buy stocks rated SKIP or LOW conviction in the analysis unless exceptional reason
- If cash is 0 or less, output ONLY sell orders or nothing at all

Convert the analysis recommendations into CSV orders only.
Use the unit limits above — do not calculate your own quantities.
Base unit quantities on the conviction-driven cash allocation in the analysis.

OUTPUT FORMAT — return ONLY this, no other text:
BUY,CODE,UNITS
SELL,CODE,UNITS"""

    response = client.chat.completions.create(
        model="meta/llama-3.1-405b-instruct",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt}
        ],
        temperature=0.1,
        top_p=0.7,
        max_tokens=128,
        stream=False
    )

    return response.choices[0].message.content


def send_request(top_companies, unit_limits, cash, portfolio_value,
                 owned_shares=None, target_date="2026-05-21"):
    """
    Two-step pipeline:
    1. Reason openly about which stocks to trade and sizing
    2. Convert reasoning to strict CSV output
    """

    start = time.time()
    print("Reasoning through best options...")
    analysis = analyse_stocks(
        top_companies, cash, portfolio_value, owned_shares, target_date
    )
    print(f"  Reasoning complete ({len(analysis)} chars)")

    # Save output and create folder if doesn't exist
    if not os.path.exists('llm_analysis_logs'):
        os.makedirs('llm_analysis_logs')
                     
    analysis_path = f"llm_analysis_logs/llm_analysis_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
    with open(analysis_path, 'w', encoding='utf-8') as f:
        f.write(analysis)
        print(f"  Saved reasoning to {analysis_path}")

    elapsed = int(time.time() - start)
    print(f"  ✓ Finished in {elapsed} seconds")

    start = time.time()
    print("Generating final actions...")
    
    orders = generate_orders(
        analysis, unit_limits, cash, portfolio_value, target_date
    )

    elapsed = int(time.time() - start)
    print(f"  ✓ Finished in {elapsed} seconds")

    return analysis, orders


def format_for_llm(cash, portfolio_value, top_companies, unit_limits,
                   owned_shares=None, target_date="2026-05-21"):
    """
    Kept for compatibility but send_request now handles everything internally.
    Returns the analysis + orders tuple directly.
    """
    return send_request(
        top_companies, unit_limits, cash, portfolio_value, owned_shares, target_date
    )
