from pathlib import Path
import yaml
import os
from dotenv import load_dotenv
from openai import OpenAI
from typing import Dict, Optional
from .utils.auth import GmailAuthenticator
from .utils.gmail import GmailUtils
from tqdm import tqdm

CONFIG_DIR = Path(__file__).parent / 'config'
CONFIG_PATH = CONFIG_DIR / 'categories.yaml'
PARENT_LABEL = "Smart Labels"

class GmailLabeler:
    def __init__(self):
        """Initialize Gmail and OpenAI clients"""
        load_dotenv()
        
        # Initialize OpenAI
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        self.openai = OpenAI(api_key=api_key)
        
        # Initialize Gmail
        auth = GmailAuthenticator()
        self.gmail_service = auth.get_gmail_service()
        self.gmail_utils = GmailUtils(self.gmail_service)
        
        # Ensure config directory exists
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Ensure parent label exists
        self._ensure_parent_label_exists()

    def _ensure_parent_label_exists(self):
        """Create the parent Smart Labels label if it doesn't exist"""
        self.gmail_utils.get_or_create_label(PARENT_LABEL)

    def analyze(self) -> None:
        """Analyze inbox and generate category suggestions"""
        try:
            # Delete existing Smart labels if any
            if CONFIG_PATH.exists():
                self._delete_existing_labels()
            
            # Analyze inbox patterns
            patterns = self._analyze_patterns()
            
            # Generate categories using OpenAI
            categories = self._generate_categories(patterns)
            
            # Save to YAML
            self._save_config(categories)
            
        except Exception as e:
            raise Exception(f"Analysis failed: {str(e)}")

    def _analyze_patterns(self) -> Dict:
        """Analyze inbox for email patterns"""
        patterns = {
            'senders': {},
            'subjects': {},
            'content_types': {}
        }
        
        # Get sample of recent emails
        messages = self.gmail_utils.get_all_messages(max_results=500)
        
        print("📊 Analyzing email patterns...")
        for msg_id in tqdm(messages, desc="Processing emails", unit="email"):
            email = self.gmail_utils.get_email_content(msg_id)
            if email:
                # Analyze sender
                sender = email.get('from', '').lower()
                if '@' in sender:
                    domain = sender.split('@')[1]
                    patterns['senders'][domain] = patterns['senders'].get(domain, 0) + 1
                
                # Analyze subject patterns
                subject = email.get('subject', '').lower()
                keywords = [
                    'order', 'invoice', 'receipt', 'confirm', 'alert', 
                    'security', 'update', 'newsletter', 'subscription',
                    'payment', 'account', 'login', 'important', 'urgent',
                    'report', 'meeting', 'reminder', 'invitation'
                ]
                for keyword in keywords:
                    if keyword in subject:
                        patterns['subjects'][keyword] = patterns['subjects'].get(keyword, 0) + 1
                
                # Analyze content types
                body = email.get('body', '').lower()
                content_types = [
                    ('transaction', ['order', 'payment', 'invoice', 'receipt']),
                    ('notification', ['notify', 'alert', 'warning']),
                    ('newsletter', ['newsletter', 'subscribe', 'unsubscribe']),
                    ('authentication', ['login', 'password', 'security', 'verify']),
                    ('social', ['connect', 'follow', 'share', 'join']),
                    ('calendar', ['meeting', 'appointment', 'schedule'])
                ]
                
                for ctype, keywords in content_types:
                    if any(keyword in body for keyword in keywords):
                        patterns['content_types'][ctype] = patterns['content_types'].get(ctype, 0) + 1
        
        # Sort patterns by frequency
        for key in patterns:
            patterns[key] = dict(sorted(patterns[key].items(), key=lambda x: x[1], reverse=True)[:10])
        
        return patterns

    def _generate_categories(self, patterns: Dict) -> Dict:
        """Generate category suggestions using OpenAI"""
        prompt = f"""
        Analyze these email patterns and suggest 6-8 clear, distinct categories.
        Each category should be simple and non-overlapping.

        Patterns found:
        {yaml.dump(patterns, sort_keys=False)}

        Create a YAML structure with these fields for each category:
        categories:
          category_name:
            description: Brief description
            priority: high/medium/low

        Rules:
        1. Categories must be distinct with no overlap
        2. Use single-word or hyphenated names
        3. Each category needs only a brief description (1-2 lines max)
        4. Use only valid YAML without any markdown formatting
        """

        try:
            response = self.openai.chat.completions.create(
                model="gpt-4-0125-preview",
                messages=[
                    {"role": "system", "content": "You are a YAML generator. Output only valid YAML without markdown formatting or code blocks."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )

            content = response.choices[0].message.content.strip()
            # Remove any markdown formatting if present
            if content.startswith('```'):
                content = '\n'.join(content.split('\n')[1:-1])
            
            return yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise Exception(f"Invalid YAML in response: {str(e)}")
        except Exception as e:
            raise Exception(f"Error generating categories: {str(e)}")

    def _save_config(self, categories: Dict) -> None:
        """Save categories to YAML config file"""
        try:
            with open(CONFIG_PATH, 'w') as f:
                yaml.safe_dump(categories, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            raise Exception(f"Failed to save config: {str(e)}")

    def label(self, dry_run: bool = False) -> Dict:
        """Label emails using current configuration"""
        if not CONFIG_PATH.exists():
            raise FileNotFoundError("No configuration file found")

        try:
            # Load configuration
            with open(CONFIG_PATH, 'r') as f:
                config = yaml.safe_load(f)

            # Generate classification prompt
            prompt_template = self._generate_prompt(config)

            # Get unlabeled emails
            unlabeled = self._get_unlabeled_emails()
            total_emails = len(unlabeled)

            if total_emails == 0:
                print("✨ No new emails to label!")
                return {"processed": 0, "labeled": 0, "errors": 0}

            stats = {
                'processed': 0,
                'labeled': 0,
                'errors': 0
            }

            print(f"🏷️  Processing {total_emails} emails...")
            
            # Create progress bar
            with tqdm(total=total_emails, desc="Labeling emails", unit="email") as pbar:
                for email_id in unlabeled:
                    email = self.gmail_utils.get_email_content(email_id)
                    if not email:
                        stats['errors'] += 1
                        pbar.update(1)
                        continue

                    category = self._classify_email(email, prompt_template)
                    if category and not dry_run:
                        if self._apply_label(email_id, category):
                            stats['labeled'] += 1

                    stats['processed'] += 1
                    pbar.update(1)
                    
                    # Update progress bar description with current stats
                    pbar.set_postfix(labeled=stats['labeled'], errors=stats['errors'])

            return stats

        except Exception as e:
            raise Exception(f"Labeling failed: {str(e)}")

    def _generate_prompt(self, config: Dict) -> str:
        """Generate efficient classification prompt from config"""
        categories = []
        for name, details in config['categories'].items():
            categories.append(f"{name}: {details['description']}")
        
        categories_text = ' | '.join(categories)
        
        return f'''
        Categorize this email into EXACTLY ONE of these categories:
        {categories_text}

        Rules:
        1. Choose exactly one category
        2. When in doubt, choose the higher priority category
        3. Be decisive - no explanations needed

        Email:
        From: {{sender}}
        Subject: {{subject}}
        Body excerpt: {{body}}

        Return ONLY the category name, nothing else.
        '''

    def _apply_label(self, email_id: str, category: str) -> bool:
        """Apply label to email"""
        try:
            # Create the full label path under Smart Labels/category
            label = self.gmail_utils.get_or_create_label(category, PARENT_LABEL)
            if label:
                return self.gmail_utils.apply_label(email_id, label['id'])
            return False
        except Exception as e:
            print(f"Error applying label: {str(e)}")
            return False

    def _delete_existing_labels(self) -> None:
        """Delete all existing Smart labels"""
        try:
            # Only delete child labels, keep the parent
            labels = self.gmail_service.users().labels().list(userId='me').execute()
            for label in labels.get('labels', []):
                if label['name'].startswith(f"{PARENT_LABEL}/"):
                    self.gmail_service.users().labels().delete(
                        userId='me', id=label['id']
                    ).execute()
        except Exception as e:
            print(f"Error deleting labels: {str(e)}")

    def _get_unlabeled_emails(self) -> list:
        """Get list of emails without Smart labels"""
        # Get all emails with Smart labels
        labeled = set()
        labels = self.gmail_service.users().labels().list(userId='me').execute()
        for label in labels.get('labels', []):
            if label['name'].startswith(f"{PARENT_LABEL}/"):
                messages = self.gmail_utils.get_messages_with_label(label['id'])
                labeled.update(messages)

        # Get all inbox messages
        all_messages = set(self.gmail_utils.get_all_messages(label_ids=['INBOX']))
        
        # Return unlabeled messages
        return list(all_messages - labeled)

    def _classify_email(self, email: Dict, prompt_template: str) -> Optional[str]:
        """Classify single email"""
        try:
            formatted_prompt = prompt_template.format(
                sender=email.get('from', 'Unknown'),
                subject=email.get('subject', 'No Subject'),
                body=email.get('body', '')[:300]
            )

            response = self.openai.chat.completions.create(
                model="gpt-4-0125-preview",
                messages=[
                    {"role": "system", "content": "You are an email classifier. Return only the category name."},
                    {"role": "user", "content": formatted_prompt}
                ],
                temperature=0.1,
                max_tokens=10
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Classification error: {str(e)}")
            return None