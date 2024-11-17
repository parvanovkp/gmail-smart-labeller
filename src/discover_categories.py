# src/discover_categories.py

from dotenv import load_dotenv
import os
from openai import OpenAI
from utils.auth import GmailAuthenticator
from utils.gmail import GmailUtils
from tqdm import tqdm
import json
import sys
import argparse
from collections import defaultdict
import re
from typing import Dict, List, Optional

class CategoryDiscoverer:
    def __init__(self):
        """Initialize the category discoverer"""
        # Initialize OpenAI
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        self.openai = OpenAI(api_key=api_key)
        
        # Initialize Gmail
        auth = GmailAuthenticator()
        self.gmail_service = auth.get_gmail_service()
        self.gmail_utils = GmailUtils(self.gmail_service)
        
        # Data collection structures
        self.emails_by_category = defaultdict(list)
        self.sender_patterns = defaultdict(int)
        self.subject_patterns = defaultdict(int)
        self.content_patterns = defaultdict(int)
        
        # Statistics tracking
        self.stats = {
            'total_emails': 0,
            'analyzed': 0,
            'errors': 0,
            'category_counts': defaultdict(int),
            'patterns': {
                'senders': {},
                'subjects': {},
                'content_types': {}
            }
        }

    def analyze_inbox(self, batch_size: int = 500) -> Optional[Dict]:
        """Analyze inbox to discover natural categories"""
        print("\nAnalyzing inbox to discover email patterns...")
        
        try:
            page_token = None
            processed = 0
            
            while True:
                results = self.gmail_service.users().messages().list(
                    userId='me',
                    maxResults=batch_size,
                    labelIds=['INBOX'],
                    pageToken=page_token
                ).execute()
                
                messages = results.get('messages', [])
                if not messages:
                    break
                
                with tqdm(total=len(messages),
                         desc=f"Analyzing emails {processed + 1}-{processed + len(messages)}") as pbar:
                    for message in messages:
                        try:
                            email_content = self.gmail_utils.get_email_content(message['id'])
                            if email_content:
                                self._analyze_patterns(email_content)
                                self.stats['analyzed'] += 1
                            else:
                                self.stats['errors'] += 1
                            
                            pbar.update(1)
                            processed += 1
                            
                        except Exception as e:
                            print(f"\nError processing message: {str(e)}")
                            self.stats['errors'] += 1
                            pbar.update(1)
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            self.stats['total_emails'] = processed
            
            # Generate categories based on analysis
            print("\nAnalyzing patterns to suggest categories...")
            categories = self._suggest_categories()
            
            if categories:
                self._save_categories(categories)
                return categories
            
        except Exception as e:
            print(f"Error during analysis: {str(e)}")
            return None

    def _analyze_patterns(self, email: Dict) -> None:
        """Analyze patterns in email metadata and content"""
        # Track sender patterns
        sender = email.get('from', '').lower()
        if '@' in sender:
            domain = sender.split('@')[1]
            self.sender_patterns[domain] += 1
        
        # Track subject patterns
        subject = email.get('subject', '').lower()
        keywords = [
            'order', 'invoice', 'receipt', 'confirm', 'alert', 
            'security', 'update', 'newsletter', 'subscription',
            'payment', 'account', 'login', 'important', 'urgent',
            'report', 'meeting', 'reminder', 'invitation'
        ]
        for keyword in keywords:
            if keyword in subject:
                self.subject_patterns[keyword] += 1
        
        # Track content patterns
        body = email.get('body', '').lower()
        content_types = [
            ('notification', r'(notify|alert|warning)'),
            ('newsletter', r'(newsletter|subscribe|unsubscribe)'),
            ('transaction', r'(order|payment|invoice|receipt)'),
            ('authentication', r'(login|password|security|verify)'),
            ('social', r'(friend|connect|follow|share)'),
            ('calendar', r'(meeting|appointment|schedule)'),
        ]
        
        for ctype, pattern in content_types:
            if re.search(pattern, body):
                self.content_patterns[ctype] += 1

    def _suggest_categories(self) -> Optional[Dict]:
        """Suggest main categories based on analysis"""
        # Update stats with pattern analysis
        self.stats['patterns']['senders'] = dict(
            sorted(self.sender_patterns.items(), key=lambda x: x[1], reverse=True)[:10]
        )
        self.stats['patterns']['subjects'] = dict(
            sorted(self.subject_patterns.items(), key=lambda x: x[1], reverse=True)[:10]
        )
        self.stats['patterns']['content_types'] = dict(
            sorted(self.content_patterns.items(), key=lambda x: x[1], reverse=True)
        )

        # Create the example JSON structure separately
        json_example = '''
        {
            "categories": {
                "CategoryName": {
                    "description": "Clear description",
                    "examples": ["Example 1", "Example 2", "Example 3"],
                    "priority": "high/medium/low",
                    "rules": ["Rule 1", "Rule 2"]
                }
            }
        }
        '''

        # Build the prompt in parts
        prompt = f"""
        Analyze these email patterns from {self.stats['total_emails']} emails and suggest
        6-10 clear, distinct categories for organizing emails under a 'Smart' label.

        Patterns found:
        Top Sender Domains:
        {json.dumps(self.stats['patterns']['senders'], indent=2)}

        Common Subject Patterns:
        {json.dumps(self.stats['patterns']['subjects'], indent=2)}

        Content Types:
        {json.dumps(self.stats['patterns']['content_types'], indent=2)}

        Create categories that:
        1. Cover all major types of emails
        2. Are clearly distinct from each other
        3. Make email management practical and efficient
        4. Consider both frequency and importance
        5. Are simple and intuitive to understand

        For each category provide:
        - Clear description of what belongs
        - 3-5 specific examples
        - Priority level (high/medium/low)
        - Clear rules for classification

        Return as JSON in this format:
        {json_example}
        """

        try:
            response = self.openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an email organization expert. Suggest clear, practical categories."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            print(f"Error suggesting categories: {str(e)}")
            return None

    def _save_categories(self, categories: Dict) -> None:
        """Save discovered categories and analysis results"""
        config = {
            "label_prefix": "Smart",
            "categories": categories['categories'],
            "classification_prompt": """
            Analyze this email and categorize it into EXACTLY ONE of these categories:
            
            {categories}
            
            Classification Rules:
            1. Each email must be assigned to exactly one category
            2. Consider both sender and content for classification
            3. When in doubt between categories, choose the higher priority one
            4. Consider the specific rules provided for each category
            
            Email Content:
            From: {sender}
            Subject: {subject}
            Body excerpt: {body}
            
            Return ONLY the category name, nothing else.
            """,
            "batch_size": 500
        }
        
        try:
            # Save configuration
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=2)
            print("\nDiscovered categories saved to config.json")
            
            # Save analysis statistics
            with open('discovery_stats.json', 'w') as f:
                json.dump(self.stats, f, indent=2)
            
            # Print summary
            print("\nAnalysis Results:")
            print(f"Total emails analyzed: {self.stats['total_emails']}")
            print(f"Successfully processed: {self.stats['analyzed']}")
            print(f"Errors encountered: {self.stats['errors']}")
            
            # Print category structure
            print("\nDiscovered Categories:")
            for category, details in categories['categories'].items():
                print(f"\n{category}:")
                print(f"  Description: {details['description']}")
                print(f"  Priority: {details['priority']}")
                print("  Rules:")
                for rule in details['rules']:
                    print(f"    - {rule}")
                
        except Exception as e:
            print(f"\nError saving results: {str(e)}")

def main():
    parser = argparse.ArgumentParser(
        description='Discover email categories based on inbox analysis'
    )
    parser.add_argument(
        '--batch-size', 
        type=int, 
        default=500,
        help='Number of emails to process in each batch'
    )
    args = parser.parse_args()
    
    load_dotenv()
    discoverer = CategoryDiscoverer()
    categories = discoverer.analyze_inbox(batch_size=args.batch_size)
    
    if categories:
        print("\nCategory discovery complete!")
        print("Next steps:")
        print("1. Review the analysis in discovery_stats.json")
        print("2. Review and edit categories in config.json")
        print("3. Run the labeling script: python smart_labeler.py")

if __name__ == "__main__":
    main()