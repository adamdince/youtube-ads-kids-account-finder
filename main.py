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
                'max_results_per_term': 50,
                'min_kids_score': 3
            }
    
    def search_channels(self, query: str, max_results: int = 50) -> List[str]:
        """Search for channels and return channel IDs"""
        url = f"{self.base_url}/search"
        params = {
            'part': 'snippet',
            'type': 'channel',
            'q': query,
            'maxResults': max_results,
            'key': self.youtube_api_key
        }
        
        response = requests.get(url, params=params)
        channel_ids = []
        
        if response.status_code == 200:
            data = response.json()
            for item in data['items']:
                channel_ids.append(item['snippet']['channelId'])
        
        return channel_ids
    
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
    
    def write_results_to_sheets(self, results: List[Dict], config: Dict):
        """Write analysis results to Google Sheets"""
        sheet_id = os.environ['GOOGLE_SHEET_ID']
        spreadsheet = self.gc.open_by_key(sheet_id)
        
        # Create or get Results worksheet
        try:
            results_sheet = spreadsheet.worksheet('Results')
            results_sheet.clear()
        except gspread.WorksheetNotFound:
            results_sheet = spreadsheet.add_worksheet(title='Results', rows=1000, cols=10)
        
        # Filter results based on minimum score
        filtered_results = [
            r for r in results 
            if r.get('kids_content_score', 0) >= config['min_kids_score'] and 'error' not in r
        ]
        
        # Prepare data for sheets
        headers = [
            'Channel ID', 'Channel Title', 'Channel URL', 'Subscriber Count',
            'Video Count', 'Kids Score', 'Matched Keywords', 'Likely Kids Content',
            'Analysis Date'
        ]
        
        data = [headers]
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
            data.append(row)
        
        # Write to sheet
        results_sheet.update('A1', data)
        
        # Update summary in Config sheet
        try:
            config_sheet = spreadsheet.worksheet('Config')
            summary_data = [
                ['Last Run', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                ['Total Channels Found', len(results)],
                ['Kids Channels Found', len(filtered_results)],
                ['Search Terms Used', ', '.join(config['search_terms'])]
            ]
            config_sheet.update('D1', summary_data)
        except:
            pass
        
        print(f"Written {len(filtered_results)} kids channels to Google Sheets")
    
    def run_analysis(self):
        """Main analysis workflow"""
        print("Starting YouTube kids channel analysis...")
        
        # Get configuration from sheets
        config = self.get_input_from_sheets()
        print(f"Search terms: {config['search_terms']}")
        
        all_channel_ids = set()
        
        # Search for channels using each term
        for term in config['search_terms']:
            print(f"Searching for channels with term: {term}")
            channel_ids = self.search_channels(term, config['max_results_per_term'])
            all_channel_ids.update(channel_ids)
            print(f"Found {len(channel_ids)} channels for '{term}'")
        
        print(f"Total unique channels to analyze: {len(all_channel_ids)}")
        
        # Analyze each channel
        results = []
        for i, channel_id in enumerate(all_channel_ids):
            if i % 10 == 0:
                print(f"Analyzing channel {i+1}/{len(all_channel_ids)}")
            
            result = self.analyze_channel(channel_id)
            results.append(result)
        
        # Write results to sheets
        self.write_results_to_sheets(results, config)
        
        print("Analysis complete!")

if __name__ == "__main__":
    analyzer = YouTubeSheetsAnalyzer()
    analyzer.run_analysis()
