# src/apply_labels.py

from dotenv import load_dotenv
import os
import sys
from utils.auth import GmailAuthenticator
from utils.gmail import GmailUtils
from openai import OpenAI
from tqdm import tqdm
import json
import argparse
from typing import Dict, Optional, Set

class EmailLabeler:
    def __init__(self, config_path: str = 'config.json'):
        """Initialize the email labeler with configuration"""
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize Gmail
        auth = GmailAuthenticator(scopes=['https://www.googleapis.com/auth/gmail.modify'])
        self.gmail_service = auth.get_gmail_service()
        self.gmail_utils = GmailUtils(self.gmail_service)
        
        # Initialize OpenAI
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        self.openai = OpenAI(api_key=api_key)
        
        # Initialize statistics
        self.stats = {
            'processed': 0,
            'labeled': 0,
            'errors': 0,
            'category_counts': {},
            'actions': {
                'labels_created': [],
                'existing_labels': [],
                'failed_categorizations': []
            }
        }

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from file"""
        try:
            if not os.path.exists(config_path):
                raise FileNotFoundError(
                    f"Configuration file not found at {config_path}. "
                    "Please run discover_categories.py first."
                )
            
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Validate configuration
            required_keys = ['label_prefix', 'categories', 'classification_prompt']
            if not all(key in config for key in required_keys):
                raise ValueError("Invalid configuration file structure")
            
            print("\nLoaded categories:")
            for category in config['categories']:
                print(f"- {category}")
            
            return config
            
        except Exception as e:
            print(f"Error loading configuration: {str(e)}")
            sys.exit(1)

    def create_label_structure(self) -> Dict[str, str]:
        """Create Gmail label hierarchy based on configuration"""
        created_labels = {}
        
        try:
            # Create main Smart label
            main_label = self.gmail_utils.create_label(self.config['label_prefix'])
            if main_label:
                print(f"\nCreated/Found main '{self.config['label_prefix']}' label")
                self.stats['actions']['existing_labels'].append(main_label['id'])
                
                # Create category labels
                for category in self.config['categories']:
                    label = self.gmail_utils.create_label(
                        category, 
                        parent_label_id=self.config['label_prefix']
                    )
                    if label:
                        created_labels[category] = label['id']
                        action = 'Found' if label['id'] in self.stats['actions']['existing_labels'] else 'Created'
                        print(f"{action} label: {self.config['label_prefix']}/{category}")
                        
                        if action == 'Created':
                            self.stats['actions']['labels_created'].append(
                                f"{self.config['label_prefix']}/{category}"
                            )
            
            return created_labels
            
        except Exception as e:
            print(f"Error creating label structure: {str(e)}")
            return {}

    def categorize_email(self, email_content: Dict) -> Optional[str]:
        """Categorize email using OpenAI"""
        try:
            # Prepare category descriptions for prompt
            category_descriptions = []
            for cat, details in self.config['categories'].items():
                description = (
                    f"{cat}:\n"
                    f"  Description: {details['description']}\n"
                    f"  Examples: {', '.join(details['examples'])}\n"
                    f"  Priority: {details['priority']}\n"
                    f"  Rules: {', '.join(details['rules'])}"
                )
                category_descriptions.append(description)
            
            # Format the classification prompt
            prompt = self.config['classification_prompt'].format(
                categories='\n'.join(category_descriptions),
                sender=email_content.get('from', 'Unknown'),  # Changed from 'from_' to 'sender'
                subject=email_content.get('subject', 'No Subject'),
                body=email_content.get('body', '')[:300]
            )

            response = self.openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an email categorization assistant. Return ONLY the category name."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            
            category = response.choices[0].message.content.strip()
            if category not in self.config['categories']:
                self.stats['actions']['failed_categorizations'].append({
                    'email': {
                        'from': email_content.get('from'),
                        'subject': email_content.get('subject')
                    },
                    'suggested_category': category
                })
                return None
            return category
            
        except Exception as e:
            print(f"\nError in categorization: {str(e)}")
            return None

    def process_inbox(self, max_emails: Optional[int] = None) -> None:
        """Process and label emails in inbox"""
        try:
            print("\nInitializing Smart Labeler...")
            
            # Create label structure
            labels = self.create_label_structure()
            if not labels:
                raise Exception("Failed to create label structure")
            
            # Get existing labeled messages to avoid duplicates
            labeled_messages: Set[str] = set()
            print("\nGetting existing labeled messages...")
            for label_id in labels.values():
                messages = self.gmail_utils.get_messages_with_label(label_id)
                labeled_messages.update(messages)
            print(f"Found {len(labeled_messages)} already labeled messages")
            
            # Process emails with pagination
            processed = 0
            page_token = None
            
            while True:
                # Get batch of emails
                results = self.gmail_service.users().messages().list(
                    userId='me',
                    labelIds=['INBOX'],
                    maxResults=min(
                        self.config.get('batch_size', 500),
                        max_emails - processed if max_emails else self.config.get('batch_size', 500)
                    ),
                    pageToken=page_token
                ).execute()
                
                messages = results.get('messages', [])
                if not messages:
                    print("No more messages to process.")
                    break
                
                # Filter out already labeled messages
                messages = [msg for msg in messages if msg['id'] not in labeled_messages]
                
                # Process batch
                with tqdm(total=len(messages), 
                         desc=f"Processing emails {processed + 1}-{processed + len(messages)}") as pbar:
                    for message in messages:
                        try:
                            # Skip if already labeled
                            if message['id'] in labeled_messages:
                                continue
                            
                            # Get email content
                            email_content = self.gmail_utils.get_email_content(message['id'])
                            if not email_content:
                                self.stats['errors'] += 1
                                continue
                            
                            # Categorize email
                            category = self.categorize_email(email_content)
                            if not category:
                                self.stats['errors'] += 1
                                continue
                            
                            # Apply label
                            if category in labels:
                                # Remove any existing Smart labels first
                                for label_id in labels.values():
                                    self.gmail_utils.remove_label(message['id'], label_id)
                                
                                # Apply new label
                                if self.gmail_utils.apply_label(message['id'], labels[category]):
                                    self.stats['labeled'] += 1
                                    self.stats['category_counts'][category] = \
                                        self.stats['category_counts'].get(category, 0) + 1
                                    labeled_messages.add(message['id'])
                            
                            self.stats['processed'] += 1
                            pbar.update(1)
                            processed += 1
                            
                            # Check if reached max_emails
                            if max_emails and processed >= max_emails:
                                print(f"\nReached maximum number of emails ({max_emails})")
                                break
                            
                        except Exception as e:
                            print(f"\nError processing message: {str(e)}")
                            self.stats['errors'] += 1
                            pbar.update(1)
                
                # Get next page token
                page_token = results.get('nextPageToken')
                if not page_token or (max_emails and processed >= max_emails):
                    break
            
            # Save final statistics
            self._save_stats()
            
        except Exception as e:
            print(f"Error processing inbox: {str(e)}")

    def _save_stats(self) -> None:
        """Save processing statistics"""
        stats_file = 'labeling_stats.json'
        try:
            with open(stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
            print(f"\nStatistics saved to {stats_file}")
            
            # Print summary
            print("\nProcessing Summary:")
            print(f"Processed: {self.stats['processed']} emails")
            print(f"Successfully labeled: {self.stats['labeled']} emails")
            print(f"Errors: {self.stats['errors']}")
            print("\nCategory Distribution:")
            for category, count in self.stats['category_counts'].items():
                print(f"{category}: {count} ({count/self.stats['labeled']*100:.1f}%)")
            
            if self.stats['actions']['failed_categorizations']:
                print(f"\nWarning: {len(self.stats['actions']['failed_categorizations'])} emails had categorization issues")
                print("Check labeling_stats.json for details")
                
        except Exception as e:
            print(f"\nError saving statistics: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Label emails based on discovered categories')
    parser.add_argument('--max-emails', type=int, help='Maximum number of emails to process')
    parser.add_argument('--config', type=str, default='config.json',
                       help='Path to configuration file')
    args = parser.parse_args()
    
    load_dotenv()
    labeler = EmailLabeler(config_path=args.config)
    labeler.process_inbox(max_emails=args.max_emails)

if __name__ == "__main__":
    main()