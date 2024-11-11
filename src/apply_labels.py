# src/apply_labels.py

from dotenv import load_dotenv
import os
from utils.auth import GmailAuthenticator
from utils.gmail import GmailUtils
from openai import OpenAI
from tqdm import tqdm
import json
import argparse

class EmailLabeler:
    def __init__(self, skip_inbox_for_ads=False):
        """
        Initialize EmailLabeler
        
        Args:
            skip_inbox_for_ads (bool): If True, will remove INBOX label from ads
                                     (effectively archiving them)
        """
        # Initialize Gmail with necessary permissions
        auth = GmailAuthenticator(scopes=['https://www.googleapis.com/auth/gmail.modify'])
        self.gmail_service = auth.get_gmail_service()
        self.gmail_utils = GmailUtils(self.gmail_service)
        
        # Store inbox management preference
        self.skip_inbox_for_ads = skip_inbox_for_ads
        
        # Load OpenAI
        api_key = os.getenv('OPENAI_API_KEY')
        self.openai = OpenAI(api_key=api_key)
        
        # Initialize statistics
        self.stats = {
            'processed': 0,
            'labeled': 0,
            'archived': 0,
            'errors': 0,
            'category_counts': {},
            'actions': {
                'labels_created': [],
                'emails_archived': 0
            }
        }

    def create_label_hierarchy(self):
        """Create label hierarchy with clear structure"""
        created_labels = {}
        
        # Define label structure
        labels = {
            "Ads": "Promotional and marketing emails",
            "Orders": "Purchase and delivery related",
            "Finance": "Banking and financial communications",
            "Auth": "Login and security notifications",
            "Important": "Priority communications"
        }
        
        # Create main Smart folder
        smart_label = self.gmail_utils.create_label("Smart")
        if smart_label:
            print("Created main 'Smart' label")
            
            # Create subcategories
            for category, description in labels.items():
                label = self.gmail_utils.create_label(category, parent_label_id="Smart")
                if label:
                    created_labels[category] = label['id']
                    self.stats['actions']['labels_created'].append(f"Smart/{category}")
                    print(f"Created label: Smart/{category}")
        
        return created_labels

    def categorize_email(self, email_content):
        """Categorize email with strict rules"""
        prompt = f"""
        Categorize this email into EXACTLY ONE of these categories:
        - Ads (ANY promotional content, newsletters, marketing, deals, unless about an active order)
        - Orders (purchase confirmations, shipping updates, delivery notifications)
        - Finance (banking, bills, payments, financial statements)
        - Auth (login confirmations, 2FA codes, security alerts)
        - Important (anything that doesn't fit above but needs attention)

        Strict rules:
        1. If it's promotional/marketing, it MUST be "Ads" even if from a company you buy from
        2. Only use "Orders" for actual purchase communications
        3. "Auth" is for automatic system notifications about logins/security
        4. "Finance" is strictly for money-related communications
        5. If unsure between Ads and something else, prefer Ads

        Email:
        From: {email_content.get('from', 'Unknown')}
        Subject: {email_content.get('subject', 'No Subject')}
        Body excerpt: {email_content.get('body', '')[:300]}...

        Response format: Just the category name, nothing else.
        """

        try:
            response = self.openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a strict email categorizer focused on separating ads from important content."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"\nError in categorization: {str(e)}")
            return None

    def process_inbox(self, max_emails=None, dry_run=False):
        """
        Process and label emails in inbox with pagination support
        
        Args:
            max_emails (int): Maximum number of emails to process (None for all)
            dry_run (bool): If True, only simulate actions without making changes
        """
        try:
            print(f"\nStarting email processing{' (DRY RUN)' if dry_run else ''}:")
            print(f"{'✓' if self.skip_inbox_for_ads else '✗'} Archive ads")
            print(f"Will process {max_emails if max_emails else 'all'} emails\n")
            
            # Create labels (unless dry run)
            labels = self.create_label_hierarchy() if not dry_run else {}
            
            # Initialize pagination variables
            processed_count = 0
            page_token = None
            
            while True:
                # Get next batch of emails
                results = self.gmail_service.users().messages().list(
                    userId='me',
                    labelIds=['INBOX'],
                    maxResults=min(500, max_emails - processed_count if max_emails else 500),
                    pageToken=page_token
                ).execute()
                
                messages = results.get('messages', [])
                if not messages:
                    print("No more messages found.")
                    break
                
                # Update progress bar total for this batch
                with tqdm(total=len(messages), desc=f"Processing emails (batch {processed_count + 1}-{processed_count + len(messages)})") as pbar:
                    # Process emails in current batch
                    for message in messages:
                        try:
                            # Get email content
                            email_content = self.gmail_utils.get_email_content(message['id'])
                            if not email_content:
                                self.stats['errors'] += 1
                                continue
                            
                            # Categorize
                            category = self.categorize_email(email_content)
                            if not category:
                                self.stats['errors'] += 1
                                continue
                            
                            # Update stats
                            self.stats['processed'] += 1
                            self.stats['category_counts'][category] = self.stats['category_counts'].get(category, 0) + 1
                            
                            if not dry_run:
                                # Apply label
                                if category in labels:
                                    if self.gmail_utils.apply_label(message['id'], labels[category]):
                                        self.stats['labeled'] += 1
                                
                                # Handle inbox skipping for ads
                                if self.skip_inbox_for_ads and category == "Ads":
                                    if self.gmail_utils.remove_label(message['id'], 'INBOX'):
                                        self.stats['archived'] += 1
                                        self.stats['actions']['emails_archived'] += 1
                            
                            pbar.update(1)
                            processed_count += 1
                            
                            # Check if we've reached max_emails
                            if max_emails and processed_count >= max_emails:
                                print(f"\nReached maximum number of emails to process ({max_emails})")
                                return
                            
                        except Exception as e:
                            print(f"\nError processing message {message['id']}: {str(e)}")
                            self.stats['errors'] += 1
                            pbar.update(1)
                
                # Check for next page
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            # Save statistics
            self._save_stats()
            
        except Exception as e:
            print(f"Error processing inbox: {str(e)}")

    def _save_stats(self):
        """Save detailed processing statistics"""
        stats_file = 'labeling_stats.json'
        try:
            with open(stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
            print(f"\nStatistics saved to {stats_file}")
            
            # Print summary
            print("\nProcessing Summary:")
            print(f"Processed: {self.stats['processed']} emails")
            print(f"Labeled: {self.stats['labeled']} emails")
            print(f"Archived: {self.stats['archived']} ads")
            print(f"Errors: {self.stats['errors']}")
            print("\nCategory Distribution:")
            for category, count in self.stats['category_counts'].items():
                print(f"{category}: {count}")
                
        except Exception as e:
            print(f"\nError saving statistics: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Process and label Gmail inbox')
    parser.add_argument('--max-emails', type=int, help='Maximum number of emails to process')
    parser.add_argument('--archive-ads', action='store_true', help='Archive ads (remove from inbox)')
    parser.add_argument('--dry-run', action='store_true', help='Simulate without making changes')
    args = parser.parse_args()
    
    load_dotenv()
    labeler = EmailLabeler(skip_inbox_for_ads=args.archive_ads)
    labeler.process_inbox(max_emails=args.max_emails, dry_run=args.dry_run)

if __name__ == "__main__":
    main()