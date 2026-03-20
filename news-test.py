import yfinance as yf

ticker = yf.Ticker("360.AX")

for entry in ticker.news:
    print(f"> {entry['content']['title']}")