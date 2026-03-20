import yfinance as yf
import pandas_ta as ta
import pandas as pd
import numpy as np
import json
from datetime import datetime

def get_filter_params(code):
    try:
        ticker = yf.Ticker(f"{code}.AX")
        df = ticker.history(period="6mo")  # reduced to 6mo — less data required

        if len(df) < 20:  # only skip if barely any data at all
            return None

        current_price = df['Close'].iloc[-1]

        # --- Safe lookbacks: only go as far back as data allows ---
        price_1m_ago  = df['Close'].iloc[-min(21, len(df))]
        price_3m_ago  = df['Close'].iloc[-min(63, len(df))]
        price_6m_ago  = df['Close'].iloc[-min(126, len(df))]

        week52_high = df['Close'].max()  # max of available data, not strict 52w
        week52_low  = df['Close'].min()

        momentum_3m = (current_price - price_3m_ago) / price_3m_ago if price_3m_ago else None
        momentum_6m = (current_price - price_6m_ago) / price_6m_ago if price_6m_ago else None

        # --- Technicals ---
        if len(df) >= 50:
            df['SMA50'] = ta.sma(df['Close'], length=50)
            sma50 = df['SMA50'].iloc[-1]
        else:
            sma50 = None

        if len(df) >= 200:
            df['SMA200'] = ta.sma(df['Close'], length=200)
            sma200 = df['SMA200'].iloc[-1]
        else:
            sma200 = None

        if len(df) >= 14:
            df['RSI'] = ta.rsi(df['Close'], length=14)
            rsi = df['RSI'].iloc[-1]
        else:
            rsi = None

        if len(df) >= 14:
            try:
                adx_data = ta.adx(df['High'], df['Low'], df['Close'], length=14)
                adx = adx_data['ADX_14'].iloc[-1]
            except:
                adx = None
        else:
            adx = None

        # --- Volume ---
        avg_volume_30d = df['Volume'].tail(30).mean()
        avg_volume_20d = df['Volume'].tail(20).mean()
        current_volume = df['Volume'].iloc[-1]
        volume_vs_avg  = current_volume / avg_volume_20d if avg_volume_20d > 0 else None

        # --- Fundamentals (with safe fallbacks) ---
        info = ticker.info

        market_cap = info.get('marketCap')

        # Revenue growth — calculate from quarterly if possible
        try:
            rev = ticker.quarterly_financials.loc['Total Revenue']
            if len(rev) >= 8:
                revenue_growth = (rev.iloc[:4].sum() - rev.iloc[4:8].sum()) / abs(rev.iloc[4:8].sum())
            elif len(rev) >= 2:
                revenue_growth = (rev.iloc[0] - rev.iloc[-1]) / abs(rev.iloc[-1])
            else:
                revenue_growth = info.get('revenueGrowth')
        except:
            revenue_growth = info.get('revenueGrowth')

        # FCF
        try:
            cf = ticker.quarterly_cashflow
            op_cf  = cf.loc['Operating Cash Flow'].iloc[:4].sum()
            capex  = cf.loc['Capital Expenditure'].iloc[:4].sum()
            free_cash_flow = op_cf + capex
        except:
            free_cash_flow = info.get('freeCashflow')

        return {
            'code':           code,
            'current_price':    round(current_price, 3),
            'avg_volume_30d':   int(avg_volume_30d),
            'market_cap':       market_cap,
            'rsi':              round(rsi, 1) if rsi else None,
            'adx':              round(adx, 1) if adx else None,
            'sma50':            round(sma50, 3) if sma50 else None,
            'sma200':           round(sma200, 3) if sma200 else None,
            'momentum_3m':      round(momentum_3m, 4) if momentum_3m else None,
            'momentum_6m':      round(momentum_6m, 4) if momentum_6m else None,
            'pct_from_52w_high': round((current_price - week52_high) / week52_high, 4),
            'pct_from_52w_low':  round((current_price - week52_low) / week52_low, 4),
            'volume_vs_avg':    round(volume_vs_avg, 2) if volume_vs_avg else None,
            'revenue_growth':   round(revenue_growth, 4) if revenue_growth else None,
            'gross_margin':     info.get('grossMargins'),
            'debt_to_equity':   info.get('debtToEquity'),
            'free_cash_flow':   free_cash_flow,
            'pe_ratio':         info.get('trailingPE'),
            'data_points':      len(df),  # so LLM knows how much history existed
        }

    except Exception as e:
        print(f"  ⚠ Error fetching {code}: {e}")
        return None


def passes_filter(p):
    if p is None:
        return False, ['no data']

    failed = []

    # 1. Can't trade it at all
    if p['avg_volume_30d'] < 50_000:
        failed.append(f"illiquid ({int(p['avg_volume_30d']):,} avg vol)")

    # 2. Shell company / too tiny
    if p['market_cap'] and p['market_cap'] < 5_000_000:
        failed.append(f"market cap too small (${p['market_cap']:,.0f})")

    # 3. Price so low it's effectively a shell
    if p['current_price'] < 0.02:
        failed.append(f"price too low (${p['current_price']})")

    # 4. RSI in absolute freefall — not a short-term buy candidate
    if p['rsi'] and p['rsi'] < 20:
        failed.append(f"RSI in freefall ({p['rsi']})")

    # 5. No price movement at all — dead stock
    if p['adx'] and p['adx'] < 10:
        failed.append(f"no trend/movement (ADX {p['adx']})")

    # 6. Complete volume collapse
    if p['volume_vs_avg'] and p['volume_vs_avg'] < 0.1:
        failed.append(f"volume collapsed ({p['volume_vs_avg']}x avg)")

    return len(failed) == 0, failed


def score_company(p):
    score = 0

    # Short-term momentum
    if p['momentum_3m'] and p['momentum_3m'] > 0.05:  score += 3
    if p['momentum_3m'] and p['momentum_3m'] > 0.15:  score += 2  # bonus for strong
    if p['momentum_6m'] and p['momentum_6m'] > 0:     score += 1

    # RSI — sweet spot for short-term entry
    if p['rsi']:
        if 45 <= p['rsi'] <= 65:   score += 3  # ideal entry zone
        elif 35 <= p['rsi'] < 45:  score += 1  # ok, might still be recovering
        elif 65 < p['rsi'] <= 75:  score += 1  # overbought but trending

    # Trend strength
    if p['adx']:
        if p['adx'] > 30:  score += 3
        elif p['adx'] > 20: score += 1

    # Price vs moving averages
    if p['sma50'] and p['current_price'] > p['sma50']:    score += 2
    if p['sma200'] and p['current_price'] > p['sma200']:  score += 1

    # Volume increasing — institutional interest
    if p['volume_vs_avg'] and p['volume_vs_avg'] > 1.5:  score += 2

    # Not too far from 52w high (momentum intact)
    if p['pct_from_52w_high'] > -0.15:  score += 2
    elif p['pct_from_52w_high'] > -0.30: score += 1

    # Positive FCF is a bonus, not a requirement
    if p['free_cash_flow'] and p['free_cash_flow'] > 0:  score += 1

    return score

results = []
passed  = []
failed = []

df = pd.read_csv('companies-2026.csv')
companies = df['Code']

for i, code in enumerate(companies):
    print(f"[{i + 1:3}/{len(companies)}] {code:4}", end=" ")

    params = get_filter_params(code)
    passes, failure_reasons = passes_filter(params)

    if passes:
        params['score'] = score_company(params)
        passed.append(params)
        print(f"🟢  Score: {params['score']}")
    else:
        failed.append({'code': code, 'reasons': failure_reasons})
        print(f"🔴  Filtered: {', '.join(failure_reasons)}")

    #time.sleep(0.2)  # yfinance rate limits

# Sort by score descending
passed.sort(key=lambda x: x['score'], reverse=True)

print(f"\n{'='*50}")
print(f"🟢 Passed: {len(passed)} / {len(companies)}")
print(f"🔴 Filtered: {len(failed)} / {len(companies)}")

print(f"\nTop scoring companies:")
for s in passed[:80]:
    print(f"{s['code']:5} score={s['score']:2}  RSI={s['rsi']}  3m={s['momentum_3m']}  ADX={s['adx']}")

path = f"analyser_outputs/top_companies_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.json"

# save top 80 for future use
with open(path, 'w') as f:
    json.dump(passed[:80], f, indent=2)

print(f"\nSaved top {min(80, len(passed))} to {path}")