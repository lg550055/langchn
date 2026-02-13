from bs4 import BeautifulSoup, Tag
from datetime import datetime
from dotenv import load_dotenv
from enum import StrEnum, auto
from typing import Dict
import json
import os
import requests
import statistics
import time
from mongo import MongoWrapper

load_dotenv()
STOCK_URL = os.getenv('STOCK_URL')
STOCK_SUFFIX = os.getenv('STOCK_SUFFIX')
COMP_URL = os.getenv('COMP_URL')

dow = ["gs", "msft", "cat", "hd", "shw", "v", "unh", "axp", "jpm", "mcd", "amgn", "trv", "crm", "ibm","nvda", "aapl", "amzn", "wmt", "dis", "jnj", "pg", "mmm", "cvx", "ko", "nke", "vz"]
qqq = ["nvda", "msft", "aapl", "amzn", "tsla", "meta", "googl", "cost", "avgo", "nflx", "pltr", "asml", "amd"]

suffix_table = {
    'qqq': 'nasdaq100',
    'dow': 'dowjones',
    'spy': 'sp500'
}

# If today is not a trading day, calculate the most recent trading date
# for now, just use today if weekday, else go back to last Friday
date = datetime.now()
if date.weekday() > 4:  # Saturday or Sunday
    days_to_subtract = date.weekday() - 4  # Go back to Friday
    date = date.replace(day=date.day - days_to_subtract)
date_str = date.strftime('%Y-%m-%d')
cache_file_path = f"archive/{date_str}.json"

class Index(StrEnum):
    DOW = auto()
    QQQ = auto()
    SPY = auto()

class FinanceAgent:
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
    
    def get_stock_data(self, ticker: str) -> Dict[str, float]:
        """
        Get most recent price and eps estimate for a given stock
        Args:
            ticker (str): Stock symbol
        Returns:
            dict: Dictionary containing price, fwd_eps and fwd_pe
        """
        result = {
            'price': None,
            'fwd_eps': 0.0,
            'fwd_pe': 0.0
        }
        
        try:
            # Get page; contains both price and earnings data
            url = f"{STOCK_URL}/{ticker}/{STOCK_SUFFIX}/"
            response = self.session.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Get stock price using 'data-testid'
            price_element = soup.find('span', {'data-testid': 'qsp-price'})
            if price_element:
                result['price'] = round(float(price_element.text.strip().replace(',', '')), 2)
            else:
                print(f"===== Price element not found for {ticker}")
            
            # Get earnings estimate from earnings estimate section
            earnings_section = soup.find('section', {'data-testid': 'earningsEstimate'})
            if earnings_section:
                # Find the table within the earnings estimate section
                table = soup.select_one('section[data-testid="earningsEstimate"] table')
                if table:
                    tbody = table.find('tbody')
                    if tbody and type(tbody) is Tag:
                        rows = tbody.contents
                        if len(rows) >= 4 and type(rows[3]) is Tag:  # 4th row (index 3)
                            second_row = rows[3]
                            cells = second_row.find_all('td')
                            # print(f"Cells found in second row: {cells}; type: {type(cells[-1])}")
                            if cells:
                                # Get the last cell value (earnings estimate for next year)
                                last_cell = cells[-1]
                                estimate = last_cell.get_text().strip()
                                if estimate and estimate != '-':
                                    result['fwd_eps'] = round(float(estimate), 2)

        except requests.RequestException as e:
            print(f"Error fetching data for {ticker}: {e}")
        except Exception as e:
            print(f"Error parsing data for {ticker}: {e}")

        if result['price'] and result['fwd_eps'] > 0:
            result['fwd_pe'] = round(result['price'] / result['fwd_eps'], 1)
        else:
            # Avoid adding empty null data
            print(f"\n--- {ticker} missing or negative fwd eps: {result['fwd_eps']}")
            return {}
        print(f"{ticker} {result['price']}, fwd eps: {result['fwd_eps']}, fwd p/e {result['fwd_pe']}")
        return result


    def parse_comp(self, res_text) -> list[tuple[str, str]]:
        comp = []
        soup = BeautifulSoup(res_text, 'html.parser')
        table_body = soup.find('tbody')

        if table_body and type(table_body) is Tag:
            rows = [row for row in table_body.find_all('tr') if type(row) is Tag]
            print(f"Found {len(rows)} rows")
            # from each row, get the 3rd an 4th 'td' children; 3rd is 'a' tag containing ticker, 4th is the weight
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
            print("Error: table_body not found or is not type Tag: ", table_body, type(table_body))
        return comp
    

    def get_comp(self, indx: Index) -> None:
        comp = []
        comp_file = f"archive/{indx}_comp.json"
        # check if comp file is less than 8 hrs old; if so, skip
        if os.path.exists(comp_file):
            file_mtime = os.path.getmtime(comp_file)
            if (time.time() - file_mtime) < (8 * 60 * 60):
                print(f"{comp_file} is less than 8 hrs old; skipped fetch")
                return
        try:
            print(f"\nFetching {indx} components...")
            suffix = suffix_table[indx]
            url = f"{COMP_URL}/{suffix}"
            # update headers for this request to only Accept-Encoding: identity
            self.session.headers.update({
                'Accept-Encoding': 'identity'
            })
            response = self.session.get(url)
            response.raise_for_status()
            # print("Page fetched; code: ", response.status_code, type(response.content), response.text[:10], response.headers.get('Content-Type'), response.encoding)
            comp = self.parse_comp(response.text)

        except requests.RequestException as e:
            print(f"Error fetching data: {e}")
        except Exception as e:
            print(f"Error parsing data: {e}")
        # save comp to file in format {"AAPL": "12.34%"}
        if comp:
            with open(comp_file, 'w') as f:
                json.dump({ticker: weight for ticker, weight in comp}, f)
            # open 'archive/latest.js' and add or replace the field {indx}_weight for each matching ticker
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
                    # Add logic to calculate and add wafpe and median_pe
                    if 'metadata' not in latest_json:
                        latest_json['metadata'] = {"date": date_str}
                    fwd_pes = []
                    wafpe = 0.0
                    sample_weight = 0.0
                    for ticker, weight in comp:
                        if ticker in latest_json:
                            latest_json[ticker][f'{indx}_weight'] = weight
                            # Add ticker's fwd pe to later caclulate median and add to wafpe
                            fwd_pe = latest_json[ticker]['fwd_pe']
                            fwd_pes.append(fwd_pe)
                            weight_decimal = float(weight.strip('%')) / 100
                            wafpe += fwd_pe * weight_decimal
                            sample_weight += weight_decimal
                    sample_weight_str = f"{sample_weight*100:.0f}%"
                    # Add wafpe (divided by sample weight to normalize), median and sample weight to metadata
                    med = statistics.median(fwd_pes)
                    latest_json['metadata'][f'{indx}_wafpe'] = round(wafpe / sample_weight, 1)
                    latest_json['metadata'][f'{indx}_median_pe'] = round(med, 1)
                    latest_json['metadata'][f'{indx}_sample_weight'] = sample_weight_str

                    with open('archive/latest.js', 'w') as f:
                        f.write('var financialData = ')
                        json.dump(latest_json, f, indent=4)
                        f.write(';')
                    print(f"Updated archive/latest.js with {indx} weights.")
                except json.JSONDecodeError as e:
                    print(f"Error decoding latest.js JSON: {e}")
            top5_weight = round(sum([float(c[1][:-1]) for c in comp[:5]]), 1)
            print(f"Top 5 {indx} components: ", comp[:5], " -agg weight: ", top5_weight, "%")
        return


    def get_multiple_stocks(self, tickers: list, wait_time: float) -> None:
        """
        Get data for multiple stocks and save to a dated and latest JSON file
        Args:
            tickers (list): List of stock symbols; case insensitive
        Returns:
            None
        """
        # check if a file named 'date_str.json' exists; if so, load it and assign to results
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
            result = self.get_stock_data(ticker)
            # Avoid adding empty data
            if result:
                results[ticker] = result
                new_data_count += 1
            else:
                print("--- Error: empty fetch result for ", ticker)
            time.sleep(wait_time)

        # Only save if new data was fetched
        if new_data_count == 0:
            print("No new data fetched; all tickers already in results.")
            return
        # Before saving, add a metadata object with fetch date
        results['metadata'] = {
            'date': date_str,
            'qqq_wafpe': '',
            "qqq_median_pe": '',
            'dow_wafpe': '',
            "dow_median_pe": ''
        }
        # Save results to file named 'date_str.json'
        with open(cache_file_path, 'w') as f:
            json.dump(results, f, indent=4)
        print(f"Saved data to {cache_file_path}")
        # overwrite 'archive/latest.js'
        with open('archive/latest.js', 'w') as latest_file:
            latest_file.write('var financialData = ')
            json.dump(results, latest_file, indent=4)
            latest_file.write(';')
        print("Updated archive/latest.js")


if __name__ == "__main__":
    agent = FinanceAgent()
    # Wait time, 2 - 6 sec, to respect server load
    wait_time = 2 + (4 * (time.time() % 1))  # % 1 -> decimal = nanoseconds part

    spy_top = ["brk-b", "orcl", "xom", "lly", "ma"]
    other = ["et", "lulu", "epd", "wmb", "kmi"]
    all_xdow = list(set(qqq + spy_top + other))
    # agent.get_stock_data("ibm")  # test single stock
    agent.get_multiple_stocks(all_xdow, wait_time)
    time.sleep(wait_time)
    agent.get_multiple_stocks(dow, wait_time)
    agent.get_comp(Index.DOW)
    time.sleep(wait_time)
    agent.get_comp(Index.QQQ)
    time.sleep(wait_time)
    agent.get_comp(Index.SPY)
    # Save to db
    mongo = MongoWrapper()
    mongo.save_file_data_to_db(cache_file_path, date_str)
