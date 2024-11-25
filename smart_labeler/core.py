from pathlib import Path
import yaml
import os
from dotenv import load_dotenv
from openai import OpenAI
from typing import Dict, Optional
from .utils.auth import GmailAuthenticator
from .utils.gmail import GmailUtils
from tqdm import tqdm
from .logger import setup_logger

CONFIG_DIR = Path(__file__).parent / 'config'
CONFIG_PATH = CONFIG_DIR / 'categories.yaml'
PARENT_LABEL = "Smart Labels"

class GmailLabeler:
    def __init__(self):
        """Initialize Gmail and OpenAI clients"""
        # Set up logging first
        self.user_config_dir = Path.home() / '.gmail-smart-labeler'
        self.logger = setup_logger(self.user_config_dir)
        
        # Load .env from user config directory
        env_path = self.user_config_dir / '.env'
        load_dotenv(env_path)
        
        # Initialize OpenAI
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            self.logger.critical("OpenAI API key not found. Please run 'gmail-smart-label configure' first.")
            raise ValueError("OpenAI API key not found")
        
        self.logger.info("Initializing services...")
        self.openai = OpenAI(api_key=api_key)
        
        # Initialize Gmail
        auth = GmailAuthenticator()
        self.gmail_service = auth.get_gmail_service()
        self.gmail_utils = GmailUtils(self.gmail_service)
        
        # Ensure config directory exists
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Ensure parent label exists
        self._ensure_parent_label_exists()
        self.logger.info("Initialization complete!")

    def _ensure_parent_label_exists(self):
        """Create the parent Smart Labels label if it doesn't exist"""
        try:
            self.logger.debug(f"Ensuring parent label '{PARENT_LABEL}' exists")
            self.gmail_utils.get_or_create_label(PARENT_LABEL)
        except Exception as e:
            self.logger.error(f"Error creating parent label: {str(e)}")
            raise

    def analyze(self) -> None:
        """Analyze inbox and generate category suggestions"""
        try:
            self.logger.info("Starting inbox analysis...")
            
            # Delete existing Smart labels if any
            if CONFIG_PATH.exists():
                self.logger.info("Deleting existing Smart labels")
                self._delete_existing_labels()
            
            # Analyze inbox patterns
            self.logger.info("Analyzing inbox patterns...")
            patterns = self._analyze_patterns()
            
            # Generate categories using OpenAI
            self.logger.info("Generating categories using OpenAI...")
            categories = self._generate_categories(patterns)
            
            # Save to YAML
            self.logger.info("Saving configuration...")
            self._save_config(categories)
            
            self.logger.info("Analysis completed successfully")
            
        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}", exc_info=True)
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
        self.logger.info(f"Analyzing patterns from {len(messages)} emails")
        
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
        
        self.logger.debug(f"Pattern analysis results: {patterns}")
        return patterns

    def _generate_categories(self, patterns: Dict) -> Dict:
        """Generate category suggestions using OpenAI"""
        self.logger.info("Generating category suggestions")
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
            self.logger.debug("Sending request to OpenAI")
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
            
            categories = yaml.safe_load(content)
            self.logger.info(f"Generated {len(categories.get('categories', {}))} categories")
            return categories
        except yaml.YAMLError as e:
            self.logger.error(f"Invalid YAML in OpenAI response: {str(e)}")
            raise Exception(f"Invalid YAML in response: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error generating categories: {str(e)}")
            raise Exception(f"Error generating categories: {str(e)}")

    def _save_config(self, categories: Dict) -> None:
        """Save categories to YAML config file"""
        try:
            self.logger.info(f"Saving configuration to {CONFIG_PATH}")
            with open(CONFIG_PATH, 'w') as f:
                yaml.safe_dump(categories, f, default_flow_style=False, sort_keys=False)
            self.logger.info("Configuration saved successfully")
        except Exception as e:
            self.logger.error(f"Failed to save config: {str(e)}")
            raise Exception(f"Failed to save config: {str(e)}")

    def label(self, dry_run: bool = False) -> Dict:
        """Label emails using current configuration"""
        if not CONFIG_PATH.exists():
            self.logger.error("No configuration file found")
            raise FileNotFoundError("No configuration file found")

        try:
            self.logger.info("Starting email labeling process")
            
            # Load configuration
            with open(CONFIG_PATH, 'r') as f:
                config = yaml.safe_load(f)
            self.logger.info(f"Loaded {len(config.get('categories', {}))} categories from config")

            # Generate classification prompt
            prompt_template = self._generate_prompt(config)

            # Get unlabeled emails
            unlabeled = self._get_unlabeled_emails()
            total_emails = len(unlabeled)

            if total_emails == 0:
                self.logger.info("No new emails to label")
                return {"processed": 0, "labeled": 0, "errors": 0}

            stats = {
                'processed': 0,
                'labeled': 0,
                'errors': 0
            }

            if dry_run:
                self.logger.info("Running in dry-run mode")
            
            self.logger.info(f"Processing {total_emails} emails...")
            
            with tqdm(total=total_emails, desc="Labeling emails", unit="email") as pbar:
                for email_id in unlabeled:
                    email = self.gmail_utils.get_email_content(email_id)
                    if not email:
                        stats['errors'] += 1
                        self.logger.warning(f"Could not fetch email content for ID: {email_id}")
                        pbar.update(1)
                        continue

                    category = self._classify_email(email, prompt_template)
                    if category and not dry_run:
                        if self._apply_label(email_id, category):
                            stats['labeled'] += 1
                            self.logger.debug(f"Applied category '{category}' to email {email_id}")
                        else:
                            self.logger.warning(f"Failed to apply category '{category}' to email {email_id}")

                    stats['processed'] += 1
                    pbar.update(1)
                    pbar.set_postfix(labeled=stats['labeled'], errors=stats['errors'])

            self.logger.info(f"Labeling complete. Processed: {stats['processed']}, "
                           f"Labeled: {stats['labeled']}, Errors: {stats['errors']}")
            return stats

        except Exception as e:
            self.logger.error(f"Labeling failed: {str(e)}", exc_info=True)
            raise Exception(f"Labeling failed: {str(e)}")

    def _generate_prompt(self, config: Dict) -> str:
        """Generate efficient classification prompt from config"""
        self.logger.debug("Generating classification prompt")
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
            self.logger.debug(f"Applying category '{category}' to email {email_id}")
            # Create the full label path under Smart Labels/category
            label = self.gmail_utils.get_or_create_label(category, PARENT_LABEL)
            if label:
                return self.gmail_utils.apply_label(email_id, label['id'])
            return False
        except Exception as e:
            self.logger.error(f"Error applying label: {str(e)}")
            return False

    def _delete_existing_labels(self) -> None:
        """Delete all existing Smart labels"""
        try:
            self.logger.info("Deleting existing Smart labels")
            # Only delete child labels, keep the parent
            labels = self.gmail_service.users().labels().list(userId='me').execute()
            for label in labels.get('labels', []):
                if label['name'].startswith(f"{PARENT_LABEL}/"):
                    self.logger.debug(f"Deleting label: {label['name']}")
                    self.gmail_service.users().labels().delete(
                        userId='me', id=label['id']
                    ).execute()
            self.logger.info("Existing labels deleted successfully")
        except Exception as e:
            self.logger.error(f"Error deleting labels: {str(e)}")
            raise

    def _get_unlabeled_emails(self) -> list:
        """Get list of emails without Smart labels"""
        try:
            self.logger.debug("Getting list of unlabeled emails")
            # Get all emails with Smart labels
            labeled = set()
            labels = self.gmail_service.users().labels().list(userId='me').execute()
            for label in labels.get('labels', []):
                if label['name'].startswith(f"{PARENT_LABEL}/"):
                    messages = self.gmail_utils.get_messages_with_label(label['id'])
                    labeled.update(messages)

            # Get all inbox messages
            all_messages = set(self.gmail_utils.get_all_messages(label_ids=['INBOX']))
            
            # Get unlabeled messages
            unlabeled = list(all_messages - labeled)
            self.logger.debug(f"Found {len(unlabeled)} unlabeled emails")
            return unlabeled
        except Exception as e:
            self.logger.error(f"Error getting unlabeled emails: {str(e)}")
            raise

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

            category = response.choices[0].message.content.strip()
            self.logger.debug(f"Classified email as: {category}")
            return category

        except Exception as e:
            self.logger.error(f"Classification error: {str(e)}")
            return None