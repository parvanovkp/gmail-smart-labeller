# src/analyze.py

from dotenv import load_dotenv
import os
from openai import OpenAI
from utils.auth import GmailAuthenticator
from utils.gmail import GmailUtils
from tqdm import tqdm
import json
import sys
from collections import Counter

# Load environment variables
load_dotenv()

class EmailAnalyzer:
    def __init__(self):
        # Check for API key
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("Error: OPENAI_API_KEY not found in environment variables")
            print("Please make sure you have a .env file with your OpenAI API key")
            print("Example .env file content:")
            print("OPENAI_API_KEY=sk-your_api_key_here")
            sys.exit(1)
            
        # Initialize Gmail
        auth = GmailAuthenticator()
        self.gmail_service = auth.get_gmail_service()
        self.gmail_utils = GmailUtils(self.gmail_service)
        
        # Initialize OpenAI
        self.openai = OpenAI(api_key=api_key)
        
        self.email_categories = []
        self.processed_count = 0
        self.error_count = 0

    def analyze_inbox(self, sample_size=100):
        """Analyze inbox and suggest label structure"""
        print(f"Analyzing {sample_size} recent emails...")
        
        try:
            results = self.gmail_service.users().messages().list(
                userId='me',
                maxResults=sample_size,
                labelIds=['INBOX']
            ).execute()
            
            messages = results.get('messages', [])
            if not messages:
                print("No messages found.")
                return {"error": "No messages found in inbox"}
            
            for message in tqdm(messages, desc="Processing emails"):
                email_content = self.gmail_utils.get_email_content(message['id'])
                if email_content:
                    category = self._categorize_email(email_content)
                    if category != "Uncategorized":
                        self.email_categories.append(category)
                        self.processed_count += 1
                else:
                    self.error_count += 1
            
            if not self.email_categories:
                return {"error": "No categories could be generated"}
                
            label_structure = self._generate_label_structure()
            self._save_results(label_structure)
            return label_structure
            
        except Exception as e:
            error_msg = f"Error analyzing inbox: {str(e)}"
            print(f"\n{error_msg}")
            return {"error": error_msg}

    def _categorize_email(self, email):
        """Categorize single email with emphasis on marketing detection"""
        prompt = f"""
        First, check if this is a marketing or promotional email (unless it's about an active order).
        Then categorize into ONLY ONE of these categories:

        - Marketing (newsletters, promotions, deals - ANY commercial email not about an active order)
        - Orders (order confirmations, shipping updates, delivery notifications)
        - Work (anything professional or work-related)
        - Personal (friends, family, social)
        - Finance (bills, receipts, banking)
        - Admin (accounts, services, administrative)

        Email:
        From: {email.get('from', 'Unknown')}
        Subject: {email.get('subject', 'No Subject')}
        Body excerpt: {email.get('body', '')[:300]}...

        Categorization rules:
        1. If it's promotional/marketing content, always categorize as "Marketing" even if from a company you've bought from
        2. Only use "Orders" for actual purchase-related communications (confirmations, tracking, delivery)
        3. If unsure between Marketing and Orders, prefer Marketing
        4. Newsletter = Marketing, unless it's a critical service update

        Response must be exactly one category name from the list above, nothing else.
        """

        try:
            response = self.openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": """You are an email categorizer specialized in detecting marketing emails.
                    Always categorize promotional content as Marketing unless it's about an active order.
                    Examples:
                    - "20% off your next purchase" = Marketing
                    - "Your order has shipped" = Orders
                    - "Check out our new products" = Marketing
                    - "Order confirmation" = Orders
                    - "Newsletter" = Marketing
                    - "Weekly deals" = Marketing"""},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,  # Zero temperature for consistent categorization
                max_tokens=10
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"\nError in categorization: {str(e)}")
            return "Uncategorized"

    def _generate_label_structure(self):
        """Generate label structure with focus on marketing separation"""
        if not self.email_categories:
            return {"error": "No categories collected"}

        category_counts = Counter(self.email_categories)
        
        prompt = f"""
        Create a Gmail label structure for these categories:
        {json.dumps(dict(category_counts), indent=2)}

        Include filtering rules to separate:
        1. Marketing emails (promotional content)
        2. Order-related emails (actual purchases)
        3. Everything else by category

        Return a valid JSON structure with filtering suggestions:
        {{
            "Marketing": {{
                "description": "Promotional emails and newsletters",
                "filters": [
                    "subject:(off OR save OR % OR deal OR newsletter)",
                    "from:(*marketing* OR *newsletter* OR *promotions*)"
                ],
                "suggested_action": "Skip Inbox/Archive"
            }},
            "Orders": {{
                "description": "Active purchase communications",
                "filters": [
                    "subject:(order OR tracking OR shipment OR delivered)",
                    "from:(*orders* OR *shipping*)"
                ],
                "suggested_action": "Keep in Inbox"
            }}
        }}
        """

        try:
            response = self.openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Create practical email filters with emphasis on separating marketing from important communications."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            try:
                structure = json.loads(response.choices[0].message.content)
                # Add statistics
                structure["Statistics"] = {
                    "total_processed": self.processed_count,
                    "total_categorized": len(self.email_categories),
                    "errors": self.error_count,
                    "category_distribution": dict(category_counts),
                    "marketing_percentage": (category_counts.get("Marketing", 0) / len(self.email_categories) * 100) if self.email_categories else 0
                }
                return structure
            except json.JSONDecodeError:
                return {
                    "Statistics": {
                        "category_counts": dict(category_counts),
                        "total_emails": len(self.email_categories),
                        "errors": self.error_count
                    }
                }
                
        except Exception as e:
            print(f"Error generating structure: {e}")
            return {"error": str(e)}

    def _save_results(self, label_structure):
        """Save analysis results"""
        try:
            with open('label_structure.json', 'w') as f:
                json.dump(label_structure, f, indent=2)
            print("\nLabel structure saved to label_structure.json")
        except Exception as e:
            print(f"\nError saving results: {str(e)}")

if __name__ == "__main__":
    analyzer = EmailAnalyzer()
    label_structure = analyzer.analyze_inbox(sample_size=100)
    print("\nSuggested Label Structure:")
    print(json.dumps(label_structure, indent=2))