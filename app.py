import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

def scrape_annexure_companies():
    # The direct, server-rendered URL for the company list
    url = "https://theannexure.com/companies.html"
    
    # It is crucial to use a User-Agent so the website doesn't block the request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    print(f"Connecting to {url}...")
    try:
        # Enforce a reasonable delay to respect the server
        time.sleep(2) 
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()  # Check for HTTP errors
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch the page: {e}")
        return None

    print("Parsing HTML...")
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find the main table on the page
    table = soup.find('table')
    if not table:
        print("Could not find a <table> on the page. The structure might have changed.")
        return None

    # Extract table rows
    rows = table.find_all('tr')
    
    # The first row contains the headers
    headers = [th.text.strip() for th in rows[0].find_all(['th', 'td'])]
    
    # Extract data from the remaining rows
    data = []
    for row in rows[1:]:
        cols = [td.text.strip() for td in row.find_all('td')]
        # We expect 10 columns based on the headers: Company, Ticker, Market cap, Sector, etc.
        if len(cols) == len(headers):
            data.append(cols)

    # Create a Pandas DataFrame
    df = pd.DataFrame(data, columns=headers)
    
    print(f"Successfully extracted {len(df)} companies!")
    return df

# Run the function and display the result
if __name__ == "__main__":
    companies_df = scrape_annexure_companies()
    
    if companies_df is not None:
        # Display the first 10 rows
        print("\n--- First 10 Companies ---")
        print(companies_df.head(10))
        
        # Optionally, save the data to a CSV file for later use
        companies_df.to_csv("annexure_companies.csv", index=False)
        print("\nData saved to 'annexure_companies.csv'")
