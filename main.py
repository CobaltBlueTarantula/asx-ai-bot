from company_analyser import analyse
from ai_handler import format_for_llm, send_request
from playwright.sync_api import sync_playwright
import asx_handler as asx
from dotenv import load_dotenv
import json
import os
from datetime import datetime
import asyncio
import discord_handler as dscrd
import asyncio
import discord_handler as dscrd

cash = 50000
portfolio = 50000

load_dotenv()
login = os.getenv("ASX_LOGIN")
password = os.getenv("ASX_PASSWORD")

def calc_max_units(price, cash, max_spending):
    budget = min(cash, max_spending)
    
    # Assume flat $15 brokerage first
    units = int((budget - 15) / price)
    
    # If trade value exceeds $15k, recalculate with 0.1% brokerage
    if units * price > 15_000:
        units = int(budget / 1.001)  # divide by 1.001 to back out the 0.1%
        units = int(units / price)
    
    return units


def get_max_units_per_company(companies, cash, portfolio_value):
    return {
        c['code']: calc_max_units(c['current_price'], cash, portfolio_value * 0.25)
        for c in companies
        if c.get('current_price') and c['current_price'] > 0
    }

def analyse_owned_stocks():
    codes = []
    units_per_code = []
    for company in asx.get_sellable_company_info(page):
        code = company.get("code")
        units = company.get("holding")

        codes.append(code)
        units_per_code.append(units)

    path = analyse(codes)
    with open(path) as json_file:
        owned_data = json.load(json_file)

    for stock, i in owned_data:
        stock['units_holding'] = units_per_code[i]

    # delete file after
    os.remove(path)
    return owned_data

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://game.asx.com.au/game/student/school/2026-1/login")
        asx.login(page, login, password)
        page.wait_for_load_state('networkidle')

        cash, portfolio = asx.get_cash_and_portfolio_value(page)

        # send llm request
        #path = analyse()
        path = "analyser_outputs/top_companies_2026-03-22_15-07-14.json"
        with open(path) as json_file:
            data = json.load(json_file)

        unit_limits = get_max_units_per_company(data, cash, portfolio)
        held_shares = analyse_owned_stocks()

        analysis, output = send_request(
            data,
            unit_limits,
            cash,
            portfolio,
            held_shares
        )

        # Save the reasoning to audit decisions
        analysis_path = f"llm_analysis_logs/llm_analysis_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
        with open(analysis_path, 'w', encoding='utf-8') as f:
            f.write(analysis)
        print(f"Saved analysis to {analysis_path}")

        held_str = "\n".join(f"- *{share['code']}* x{share['units_holding']}" for share in held_shares) if held_shares else ""
        held_section = f"## Held Shares:\n{held_str}\n" if held_str else ""

        log_message = f"# Status\n**Cash:** ${cash:,.2f}\n**Portfolio Value:** ${portfolio:,.2f}\n{held_section}# Actions:"

        for line in output.strip().split('\n'):
            action, code, units = line.strip().split(',')

            try:
                units = max(1, int(float(units)))
            except (ValueError, TypeError):
                print(f"  ⚠ Invalid units for {code}: {units}, skipping")
                continue

            if "buy" in action.lower():
                max_units = unit_limits.get(code, 0)
                if max_units == 0:
                    log_message += f"\n- Cannot buy any units of *{code}*"
                    continue
                units = min(units, max_units) # clamp

                log_message += f"\n- Buying *{code}* x{units}"
                asx.buy_stock(page, code, units)
            elif "sell" in action.lower():
                owned = next((s['units_holding'] for s in held_shares if s['code'] == code), 0)
                if owned == 0:
                    log_message += f"\n- Cannot sell any units of *{code}*"
                    continue
                units = min(units, owned) # clamp

                log_message += f"\n- Selling *{code}* x{units}"
                asx.sell_stock(page, code, units)
            else:
                log_message += f"\n- Unknown Instruction: {line.strip()}"
        
        dscrd.send_message(log_message)