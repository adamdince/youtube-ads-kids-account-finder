# main.py - Main script for GitHub Actions
import os
import json
import requests
import re
from typing import List, Dict
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

class YouTubeSheetsAnalyzer:
    def __init__(self):
        self.youtube_api_key = os.environ['YOUTUBE_API_KEY']
        self.base_url = "https://www.googleapis.com/youtube/v3"
        
        # Setup Google Sheets connection
        self.setup_sheets_client()
        
        # Kids content keywords
        self.kids_keywords = {
            'direct': [
                'kids', 'children', 'child', 'baby', 'babies', 'toddler', 'toddlers',
                'preschool', 'kindergarten', 'nursery', 'playground', 'daycare'
            ],
            'content': [
                'nursery rhymes', 'lullaby', 'lullabies', 'bedtime stories',
                'abc song', 'counting song', 'finger family', 'wheels on the bus',
                'twinkle twinkle', 'educational videos', 'learning videos',
                'cartoon for kids', 'animation for children', 'kids songs',
                'children songs', 'toy review', 'toy unboxing', 'play time'
            ],
            'characters': [
                'peppa pig', 'paw patrol', 'bluey', 'cocomelon', 'blippi',
                'ryan', 'diana', 'vlad', 'nastya', 'mickey mouse clubhouse',
                'daniel tiger', 'sesame street', 'thomas the train'
            ]
        }
    
    def setup_sheets_client(self):
        """Setup Google Sheets API client"""
        # Google service account credentials from GitHub secrets
        service_account_info = json.loads(os.environ['GOOGLE_SHEETS_CREDENTIALS'])
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_info(
            service_account_info, scopes=scopes
        )
        
        self.gc = gspread.authorize(credentials)
    
    def get_input_from_sheets(self) -> Dict:
        """Read configuration and search terms from Google Sheets"""
        sheet_id = os.environ['GOOGLE_SHEET_ID']
        
        try:
            spreadsheet = self.gc.open_by_key(sheet_id)
            
            # Read from 'Config' worksheet
            config_sheet = spreadsheet.worksheet('Config')
            config_data = config_sheet.get_all_records()
            
            # Read search terms from 'Search Terms' worksheet
            search_sheet = spreadsheet.worksheet('Search Terms')
            search_terms = [row[0] for row in search_sheet.get_all_values()[1:] if row[0]]
            
            return {
                'search_terms': search_terms,
                'max_results_per_term': int(config_data[0].get('max_results_per_term', 50)),
                'min_kids_score': int(config_data[0].get('min_kids_score', 3))
            }
        except Exception as e:
            print(f"Error reading from sheets: {e}")
            # Fallback defaults
            return {
                'search_terms': ['kids', 'children', 'nursery rhymes'],
                'max_results_per_term': 100,
                'min_kids_score': 3
            }
    
    def search_channels(self, query: str, max_results: int = 100) -> List[str]:
        """Search for channels and return channel IDs with pagination support"""
        url = f"{self.base_url}/search"
        channel_ids = []
        next_page_token = None
        results_per_page = min(50, max_results)  # API max is 50 per request
        
        while len(channel_ids) < max_results:
            # Calculate how many results we still need
            remaining_results = max_results - len(channel_ids)
            current_page_size = min(results_per_page, remaining_results)
            
            params = {
                'part': 'snippet',
                'type': 'channel',
                'q': query,
                'maxResults': current_page_size,
                'key': self.youtube_api_key
            }
            
            # Add pagination token if we have one
            if next_page_token:
                params['pageToken'] = next_page_token
            
            try:
                response = requests.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract channel IDs from this page
                    for item in data['items']:
                        if len(channel_ids) < max_results:
                            channel_ids.append(item['snippet']['channelId'])
                    
                    # Check if there are more pages
                    next_page_token = data.get('nextPageToken')
                    
                    # If no more pages or we have enough results, break
                    if not next_page_token or len(channel_ids) >= max_results:
                        break
                        
                else:
                    print(f"Error searching for '{query}': {response.status_code}")
                    break
                    
            except Exception as e:
                print(f"Exception searching for '{query}': {e}")
                break
        
        return channel_ids[:max_results]  # Ensure we don't exceed the requested amount
    
    def get_channel_info(self, channel_id: str) -> Dict:
        """Get detailed channel information"""
        url = f"{self.base_url}/channels"
        params = {
            'part': 'snippet,brandingSettings,statistics,status',
            'id': channel_id,
            'key': self.youtube_api_key
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data['items']:
                return data['items'][0]
        return {}
    
    def analyze_text_for_kids_content(self, text: str) -> Dict:
        """Analyze text for children's content indicators"""
        text_lower = text.lower()
        score = 0
        matched_keywords = []
        
        # Check direct kids keywords (higher weight)
        for keyword in self.kids_keywords['direct']:
            if keyword in text_lower:
                score += 3
                matched_keywords.append(keyword)
        
        # Check content keywords (medium weight)
        for keyword in self.kids_keywords['content']:
            if keyword in text_lower:
                score += 2
                matched_keywords.append(keyword)
        
        # Check character keywords
        for keyword in self.kids_keywords['characters']:
            if keyword in text_lower:
                score += 2
                matched_keywords.append(keyword)
        
        # Check for age-related mentions
        age_pattern = r'\b(?:ages?\s+)?(\d+)\s*(?:-|to)\s*(\d+)\b'
        age_matches = re.findall(age_pattern, text_lower)
        for match in age_matches:
            min_age, max_age = int(match[0]), int(match[1])
            if min_age <= 12 or max_age <= 12:
                score += 4
                matched_keywords.append(f"ages {min_age}-{max_age}")
        
        return {
            'score': score,
            'matched_keywords': list(set(matched_keywords)),
            'likely_kids_content': score >= 3
        }
    
    def analyze_channel(self, channel_id: str) -> Dict:
        """Comprehensive analysis of a channel for kids content"""
        channel_info = self.get_channel_info(channel_id)
        if not channel_info:
            return {'error': 'Channel not found', 'channel_id': channel_id}
        
        snippet = channel_info.get('snippet', {})
        branding = channel_info.get('brandingSettings', {})
        
        # Collect text to analyze
        texts_to_analyze = []
        
        if snippet.get('title'):
            texts_to_analyze.append(snippet['title'])
        if snippet.get('description'):
            texts_to_analyze.append(snippet['description'])
        if branding.get('channel', {}).get('description'):
            texts_to_analyze.append(branding['channel']['description'])
        
        combined_text = ' '.join(texts_to_analyze)
        analysis = self.analyze_text_for_kids_content(combined_text)
        
        return {
            'channel_id': channel_id,
            'channel_title': snippet.get('title', ''),
            'channel_url': f"https://www.youtube.com/channel/{channel_id}",
            'subscriber_count': int(channel_info.get('statistics', {}).get('subscriberCount', 0)),
            'video_count': int(channel_info.get('statistics', {}).get('videoCount', 0)),
            'kids_content_score': analysis['score'],
            'matched_keywords': ', '.join(analysis['matched_keywords']),
            'likely_kids_content': analysis['likely_kids_content'],
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def get_existing_channels(self) -> set:
        """Get all channel IDs that have been previously found"""
        sheet_id = os.environ['GOOGLE_SHEET_ID']
        spreadsheet = self.gc.open_by_key(sheet_id)
        
        try:
            results_sheet = spreadsheet.worksheet('Results')
            all_data = results_sheet.get_all_values()
            
            # Skip header row and extract channel IDs (first column)
            existing_channels = set()
            for row in all_data[1:]:  # Skip header
                if row and len(row) > 0 and row[0]:  # Check if channel ID exists
                    existing_channels.add(row[0])
            
            print(f"Found {len(existing_channels)} existing channels in Results sheet")
            return existing_channels
            
        except gspread.WorksheetNotFound:
            print("Results sheet not found - this must be the first run")
            return set()
        except Exception as e:
            print(f"Error reading existing channels: {e}")
            return set()

    def write_results_to_sheets(self, results: List[Dict], config: Dict):
        """Write only NEW analysis results to Google Sheets"""
        sheet_id = os.environ['GOOGLE_SHEET_ID']
        spreadsheet = self.gc.open_by_key(sheet_id)
        
        # Get existing channels to avoid duplicates
        existing_channel_ids = self.get_existing_channels()
        
        # Create or get Results worksheet
        try:
            results_sheet = spreadsheet.worksheet('Results')
        except gspread.WorksheetNotFound:
            results_sheet = spreadsheet.add_worksheet(title='Results', rows=1000, cols=10)
            # Add headers for new sheet
            headers = [
                'Channel ID', 'Channel Title', 'Channel URL', 'Subscriber Count',
                'Video Count', 'Kids Score', 'Matched Keywords', 'Likely Kids Content',
                'Analysis Date'
            ]
            results_sheet.update('A1', [headers])
        
        # Filter results based on minimum score AND exclude existing channels
        filtered_results = [
            r for r in results 
            if (r.get('kids_content_score', 0) >= config['min_kids_score'] 
                and 'error' not in r 
                and r.get('channel_id') not in existing_channel_ids)
        ]
        
        # Only proceed if we have new channels
        if not filtered_results:
            print("No new kids channels found - all channels were already in the database")
            self.update_summary(spreadsheet, len(results), 0, config)
            return
        
        # Prepare data for new channels only
        new_rows = []
        for result in filtered_results:
            row = [
                result.get('channel_id', ''),
                result.get('channel_title', ''),
                result.get('channel_url', ''),
                result.get('subscriber_count', 0),
                result.get('video_count', 0),
                result.get('kids_content_score', 0),
                result.get('matched_keywords', ''),
                'Yes' if result.get('likely_kids_content', False) else 'No',
                result.get('analysis_date', '')
            ]
            new_rows.append(row)
        
        # Append new rows to the existing sheet (don't overwrite)
        if new_rows:
            # Find the next empty row
            all_values = results_sheet.get_all_values()
            next_row = len(all_values) + 1
            
            # Update starting from the next empty row
            range_name = f'A{next_row}'
            results_sheet.update(range_name, new_rows)
            
            print(f"Added {len(filtered_results)} NEW kids channels to Google Sheets")
        
        # Update summary
        self.update_summary(spreadsheet, len(results), len(filtered_results), config)
    
    def update_summary(self, spreadsheet, total_found: int, new_added: int, config: Dict):
        """Update the summary section in Config sheet"""
        try:
            config_sheet = spreadsheet.worksheet('Config')
            summary_data = [
                ['Last Run', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                ['Total Channels Analyzed', total_found],
                ['NEW Kids Channels Added', new_added],
                ['Search Terms Used', ', '.join(config['search_terms'])]
            ]
            config_sheet.update('D1', summary_data)
        except Exception as e:
            print(f"Error updating summary: {e}")
    
    def search_channels(self, query: str, max_results: int = 100) -> List[str]:
        """Search for channels and return channel IDs with pagination support and error handling"""
        url = f"{self.base_url}/search"
        channel_ids = []
        next_page_token = None
        results_per_page = min(50, max_results)  # API max is 50 per request
        
        while len(channel_ids) < max_results:
            # Calculate how many results we still need
            remaining_results = max_results - len(channel_ids)
            current_page_size = min(results_per_page, remaining_results)
            
            params = {
                'part': 'snippet',
                'type': 'channel',
                'q': query,
                'maxResults': current_page_size,
                'key': self.youtube_api_key
            }
            
            # Add pagination token if we have one
            if next_page_token:
                params['pageToken'] = next_page_token
            
            try:
                response = requests.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract channel IDs from this page
                    for item in data['items']:
                        if len(channel_ids) < max_results:
                            channel_ids.append(item['snippet']['channelId'])
                    
                    # Check if there are more pages
                    next_page_token = data.get('nextPageToken')
                    
                    # If no more pages or we have enough results, break
                    if not next_page_token or len(channel_ids) >= max_results:
                        break
                        
                elif response.status_code == 403:
                    error_data = response.json()
                    if 'quotaExceeded' in str(error_data):
                        print(f"❌ QUOTA EXCEEDED for search term '{query}'. Stopping searches.")
                        break
                    else:
                        print(f"❌ API Error for '{query}': {response.status_code} - {error_data}")
                        break
                        
                else:
                    print(f"❌ HTTP Error for '{query}': {response.status_code}")
                    break
                    
            except Exception as e:
                print(f"❌ Exception searching for '{query}': {e}")
                break
                
            # Add delay between pagination requests
            import time
            time.sleep(1.0)  # Increased delay
        
        return channel_ids[:max_results]  # Ensure we don't exceed the requested amount

    def run_analysis(self):
        """Main analysis workflow with quota management"""
        print("Starting YouTube kids channel analysis...")
        
        # Get configuration from sheets
        config = self.get_input_from_sheets()
        print(f"Search terms: {config['search_terms']}")
        print(f"Total search terms: {len(config['search_terms'])}")
        
        all_channel_ids = set()
        search_count = 0
        
        # Search for channels using each term with quota monitoring
        for i, term in enumerate(config['search_terms']):
            print(f"\n[{i+1}/{len(config['search_terms'])}] Searching for: '{term}'")
            
            try:
                channel_ids = self.search_channels(term, config['max_results_per_term'])
                
                if not channel_ids:
                    print(f"⚠️ No results for '{term}' - might have hit API limit")
                    # Check if we should stop due to quota
                    if search_count > 20:  # If we've done 20+ searches and getting no results
                        print("🛑 Likely hit API quota limit. Proceeding with channels found so far.")
                        break
                else:
                    all_channel_ids.update(channel_ids)
                    print(f"✅ Found {len(channel_ids)} channels for '{term}' (Total unique: {len(all_channel_ids)})")
                
                search_count += 1
                
                # Add delay between search terms to avoid rate limiting
                import time
                time.sleep(1.5)
                
            except Exception as e:
                print(f"❌ Error searching for '{term}': {e}")
                continue
        
        print(f"\n📊 Search phase complete!")
        print(f"Total unique channels found: {len(all_channel_ids)}")
        
        if not all_channel_ids:
            print("❌ No channels found to analyze. Check API quota or search terms.")
            return
        
        # Get existing channels to avoid duplicates
        print("🔍 Checking for existing channels...")
        existing_channel_ids = self.get_existing_channels()
        
        # Filter out channels we've already analyzed
        new_channel_ids = [cid for cid in all_channel_ids if cid not in existing_channel_ids]
        print(f"📈 New channels to analyze: {len(new_channel_ids)} (Skipping {len(all_channel_ids) - len(new_channel_ids)} existing)")
        
        if not new_channel_ids:
            print("✅ No new channels to analyze - all channels were already in database!")
            return
        
        # Analyze channels in small batches with frequent saves
        batch_size = 50  # Reduced batch size
        total_added = 0
        
        for i in range(0, len(new_channel_ids), batch_size):
            batch = list(new_channel_ids)[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(new_channel_ids) + batch_size - 1) // batch_size
            
            print(f"\n🔄 Processing Batch {batch_num}/{total_batches} ({len(batch)} channels)")
            
            batch_results = []
            for j, channel_id in enumerate(batch):
                global_index = i + j + 1
                
                if global_index % 10 == 1:  # Print every 10th channel
                    print(f"Analyzing channel {global_index}/{len(new_channel_ids)}")
                
                try:
                    result = self.analyze_channel(channel_id)
                    batch_results.append(result)
                    
                    # Add delay to avoid rate limiting
                    import time
                    time.sleep(0.2)
                    
                except Exception as e:
                    print(f"❌ Error analyzing channel {channel_id}: {e}")
                    # Check if this is a quota error
                    if 'quotaExceeded' in str(e) or '403' in str(e):
                        print("🛑 Hit API quota during analysis. Saving progress and stopping.")
                        break
                    continue
            
            # Filter and write this batch to sheets immediately
            filtered_batch = [
                r for r in batch_results 
                if (r.get('kids_content_score', 0) >= config['min_kids_score'] 
                    and 'error' not in r)
            ]
            
            if filtered_batch:
                try:
                    print(f"💾 Writing {len(filtered_batch)} kids channels to Google Sheets...")
                    self.write_batch_to_sheets(filtered_batch)
                    total_added += len(filtered_batch)
                    print(f"✅ Successfully wrote batch {batch_num}. Running total: {total_added} kids channels added.")
                except Exception as e:
                    print(f"❌ Error writing batch to sheets: {e}")
                    # Try to continue with next batch
            else:
                print(f"⚠️ No qualifying kids channels in batch {batch_num}")
            
            print(f"📊 Batch {batch_num} complete. Processed {i + len(batch)}/{len(new_channel_ids)} channels.")
            
            # Add longer delay between batches
            import time
            time.sleep(2.0)
        
        print(f"\n🎉 Analysis complete! Added {total_added} new kids channels total.")
        
        # Update final summary
        try:
            sheet_id = os.environ['GOOGLE_SHEET_ID']
            spreadsheet = self.gc.open_by_key(sheet_id)
            self.update_summary(spreadsheet, len(new_channel_ids), total_added, config)
        except Exception as e:
            print(f"Error updating final summary: {e}")
    
    def write_batch_to_sheets(self, batch_results: List[Dict]):
        """Write a batch of results to Google Sheets immediately"""
        sheet_id = os.environ['GOOGLE_SHEET_ID']
        spreadsheet = self.gc.open_by_key(sheet_id)
        
        # Get or create Results worksheet
        try:
            results_sheet = spreadsheet.worksheet('Results')
        except gspread.WorksheetNotFound:
            results_sheet = spreadsheet.add_worksheet(title='Results', rows=5000, cols=10)
            # Add headers for new sheet
            headers = [
                'Channel ID', 'Channel Title', 'Channel URL', 'Subscriber Count',
                'Video Count', 'Kids Score', 'Matched Keywords', 'Likely Kids Content',
                'Analysis Date'
            ]
            results_sheet.update('A1', [headers])
        
        # Prepare data for new channels
        new_rows = []
        for result in batch_results:
            row = [
                result.get('channel_id', ''),
                result.get('channel_title', ''),
                result.get('channel_url', ''),
                result.get('subscriber_count', 0),
                result.get('video_count', 0),
                result.get('kids_content_score', 0),
                result.get('matched_keywords', ''),
                'Yes' if result.get('likely_kids_content', False) else 'No',
                result.get('analysis_date', '')
            ]
            new_rows.append(row)
        
        if new_rows:
            # Find the next empty row
            all_values = results_sheet.get_all_values()
            next_row = len(all_values) + 1
            
            # Update starting from the next empty row
            range_name = f'A{next_row}'
            results_sheet.update(range_name, new_rows)

if __name__ == "__main__":
    analyzer = YouTubeSheetsAnalyzer()
    analyzer.run_analysis()
