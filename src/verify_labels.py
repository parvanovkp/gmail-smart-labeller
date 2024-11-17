# src/verify_labels.py

from dotenv import load_dotenv
import os
from utils.auth import GmailAuthenticator
from utils.gmail import GmailUtils
from collections import defaultdict

class LabelVerifier:
    def __init__(self):
        auth = GmailAuthenticator()
        self.gmail_service = auth.get_gmail_service()
        self.gmail_utils = GmailUtils(self.gmail_service)
        
    def get_message_ids_by_label(self, label_id):
        """Get all message IDs for a given label"""
        try:
            messages = []
            page_token = None
            
            while True:
                results = self.gmail_service.users().messages().list(
                    userId='me',
                    labelIds=[label_id],
                    pageToken=page_token
                ).execute()
                
                if 'messages' in results:
                    messages.extend(results['messages'])
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                    
            return {msg['id'] for msg in messages}
        except Exception as e:
            print(f"Error getting messages for label {label_id}: {e}")
            return set()

    def verify_counts(self):
        """Verify all message counts and find discrepancies"""
        try:
            # Get all labels
            labels_response = self.gmail_service.users().labels().list(userId='me').execute()
            smart_labels = [label for label in labels_response['labels'] 
                          if label['name'].startswith('Smart/')]
            
            # Get inbox messages
            inbox_messages = self.get_message_ids_by_label('INBOX')
            print(f"\nTotal inbox messages: {len(inbox_messages)}")
            
            # Get messages for each Smart label
            label_messages = {}
            message_labels = defaultdict(list)
            total_labeled = 0
            
            print("\nCounting messages per label:")
            for label in smart_labels:
                messages = self.get_message_ids_by_label(label['id'])
                label_messages[label['name']] = messages
                total_labeled += len(messages)
                print(f"{label['name']}: {len(messages)} messages")
                
                # Track which labels each message has
                for msg_id in messages:
                    message_labels[msg_id].append(label['name'])
            
            # Find messages with multiple labels
            multi_labeled = {
                msg_id: labels for msg_id, labels in message_labels.items() 
                if len(labels) > 1
            }
            
            # Find inbox messages without Smart labels
            unlabeled = {
                msg_id for msg_id in inbox_messages 
                if not any(msg_id in msgs for msgs in label_messages.values())
            }
            
            # Find labeled messages not in inbox
            not_in_inbox = {
                msg_id for label_msgs in label_messages.values() 
                for msg_id in label_msgs 
                if msg_id not in inbox_messages
            }
            
            # Print results
            print("\nAnalysis Results:")
            print(f"Total messages in inbox: {len(inbox_messages)}")
            print(f"Total labeled messages: {total_labeled}")
            print(f"Unique labeled messages: {len(message_labels)}")
            
            if multi_labeled:
                print("\nMessages with multiple labels:")
                for msg_id, labels in multi_labeled.items():
                    msg = self.gmail_service.users().messages().get(
                        userId='me', id=msg_id, format='metadata'
                    ).execute()
                    subject = next(
                        (h['value'] for h in msg['payload']['headers'] 
                         if h['name'].lower() == 'subject'),
                        'No Subject'
                    )
                    print(f"Message '{subject}' has labels: {', '.join(labels)}")
            
            if unlabeled:
                print(f"\nFound {len(unlabeled)} inbox messages without Smart labels")
                
            if not_in_inbox:
                print(f"\nFound {len(not_in_inbox)} labeled messages not in inbox")
                
            # Get detailed counts
            print("\nDetailed counts:")
            for label_name, messages in label_messages.items():
                inbox_count = len(messages & inbox_messages)
                print(f"{label_name}:")
                print(f"  Total messages: {len(messages)}")
                print(f"  In inbox: {inbox_count}")
                print(f"  Not in inbox: {len(messages - inbox_messages)}")

        except Exception as e:
            print(f"Error during verification: {e}")

def main():
    load_dotenv()
    verifier = LabelVerifier()
    verifier.verify_counts()

if __name__ == "__main__":
    main()