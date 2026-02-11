import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path


def extract_fwd_eps_data(archive_dir, start_date, end_date):
    """
    Extract fwd_eps data from JSON files between start_date and end_date.
    
    Args:
        archive_dir (str | Path): Directory containing JSON files
    start_date (str): Start date in format 'yyyy-mm-dd'
    end_date (str): End date in format 'yyyy-mm-dd'
    
    Returns:
        DataFrame with dates as rows and ticker symbols as columns,
        containing fwd_eps values
    """
    
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    data = {}
    
    archive_path = Path(archive_dir)
    json_files = sorted(archive_path.glob('????-??-??.json'))
    
    for file_path in json_files:
        # Extract date from filename
        date_str = file_path.stem  # Gets filename without extension
        file_date = datetime.strptime(date_str, '%Y-%m-%d')
        
        # Check if date is within range
        if start <= file_date <= end:
            with open(file_path, 'r') as f:
                file_data = json.load(f)
            
            # Extract fwd_eps for each ticker (skip 'metadata' key)
            row_data = {}
            for ticker, ticker_info in file_data.items():
                if ticker != 'metadata' and isinstance(ticker_info, dict):
                    if 'fwd_eps' in ticker_info:
                        row_data[ticker] = ticker_info['fwd_eps']
            
            # Store data with date as key
            data[file_date.date()] = row_data
    
    # Create DataFrame with dates as rows and tickers as columns
    df = pd.DataFrame.from_dict(data, orient='index')
    df.index.name = 'date'
    df = df.sort_index()
    
    return df


# Example usage:
if __name__ == "__main__":
    # Define paths and dates
    archive_directory = "/home/polo/projects/langchn/direct/archive"
    start_date = "2025-09-22"
    end_date = "2026-02-10"
    
    # Extract data
    df = extract_fwd_eps_data(archive_directory, start_date, end_date)
    df.to_csv("archive/fwd_eps.csv")
    # Display the dataframe
    print(df.head(3))
    print(df.tail(3))
    print(f"Shape: {df.shape}")