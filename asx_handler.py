def login(page, login, password):
    page.locator('input[name="studentLoginForm:loginId"]').fill(login)
    page.locator('input[name="studentLoginForm:password"]').fill(password)
    page.locator('a.btn.btn-primary', has_text='Login').click()

def buy_stock(page, code, units):
    page.goto("https://game.asx.com.au/game/play/school/2026-1/orders/add")
    page.wait_for_load_state('networkidle')
    page.locator('div#buyside .ui-radiobutton-box').dispatch_event('click')
    page.wait_for_timeout(500)
    page.locator('#asxCode').wait_for(state='visible')
    page.locator('#asxCode').select_option(code)
    page.wait_for_timeout(500)
    page.locator('#volume').wait_for(state='visible')
    page.locator('#volume').click()
    page.locator('#volume').fill(str(units))
    page.wait_for_timeout(500)
    page.locator('div#market_limit .ui-radiobutton-box').dispatch_event('click')
    page.wait_for_timeout(500)
    page.locator('#submitBtn').dispatch_event('click')

    page.wait_for_timeout(500)
    page.locator('#saveBtn').evaluate('el => el.click()')
    page.wait_for_load_state('networkidle')

# SELLING
def get_sellable_company_info(page):
    page.goto("https://game.asx.com.au/game/play/school/2026-1/portfolio")
    page.wait_for_load_state('networkidle')
    rows = page.locator('#table-view tbody tr:not(.mobile-actions)').all()
    companies = []
    for row in rows:
        code = row.locator('td:first-child a').first.inner_text().strip()
        href = row.locator('td:first-child a').first.get_attribute('href')
        holding = int(row.locator('td:nth-child(2)').inner_text().strip().replace(",", ""))
        last = row.locator('td:nth-child(4)').inner_text().strip().replace('$', '')
        companies.append({'code': code, 'price': float(last.replace(",", "")), 'href': href, 'holding': holding})
    return companies

def sell_stock(page, code, units):
    page.goto("https://game.asx.com.au/game/play/school/2026-1/orders/add")
    page.wait_for_load_state('networkidle')
    page.locator('div#sellside .ui-radiobutton-box').dispatch_event('click')
    page.wait_for_timeout(500)
    page.locator('#sellAsxCode').wait_for(state='visible')
    page.locator('#sellAsxCode').select_option(code)
    page.wait_for_timeout(500)
    page.locator('#volume').wait_for(state='visible')
    page.locator('#volume').click()
    page.locator('#volume').fill(str(units))
    page.wait_for_timeout(500)
    page.locator('div#market_limit .ui-radiobutton-box').dispatch_event('click')
    page.wait_for_timeout(500)
    page.locator('#submitBtn').dispatch_event('click')
    
    page.wait_for_timeout(500)
    page.locator('#saveBtn').evaluate('el => el.click()')
    page.wait_for_load_state('networkidle')

def get_cash_and_portfolio_value(page):
    cash_text = page.locator('tr:has(td:text("Cash:")) td.ie8-td-last-child').inner_text().strip()
    cash = int(float(cash_text.replace('$', '').replace(',', '')))
    portfolio_text = page.locator('tr:has(td:text("Portfolio value:")) td.ie8-td-last-child').inner_text().strip()
    portfolio_value = int(float(portfolio_text.replace('$', '').replace(',', '')))

    return (cash, portfolio_value)