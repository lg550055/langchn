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
        # Set comprehensive headers
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
    
    def get_stock_data(self, ticker: str) -> Dict[str, Optional[str]]:
        """
        Get most recent price and eps estimate for a given stock
        Args:
            ticker (str): Stock symbol
        Returns:
            dict: Dictionary containing stock_price and eps_estimate
        """
        result = {
            'stock_price': None,
            'eps_estimate': ""
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
        print(f"{ticker} {price}, fwd eps: {result['eps_estimate']}, fwd p/e {fwd_pe}")
        return result


    def parse_qqq_comp(self, res_text) -> list:
        comp = []
        soup = BeautifulSoup(res_text, 'html.parser')
        table_body = soup.find(id='companyListComponent')
        if not table_body:
            print("Table_body not found.")
            return comp
        # 'table_body' has 'tr' children, half have 'id' attributes and half have 'style' attributes; keep only those with 'id'
        if type(table_body) is Tag:
            rows = [row for row in table_body.find_all('tr') if type(row) is Tag and row.get('id')]
            print(f"Found {len(rows)} rows")
            # from each row, get the 3rd an 4th 'td' children; 3rd is an 'a' tag whose contents is the ticker, 4th is the weight
            for row in rows:
                cells = row.find_all('td')
                if len(cells) > 3:
                    ticker = cells[2].get_text().strip()
                    weight = cells[3].get_text().strip()
                    comp.append((ticker, weight))
            # consolidate GOOGL and GOOG into one entry
            googl = next((item for item in comp if item[0] == 'GOOGL'), None)
            goog = next((item for item in comp if item[0] == 'GOOG'), None)
            if googl and goog:
                combined_weight = float(googl[1].replace('%', '')) + float(goog[1].replace('%', ''))
                comp = [item for item in comp if item[0] not in ('GOOGL', 'GOOG')]
                # insert combined GOOGL entry right before the next largest weight
                inserted = False
                for i, item in enumerate(comp):
                    if float(item[1].replace('%', '')) < combined_weight:
                        comp.insert(i, ('GOOGL', f"{combined_weight:.2f}%"))
                        inserted = True
                        break
                if not inserted:
                    comp.append(('GOOGL', f"{combined_weight:.2f}%"))
        else:
            print("Table_body is not a Tag.")
        return comp

    def get_comp(self) -> None:
        comp = []
        # check if 'archive/qqq_comp.json' is less than 1 day old; if so, skip
        if os.path.exists('archive/qqq_comp.json'):
            file_mtime = os.path.getmtime('archive/qqq_comp.json')
            if (time.time() - file_mtime) < (1 * 24 * 60 * 60):
                print("qqq_comp.json is less than 1 days old; skipping fetch.")
                return
        try:
            print("\nFetching QQQ components...")
            url = "https://www.slickcharts.com/nasdaq100"
            # update headers for this request to only Accept-Encoding: identity
            self.session.headers.update({
                'Accept-Encoding': 'identity'
            })
            response = self.session.get(url)
            response.raise_for_status()
            print("Page fetched; code: ", response.status_code, type(response.content), response.text[:10], response.headers.get('Content-Type'), response.encoding)
            comp = self.parse_qqq_comp(response.text)

        except requests.RequestException as e:
            print(f"Error fetching data: {e}")
        except Exception as e:
            print(f"Error parsing data: {e}")
        # save to qqq_comp.json in format [{"AAPL": "12.34%"}]
        with open('archive/qqq_comp.json', 'w') as f:
            json.dump({ticker: weight for ticker, weight in comp}, f)
        # open 'archive/latest.js' and add or rplace the field qqq_weight for each matching ticker
        if os.path.exists('archive/latest.js'):
            with open('archive/latest.js', 'r') as f:
                latest_data = f.read()
            # remove 'var financialData = ' and the trailing ';'
            if latest_data.startswith('var financialData = '):
                latest_data = latest_data[len('var financialData = '):]
            if latest_data.endswith(';'):
                latest_data = latest_data[:-1]
            try:
                latest_json = json.loads(latest_data)
                for ticker, weight in comp:
                    if ticker in latest_json:
                        latest_json[ticker]['qqq_weight'] = weight
                with open('archive/latest.js', 'w') as f:
                    f.write('var financialData = ')
                    json.dump(latest_json, f, indent=4)
                    f.write(';')
                print("Updated archive/latest.js with QQQ weights.")
            except json.JSONDecodeError as e:
                print(f"Error decoding latest.js JSON: {e}")
    
        print(f"Top QQQ components: ", comp[:9])
        return


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
            results[ticker] = self.get_stock_data(ticker)
            new_data_count += 1
            time.sleep(wait_time)

        # Only save if new data was fetched
        if new_data_count == 0:
            print("No new data fetched; all tickers already in results.")
            return
        # Save results to file named 'date_str.json'
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
    other = ["et", "lulu", "epd", "wmb", "kmi"]
    all = list(set(dow + qqq + spy_top + other))
    # agent.get_multiple_stocks(all)
    # agent.get_stock_data("nflx")
    agent.get_comp()
