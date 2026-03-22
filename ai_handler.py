import os
from dotenv import load_dotenv
from openai import OpenAI

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
    """
    Step 1: Ask the model to reason about the stocks openly.
    No output format constraints — just think.
    """
    owned_str = f"Currently owned positions:\n{owned_shares}" if owned_shares else "No current positions."

    prompt = f"""You are analysing ASX stocks for short-term trades (now until {target_date}).

PORTFOLIO STATE:
- Cash available: ${cash:,.2f} AUD
- Total portfolio value: ${portfolio_value:,.2f} AUD
- Max single position: ${portfolio_value * 0.25:,.2f} AUD (25% rule)
- {owned_str}

STOCK DATA:
{top_companies}

YOUR TASK:
Go through each stock and assess it. For each one, note:
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

Be ruthless. If fewer than 2 stocks are genuinely compelling, only recommend those.
Do not recommend a stock just to fill a quota.
Also assess any owned positions and flag any that should be sold.

Think through this carefully and write your reasoning."""

    response = client.chat.completions.create(
        model="meta/llama-3.1-405b-instruct",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt}
        ],
        temperature=0.3,
        top_p=0.7,
        max_tokens=2048,  # room to actually reason
        stream=False
    )

    return response.choices[0].message.content


def generate_orders(analysis, unit_limits, cash, portfolio_value, target_date):
    """
    Step 2: Given the reasoning from step 1, convert to CSV orders.
    Strict formatting, low temperature, short output.
    """
    unit_limits_str = "\n".join(
        f"  {code}: max {units} units"
        for code, units in unit_limits.items()
    )

    prompt = f"""Based on the following trading analysis, generate the final order CSV.

ANALYSIS:
{analysis}

HARD CONSTRAINTS:
- Cash available: ${cash:,.2f} AUD
- Max per position: ${portfolio_value * 0.25:,.2f} AUD
- You MUST NOT exceed these pre-calculated unit limits:
{unit_limits_str}
- Maximum 5 orders total
- Cannot buy fractional units, always round down
- Do not buy stocks rated SKIP or LOW conviction in the analysis unless exceptional reason

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
        temperature=0.1,   # very deterministic for order generation
        top_p=0.7,
        max_tokens=128,    # orders only, should be short
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
    print("  Step 1: Analysing stocks...")
    analysis = analyse_stocks(
        top_companies, cash, portfolio_value, owned_shares, target_date
    )
    print(f"  Analysis complete ({len(analysis)} chars)")

    print("  Step 2: Generating orders...")
    orders = generate_orders(
        analysis, unit_limits, cash, portfolio_value, target_date
    )

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