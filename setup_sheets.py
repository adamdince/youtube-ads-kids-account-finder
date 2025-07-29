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
    
    # Create Search Terms worksheet with your comprehensive list
    search_sheet = spreadsheet.add_worksheet(title='Search Terms', rows=200, cols=3)
    
    # Your comprehensive search terms list
    search_terms_data = [
        ['Search Term', 'Description', 'Active'],
        # Popular Kids Characters/Shows
        ['peppa pig', 'Popular kids cartoon character', 'TRUE'],
        ['cocomelon', 'Popular kids educational channel', 'TRUE'],
        ['blippi', 'Popular kids educational character', 'TRUE'],
        ['baby shark', 'Popular kids song/character', 'TRUE'],
        ['ms rachel', 'Popular toddler educator', 'TRUE'],
        ['ryans world', 'Popular kids toy review channel', 'TRUE'],
        ['bluey', 'Popular kids cartoon show', 'TRUE'],
        ['mickey mouse clubhouse', 'Disney kids show', 'TRUE'],
        ['paw patrol', 'Popular kids cartoon', 'TRUE'],
        ['pj masks', 'Popular kids superhero cartoon', 'TRUE'],
        ['sesame street', 'Classic educational kids show', 'TRUE'],
        ['little baby bum', 'Popular nursery rhyme channel', 'TRUE'],
        
        # Music Content for Kids
        ['nursery rhymes', 'Traditional songs for young children', 'TRUE'],
        ['kids songs', 'General music content for children', 'TRUE'],
        ['baby songs', 'Music specifically for babies', 'TRUE'],
        ['toddler songs', 'Music for toddlers 1-3 years', 'TRUE'],
        ['abc songs', 'Alphabet learning songs', 'TRUE'],
        ['counting songs', 'Number learning songs', 'TRUE'],
        ['lullabies for babies', 'Sleep songs for infants', 'TRUE'],
        ['bedtime songs for toddlers', 'Sleep songs for toddlers', 'TRUE'],
        ['sing-along kids', 'Interactive music for children', 'TRUE'],
        ['educational songs for toddlers', 'Learning through music', 'TRUE'],
        
        # Educational Content
        ['learning videos for toddlers', 'Educational content for young children', 'TRUE'],
        ['abc learning for kids', 'Alphabet education', 'TRUE'],
        ['numbers for toddlers', 'Math education for young children', 'TRUE'],
        ['shapes and colors for preschoolers', 'Basic concepts for preschoolers', 'TRUE'],
        ['early learning videos', 'Educational content for early development', 'TRUE'],
        ['educational videos for 2 year olds', 'Age-specific learning content', 'TRUE'],
        ['kindergarten learning songs', 'Education through music for K students', 'TRUE'],
        
        # Gaming Content for Kids
        ['roblox for kids', 'Child-friendly Roblox content', 'TRUE'],
        ['minecraft kids', 'Child-friendly Minecraft content', 'TRUE'],
        ['among us funny kids', 'Child-friendly Among Us content', 'TRUE'],
        ['youtube kids gaming', 'Gaming content specifically for children', 'TRUE'],
        
        # Toy and Entertainment Content
        ['toy unboxing', 'Toy reveal and review videos', 'TRUE'],
        ['surprise eggs', 'Toy surprise videos popular with kids', 'TRUE'],
        ['kids prank videos', 'Child-friendly prank content', 'TRUE'],
        ['toy reviews for kids', 'Toy evaluation content for children', 'TRUE'],
        
        # General Kids Content
        ['youtube kids', 'Content specifically marked for children', 'TRUE'],
        ['made for kids', 'Officially designated children content', 'TRUE'],
        ['videos for 2 year olds', 'Age-specific content for toddlers', 'TRUE'],
        ['kids cartoon channel', 'Animated content for children', 'TRUE'],
        ['toddler video compilation', 'Compiled content for young children', 'TRUE'],
        ['kids story time', 'Storytelling content for children', 'TRUE'],
        
        # Additional backup terms (set to FALSE initially)
        ['kids', 'General kids content - backup term', 'FALSE'],
        ['children', 'General children content - backup term', 'FALSE'],
        ['toddler', 'General toddler content - backup term', 'FALSE'],
        ['preschool', 'General preschool content - backup term', 'FALSE'],
    ]
    
    search_sheet.update('A1', search_terms_data)
    
    # Create Results worksheet (will be populated by the script)
    results_sheet = spreadsheet.add_worksheet(title='Results', rows=5000, cols=10)  # Increased rows for more results
    results_headers = [
        'Channel ID', 'Channel Title', 'Channel URL', 'Subscriber Count',
        'Video Count', 'Kids Score', 'Matched Keywords', 'Likely Kids Content',
        'Analysis Date'
    ]
    results_sheet.update('A1', [results_headers])
    
    # Create Instructions worksheet
    instructions_sheet = spreadsheet.add_worksheet(title='Instructions', rows=100, cols=2)
    instructions_data = [
        ['YouTube Kids Channel Analysis Tool', ''],
        ['', ''],
        ['How to use:', ''],
        ['1. Configure Settings', 'Edit the Config sheet to set analysis parameters'],
        ['2. Manage Search Terms', 'Enable/disable search terms in the Search Terms sheet'],
        ['3. Trigger Analysis', 'Use the trigger URL or run manually from GitHub'],
        ['4. View Results', 'Check the Results sheet for analysis output'],
        ['', ''],
        ['Settings Explanation:', ''],
        ['max_results_per_term', 'Maximum channels to find per search term (50 max per API call)'],
        ['min_kids_score', 'Minimum score to include channel in results (3+ recommended)'],
        ['', ''],
        ['Search Terms Management:', ''],
        ['Active = TRUE', 'Term will be used in searches'],
        ['Active = FALSE', 'Term will be skipped (good for testing)'],
        ['', ''],
        ['Expected Daily Results:', ''],
        ['With all terms active', '~42 search terms × 50 results = 2,100 channels analyzed'],
        ['Realistic unique channels', '~500-1,000 per day (accounting for duplicates)'],
        ['New channels added daily', '~50-300 (depending on previous runs)'],
        ['', ''],
        ['API Quota Usage:', ''],
        ['Daily quota limit', '10,000 units'],
        ['Estimated daily usage', '~2,000-3,000 units'],
        ['Remaining quota', 'Plenty of room for multiple daily runs'],
        ['', ''],
        ['GitHub Repository:', 'https://github.com/your-username/youtube-kids-analyzer'],
        ['', ''],
        ['Score Meaning:', ''],
        ['0-2', 'Unlikely to be kids content'],
        ['3-5', 'Possibly kids content'],
        ['6+', 'Very likely kids content']
    ]
    instructions_sheet.update('A1', instructions_data)
    
    print(f"Added {len(search_terms_data)-1} search terms to the sheet")
    return spreadsheet.id

if __name__ == "__main__":
    sheet_id = setup_google_sheet()
    print(f"\nSheet ID for GitHub secrets: {sheet_id}")
    print(f"\nNext steps:")
    print(f"1. Update the service account file path in this script")
    print(f"2. Update your email address in this script") 
    print(f"3. Run this script locally to create your Google Sheet")
    print(f"4. Copy the Sheet ID to your GitHub secrets")
