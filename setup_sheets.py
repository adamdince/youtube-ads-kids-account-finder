# setup_sheets.py - Helper script to create the initial Google Sheets structure
import gspread
import json
import os
from google.oauth2.service_account import Credentials

def setup_google_sheet():
    """Create the initial Google Sheets structure"""
    
    # Setup credentials (run this locally first)
    service_account_file = 'path/to/your/service-account-key.json'  # Update this path
    
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    credentials = Credentials.from_service_account_file(service_account_file, scopes=scopes)
    gc = gspread.authorize(credentials)
    
    # Create new spreadsheet
    spreadsheet = gc.create('YouTube Kids Channel Analysis')
    spreadsheet.share('your-email@gmail.com', perm_type='user', role='owner')  # Update with your email
    
    print(f"Created spreadsheet: {spreadsheet.url}")
    print(f"Spreadsheet ID: {spreadsheet.id}")
    
    # Create Config worksheet
    config_sheet = spreadsheet.sheet1
    config_sheet.update_title('Config')
    
    config_headers = [
        ['Setting', 'Value', '', 'Summary', 'Value'],
        ['max_results_per_term', '50', '', 'Last Run', ''],
        ['min_kids_score', '3', '', 'Total Channels Found', ''],
        ['', '', '', 'Kids Channels Found', ''],
        ['', '', '', 'Search Terms Used', '']
    ]
    config_sheet.update('A1', config_headers)
    
    # Create Search Terms worksheet
    search_sheet = spreadsheet.add_worksheet(title='Search Terms', rows=100, cols=3)
    search_terms_data = [
        ['Search Term', 'Description', 'Active'],
        ['kids', 'General kids content', 'TRUE'],
        ['children', 'General children content', 'TRUE'],
        ['nursery rhymes', 'Songs for young children', 'TRUE'],
        ['toy review', 'Toy unboxing and reviews', 'TRUE'],
        ['educational kids', 'Educational content for children', 'TRUE'],
        ['cartoon for kids', 'Animated content for children', 'TRUE'],
        ['baby songs', 'Songs for babies and toddlers', 'TRUE'],
        ['cocomelon', 'Popular kids channel brand', 'FALSE'],
        ['blippi', 'Popular kids educational character', 'FALSE'],
        ['peppa pig', 'Popular kids cartoon character', 'FALSE']
    ]
    search_sheet.update('A1', search_terms_data)
    
    # Create Results worksheet (will be populated by the script)
    results_sheet = spreadsheet.add_worksheet(title='Results', rows=1000, cols=10)
    results_headers = [
        'Channel ID', 'Channel Title', 'Channel URL', 'Subscriber Count',
        'Video Count', 'Kids Score', 'Matched Keywords', 'Likely Kids Content',
        'Analysis Date'
    ]
    results_sheet.update('A1', [results_headers])
    
    # Create Instructions worksheet
    instructions_sheet = spreadsheet.add_worksheet(title='Instructions', rows=50, cols=2)
    instructions_data = [
        ['YouTube Kids Channel Analysis Tool', ''],
        ['', ''],
        ['How to use:', ''],
        ['1. Configure Settings', 'Edit the Config sheet to set analysis parameters'],
        ['2. Add Search Terms', 'Add or modify search terms in the Search Terms sheet'],
        ['3. Trigger Analysis', 'Use the trigger URL or run manually from GitHub'],
        ['4. View Results', 'Check the Results sheet for analysis output'],
        ['', ''],
        ['Settings Explanation:', ''],
        ['max_results_per_term', 'Maximum channels to find per search term (API quota limit)'],
        ['min_kids_score', 'Minimum score to include channel in results (3+ recommended)'],
        ['', ''],
        ['GitHub Repository:', 'https://github.com/your-username/youtube-kids-analyzer'],
        ['Trigger Analysis:', 'Run from GitHub Actions or use webhook URL'],
        ['', ''],
        ['Score Meaning:', ''],
        ['0-2', 'Unlikely to be kids content'],
        ['3-5', 'Possibly kids content'],
        ['6+', 'Very likely kids content']
    ]
    instructions_sheet.update('A1', instructions_data)
    
    return spreadsheet.id

if __name__ == "__main__":
    sheet_id = setup_google_sheet()
    print(f"\nSheet ID for GitHub secrets: {sheet_id}")
