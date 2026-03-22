from company_analyser import analyse
from ai_handler import format_for_llm, send_request
from playwright.sync_api import sync_playwright
import asx_handler as asx
from dotenv import load_dotenv
import json
import os
from datetime import datetime

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
        path = analyse()
        with open(path) as json_file:
            data = json.load(json_file)

        unit_limits = get_max_units_per_company(data, cash, portfolio)

        message = format_for_llm(cash, portfolio, data, unit_limits, analyse_owned_stocks())
        
        path = f"prompt_logs/llm_prompt_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
        with open(path, 'w', encoding='utf-8') as f:
            f.write(message)
        print(f"Saved llm prompt to {path}")


        output = send_request(message)

        for line in output.strip().split('\n'):
            action, code, units = line.strip().split(',')

            if "buy" in action.lower():
                print(f"Buying {code} x{units}")
                # todo buy and implement proper logging
            elif "sell" in action.lower():
                print(f"Selling {code} x{units}")
                # todo sell and impelement proper logging