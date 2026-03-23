import yfinance as yf
import pandas_ta as ta
import pandas as pd
import simplejson as json
from datetime import datetime

TARGET_DATE = "2026-05-12"
TOP_N = 15

def get_filter_params(code):
    try:
        ticker = yf.Ticker(f"{code}.AX")
        df = ticker.history(period="6mo")

        if len(df) < 20:
            return None

        current_price = df['Close'].iloc[-1]
        n = len(df)

        # ── Safe lookbacks ──────────────────────────────────────
        price_1m = df['Close'].iloc[-min(21, n-1)]
        price_3m = df['Close'].iloc[-min(63, n-1)]
        price_6m = df['Close'].iloc[-min(126, n-1)]

        momentum_1m = (current_price - price_1m) / price_1m if price_1m else None
        momentum_3m = (current_price - price_3m) / price_3m if price_3m else None
        momentum_6m = (current_price - price_6m) / price_6m if price_6m else None

        week52_high = df['Close'].max()
        week52_low  = df['Close'].min()
        pct_from_high = (current_price - week52_high) / week52_high
        pct_from_low  = (current_price - week52_low)  / week52_low

        # ── Technicals ──────────────────────────────────────────
        sma20  = ta.sma(df['Close'], length=20).iloc[-1]  if n >= 20  else None
        sma50  = ta.sma(df['Close'], length=50).iloc[-1]  if n >= 50  else None
        sma200 = ta.sma(df['Close'], length=200).iloc[-1] if n >= 200 else None
        rsi    = ta.rsi(df['Close'], length=14).iloc[-1]  if n >= 14  else None

        # MACD
        macd_cross = None
        macd_hist  = None
        if n >= 26:
            macd_df    = ta.macd(df['Close'])
            macd_val   = macd_df['MACD_12_26_9'].iloc[-1]
            macd_sig   = macd_df['MACDs_12_26_9'].iloc[-1]
            macd_hist  = macd_df['MACDh_12_26_9'].iloc[-1]
            macd_cross = "bullish" if macd_val > macd_sig else "bearish"

        # ADX
        adx = None
        if n >= 14:
            try:
                adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)['ADX_14'].iloc[-1]
            except:
                pass

        # Bollinger Band position (0 = at lower band, 1 = at upper band)
        bb_pct = None
        if n >= 20:
            try:
                bb = ta.bbands(df['Close'], length=20)
                bb_pct = bb['BBP_20_2.0'].iloc[-1]
            except:
                pass

        # Volume trend: is volume growing over last 10 days vs prior 10?
        vol_recent = df['Volume'].tail(10).mean()
        vol_prior  = df['Volume'].iloc[-20:-10].mean()
        volume_trend = (vol_recent - vol_prior) / vol_prior if vol_prior > 0 else None

        avg_vol_20d    = df['Volume'].tail(20).mean()
        avg_vol_30d    = df['Volume'].tail(30).mean()
        current_volume = df['Volume'].iloc[-1]
        volume_vs_avg  = current_volume / avg_vol_20d if avg_vol_20d > 0 else None

        # ── Fundamentals (fast, ASX-safe) ───────────────────────
        info = ticker.info
        market_cap   = info.get('marketCap')
        pe_ratio     = info.get('trailingPE')
        gross_margin = info.get('grossMargins')
        debt_equity  = info.get('debtToEquity')

        # Revenue growth — quarterly is more reliable but slow; try it, fallback fast
        revenue_growth = None
        try:
            rev = ticker.quarterly_financials.loc['Total Revenue']
            if len(rev) >= 4:
                recent_yr = rev.iloc[:4].sum()
                prior_yr  = rev.iloc[4:8].sum() if len(rev) >= 8 else rev.iloc[-4:].sum()
                revenue_growth = (recent_yr - prior_yr) / abs(prior_yr)
        except:
            revenue_growth = info.get('revenueGrowth')

        # FCF — quarterly cashflow, fast fallback
        free_cash_flow = None
        try:
            cf = ticker.quarterly_cashflow
            op_cf = cf.loc['Operating Cash Flow'].iloc[:4].sum()
            capex = cf.loc['Capital Expenditure'].iloc[:4].sum()
            free_cash_flow = float(op_cf + capex)
        except:
            free_cash_flow = info.get('freeCashflow')

        # ── Catalyst: earnings before target date ────────────────
        earnings_before_target = False
        earnings_date_str = None
        try:
            cal = ticker.calendar
            if cal is not None and not cal.empty:
                ed = cal.iloc[0].get('Earnings Date')
                if ed:
                    earnings_date_str = str(ed)
                    earnings_before_target = earnings_date_str <= TARGET_DATE
        except:
            pass

        return {
            'code':                   code,
            'current_price':          round(float(current_price), 3),
            'market_cap':             market_cap,
            'avg_volume_30d':         int(avg_vol_30d),

            # Momentum
            'momentum_1m':            round(momentum_1m, 4) if momentum_1m is not None else None,
            'momentum_3m':            round(momentum_3m, 4) if momentum_3m is not None else None,
            'momentum_6m':            round(momentum_6m, 4) if momentum_6m is not None else None,

            # Technicals
            'rsi':                    round(float(rsi), 1)   if rsi   is not None else None,
            'adx':                    round(float(adx), 1)   if adx   is not None else None,
            'macd_cross':             macd_cross,
            'macd_hist':              round(float(macd_hist), 4) if macd_hist is not None else None,
            'sma20':                  round(float(sma20), 3) if sma20  is not None else None,
            'sma50':                  round(float(sma50), 3) if sma50  is not None else None,
            'sma200':                 round(float(sma200), 3) if sma200 is not None else None,
            'bb_pct':                 round(float(bb_pct), 3) if bb_pct is not None else None,

            # Volume
            'volume_vs_avg':          round(float(volume_vs_avg), 2) if volume_vs_avg is not None else None,
            'volume_trend_10d':       round(float(volume_trend), 4) if volume_trend is not None else None,

            # 52-week range
            'pct_from_52w_high':      round(float(pct_from_high), 4),
            'pct_from_52w_low':       round(float(pct_from_low), 4),

            # Fundamentals
            'pe_ratio':               pe_ratio,
            'gross_margin':           gross_margin,
            'debt_to_equity':         debt_equity,
            'revenue_growth':         round(float(revenue_growth), 4) if revenue_growth is not None else None,
            'free_cash_flow':         free_cash_flow,

            # Catalyst
            'earnings_before_target': earnings_before_target,
            'earnings_date':          earnings_date_str,

            'data_points':            n,
        }

    except Exception as e:
        print(f"  ⚠ Error fetching {code}: {e}")
        return None


def passes_filter(p):
    """Only hard-rejects genuinely untradeable stocks."""
    if p is None:
        return False, ['no data']

    failed = []

    if p['avg_volume_30d'] < 50_000:
        failed.append(f"illiquid ({p['avg_volume_30d']:,} avg vol)")

    if p['market_cap'] and p['market_cap'] < 5_000_000:
        failed.append(f"micro-cap shell (${p['market_cap']:,.0f})")

    if p['current_price'] < 0.02:
        failed.append(f"price too low (${p['current_price']})")

    if p['rsi'] and p['rsi'] < 20:
        failed.append(f"RSI freefall ({p['rsi']})")

    if p['adx'] and p['adx'] < 10:
        failed.append(f"dead stock (ADX {p['adx']})")

    if p['volume_vs_avg'] and p['volume_vs_avg'] < 0.1:
        failed.append(f"volume collapsed ({p['volume_vs_avg']}x avg)")

    return len(failed) == 0, failed


def score_company(p):
    """
    Scoring tuned for 10-week short-term holds.
    Max possible score: ~34
    """
    score = 0

    # ── Momentum (most important for 10 weeks) ───────────────
    # 1m momentum — strongest short-term predictor
    if p['momentum_1m'] is not None:
        if p['momentum_1m'] > 0.10:   score += 5
        elif p['momentum_1m'] > 0.05: score += 3
        elif p['momentum_1m'] > 0:    score += 1

    # 3m momentum — confirms trend
    if p['momentum_3m'] is not None:
        if p['momentum_3m'] > 0.15:   score += 4
        elif p['momentum_3m'] > 0.05: score += 2
        elif p['momentum_3m'] > 0:    score += 1

    # 6m momentum — context only, lower weight
    if p['momentum_6m'] and p['momentum_6m'] > 0: score += 1

    # ── RSI — entry timing ───────────────────────────────────
    if p['rsi']:
        if 45 <= p['rsi'] <= 60:    score += 4  # ideal: trending but room to run
        elif 60 < p['rsi'] <= 70:   score += 2  # strong trend, slightly overbought
        elif 35 <= p['rsi'] < 45:   score += 1  # recovering
        # <35 or >70: no points — risky entries

    # ── MACD ────────────────────────────────────────────────
    if p['macd_cross'] == 'bullish':              score += 3
    if p['macd_hist'] and p['macd_hist'] > 0:    score += 1  # histogram positive = accelerating

    # ── Trend strength (ADX) ─────────────────────────────────
    if p['adx']:
        if p['adx'] > 35:    score += 4
        elif p['adx'] > 25:  score += 2
        elif p['adx'] > 15:  score += 1

    # ── Price vs moving averages ─────────────────────────────
    if p['sma20']  and p['current_price'] > p['sma20']:  score += 2
    if p['sma50']  and p['current_price'] > p['sma50']:  score += 1
    if p['sma200'] and p['current_price'] > p['sma200']: score += 1

    # ── Bollinger Band position ──────────────────────────────
    # Sweet spot: 0.4–0.7 = mid-to-upper band, trending without being stretched
    if p['bb_pct'] is not None:
        if 0.4 <= p['bb_pct'] <= 0.7:   score += 3
        elif 0.7 < p['bb_pct'] <= 0.85: score += 1  # strong but near top
        elif p['bb_pct'] < 0.2:         score += 1  # potential reversal play

    # ── Volume ──────────────────────────────────────────────
    if p['volume_vs_avg'] and p['volume_vs_avg'] > 1.5:  score += 2
    if p['volume_trend_10d'] and p['volume_trend_10d'] > 0.2: score += 2  # volume growing

    # ── 52-week position ─────────────────────────────────────
    if p['pct_from_52w_high'] > -0.10:   score += 3  # near highs = strong momentum
    elif p['pct_from_52w_high'] > -0.25: score += 1

    # ── Catalyst bonus (huge for 10 weeks) ───────────────────
    if p['earnings_before_target']:      score += 4  # earnings = biggest short-term catalyst

    # ── Fundamentals (minor bonus only) ──────────────────────
    if p['free_cash_flow'] and p['free_cash_flow'] > 0: score += 1

    return score

def parse_company_news(raw_news_items):
    """
    Strips yfinance news objects down to just what the LLM needs.
    """
    cleaned = []
    for item in raw_news_items:
        try:
            content = item.get('content', {})

            # Parse date to readable format
            pub_raw = content.get('pubDate', '')
            try:
                pub_date = datetime.strptime(pub_raw, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d')
            except:
                pub_date = pub_raw[:10] if pub_raw else 'unknown'

            cleaned.append({
                'date':     pub_date,
                'title':    content.get('title', ''),
                'summary':  content.get('summary', '')[:300],  # cap at 300 chars
                'type':     content.get('contentType', 'STORY'),  # STORY or VIDEO
                'source':   content.get('provider', {}).get('displayName', ''),
            })
        except:
            continue

    return cleaned

# returns path the file was saved to
def analyse(companies = None):
    passed = []
    failed = []

    if companies is None:
        df_companies = pd.read_csv('resources/companies-2026.csv')
        companies = df_companies['Code'].drop_duplicates().tolist()  # deduplicated

    print(f"Screening {len(companies)} companies...\n")

    for i, code in enumerate(companies):
        print(f"[{i+1:4}/{len(companies)}] {code:6}", end=" ")

        params = get_filter_params(code)
        passes, reasons = passes_filter(params)

        if passes:
            params['score'] = score_company(params)

            # get news if passed
            ticker = yf.Ticker(f"{code}.AX")
            params['news'] = parse_company_news(ticker.news)

            passed.append(params)
            print(f"🟢  score={params['score']:2}  RSI={params['rsi']}  1m={params['momentum_1m']}  MACD={params['macd_cross']}")
        else:
            failed.append({'code': code, 'reasons': reasons})
            print(f"🔴  {', '.join(reasons)}")

    passed.sort(key=lambda x: x['score'], reverse=True)

    print(f"\n{'='*55}")
    print(f"🟢 Passed: {len(passed):,} / {len(companies):,}")
    print(f"🔴 Filtered: {len(failed):,} / {len(companies):,}")

    print(f"\nTop {min(TOP_N, len(passed))} candidates:")
    for s in passed[:TOP_N]:
        earnings_flag = "📅" if s['earnings_before_target'] else "  "
        print(f"  {earnings_flag}{s['code']:6} score={s['score']:2}  "
            f"RSI={s['rsi']}  1m={s['momentum_1m']}  "
            f"ADX={s['adx']}  MACD={s['macd_cross']}")

    # Save output
    if not os.path.exists('analyser_outputs'):
        os.makedirs('analyser_outputs')
    
    path = f"analyser_outputs/top_companies_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    with open(path, 'w') as f:
        json.dump(passed[:TOP_N], f, indent=2, ignore_nan=True)

    print(f"\nSaved top {min(TOP_N, len(passed))} to {path}")
    return path

if __name__ == "__main__":
    analyse()
