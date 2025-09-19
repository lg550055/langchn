from bs4 import BeautifulSoup, Tag
from datetime import datetime
from typing import Dict, Optional
import json
import os
import requests
import time

class YahooFinanceAgent:
    def __init__(self):
        self.session = requests.Session()
        # Set comprehensive headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })
    
    def get_stock_data(self, ticker: str, date: str) -> Dict[str, Optional[str]]:
        """
        Get most recent price and eps estimate for a given stock
        Args:
            ticker (str): Stock symbol
        Returns:
            dict: Dictionary containing stock_price, date, and eps_estimate
        """
        result = {
            'ticker': ticker,
            'stock_price': None,
            'date': date,
            'eps_estimate': None
        }
        
        try:
            # Get the analysis page; contains both price and earnings data
            analysis_url = f"https://finance.yahoo.com/quote/{ticker}/analysis/"
            response = self.session.get(analysis_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract stock price using 'data-testid'
            price_element = soup.find('span', {'data-testid': 'qsp-price'})
            if price_element:
                result['stock_price'] = price_element.text.strip()
            else:
                print(f"===== Price element not found for {ticker}")
            
            # Extract date from market time notice -only has time; using today as noted above
            # block deleted
            
            # Extract earnings estimate from earnings estimate section
            earnings_section = soup.find('section', {'data-testid': 'earningsEstimate'})
            if earnings_section:
                # Find the table within the earnings estimate section
                table = soup.select_one('section[data-testid="earningsEstimate"] table')
                if table:
                    tbody = table.find('tbody')
                    # print(f"Table found for earnings estimate: {type(table)}")
                    if tbody and type(tbody) is Tag:
                        rows = tbody.contents
                        if len(rows) >= 2 and type(rows[1]) is Tag:  # Second row (index 1)
                            second_row = rows[1]
                            cells = second_row.find_all('td')
                            # print(f"Cells found in second row: {cells}; type: {type(cells[-1])}")
                            if cells:
                                # Get the last cell value (earnings estimate for next year)
                                last_cell = cells[-1]
                                estimate = last_cell.get_text().strip()
                                if estimate and estimate != '-':
                                    result['eps_estimate'] = estimate

        except requests.RequestException as e:
            print(f"Error fetching data for {ticker}: {e}")
        except Exception as e:
            print(f"Error parsing data for {ticker}: {e}")

        fwd_pe = "N/A"
        price = float(result['stock_price'].replace(',', ''))
        if price and result['eps_estimate']:
            fwd_eps = float(result['eps_estimate'].replace(',', ''))
            if fwd_eps and fwd_eps > 0:
                fwd_pe = round(price / fwd_eps, 1)
            else:
                print(f"\n--- Missing or negative fwd eps for {ticker}")
        print(f"\n{ticker} {price}, fwd eps: {result['eps_estimate']}, fwd p/e {fwd_pe}")
        return result


    def get_multiple_stocks(self, tickers: list) -> None:
        """
        Get data for multiple stock tickers
        Args:
            tickers (list): List of stock symbols; case insensitive
        Returns:
            dict: Dictionary with ticker as key and stock data as value
        """
        # If today is not a trading day, calculate the most recent trading date
        # for now, just use today if weekday, else go back to last Friday
        date = datetime.now()
        if date.weekday() > 4:  # Saturday or Sunday
            days_to_subtract = date.weekday() - 4  # Go back to Friday
            date = date.replace(day=date.day - days_to_subtract)
        date_str = date.strftime('%Y-%m-%d')
        # Wait time, 2 - 6 sec, to respect Yahoo Finance servers
        wait_time = 2 + (4 * (time.time() % 1))  # % 1 -> decimal = nanoseconds part
        # check if a file named 'date_str.json' exists; if so, load it and assign to results
        cache_file_path = f"archive/{date_str}.json"
        if os.path.exists(cache_file_path):
            with open(cache_file_path, 'r') as f:
                results = json.load(f)
            print(f"Loaded {date_str}.json; contains {len(results)} entries")
        else:   
            results = {}

        new_data_count = 0
        for ticker in tickers:
            ticker = ticker.strip().upper()
            # if ticker already in results, skip
            if ticker in results:
                print(f"Skipping {ticker}, already in results: {results[ticker]}")
                continue
            print(f"\nFetching data for {ticker}...")
            results[ticker] = self.get_stock_data(ticker, date_str)
            new_data_count += 1
            time.sleep(wait_time)

        # Only save if new data was fetched
        if new_data_count == 0:
            print("No new data fetched; all tickers already in results.")
            return
        # Save results to a file named '<date_str>.json'
        with open(cache_file_path, 'w') as f:
            json.dump(results, f, indent=4)
        # overwrite 'archive/latest.js'
        print(f"Saved data to {cache_file_path}")
        with open('archive/latest.js', 'w') as latest_file:
            latest_file.write('var financialData = ')
            json.dump(results, latest_file, indent=4)
            latest_file.write(';')
        print("Updated archive/latest.js")


if __name__ == "__main__":
    agent = YahooFinanceAgent()

    dow = ["gs", "msft", "cat", "hd", "shw", "v", "unh", "axp", "jpm", "mcd", "amgn", "trv", "crm", "nvda", "aapl", "amzn", "wmt", "dis", "nke", "vz"]
    qqq = ["nvda", "msft", "aapl", "amzn", "tsla", "meta", "googl", "cost", "avgo", "nflx", "pltr"]
    spy_top = ["brk-b", "xom"]
    other = ["et", "lulu"]
    all = list(set(dow + qqq + spy_top + other))
    agent.get_multiple_stocks(other)
    # agent.get_stock_data("nflx", "2025-09-18")
