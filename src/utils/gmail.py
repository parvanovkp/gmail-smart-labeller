# src/utils/gmail.py

from base64 import urlsafe_b64decode
import email
import json

class GmailUtils:
    def __init__(self, service):
        self.service = service

    def get_email_content(self, message_id):
        """Get email content with robust error handling"""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

            # Initialize email data
            email_data = {
                'id': message_id,
                'subject': 'No Subject',
                'from': 'No Sender',
                'body': 'No Content'
            }

            # Get headers
            headers = message.get('payload', {}).get('headers', [])
            for header in headers:
                name = header.get('name', '').lower()
                if name == 'subject':
                    email_data['subject'] = header.get('value', 'No Subject')
                elif name == 'from':
                    email_data['from'] = header.get('value', 'No Sender')

            # Get body
            payload = message.get('payload', {})
            body = ''

            # Function to extract body from payload
            def get_body_from_payload(part):
                if 'body' in part and 'data' in part['body']:
                    return urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                return ''

            # Check for multipart
            if 'parts' in payload:
                # First try to find text/plain
                for part in payload['parts']:
                    mime_type = part.get('mimeType', '')
                    if 'text/plain' in mime_type:
                        body = get_body_from_payload(part)
                        break
                
                # If no text/plain, try text/html
                if not body:
                    for part in payload['parts']:
                        mime_type = part.get('mimeType', '')
                        if 'text/html' in mime_type:
                            body = get_body_from_payload(part)
                            break
            else:
                # Single part message
                body = get_body_from_payload(payload)

            email_data['body'] = body if body else 'No Content'
            return email_data

        except Exception as e:
            print(f"Error getting email content for message {message_id}: {str(e)}")
            return None

    def create_label(self, name, parent_label_id=None):
        """Create a Gmail label with proper error handling"""
        try:
            # First check if label exists
            existing_labels = self.service.users().labels().list(userId='me').execute()
            for label in existing_labels.get('labels', []):
                if label['name'] == (f"{parent_label_id}/{name}" if parent_label_id else name):
                    print(f"Label '{name}' already exists, using existing label")
                    return label

            # Create new label
            label_object = {
                'name': f"{parent_label_id}/{name}" if parent_label_id else name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }
            
            result = self.service.users().labels().create(
                userId='me',
                body=label_object
            ).execute()
            return result
            
        except Exception as e:
            print(f"Error creating label {name}: {str(e)}")
            return None

    def apply_label(self, message_id, label_id):
        """Apply a label to an email"""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': [label_id]}
            ).execute()
            return True
        except Exception as e:
            print(f"Error applying label to message {message_id}: {str(e)}")
            return False

    def remove_label(self, message_id, label_id):
        """Remove a label from an email"""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': [label_id]}
            ).execute()
            return True
        except Exception as e:
            print(f"Error removing label from message {message_id}: {str(e)}")
            return False

    def get_or_create_label(self, name, parent_label_id=None):
        """Get existing label or create new one"""
        try:
            # First try to get existing label
            existing_labels = self.service.users().labels().list(userId='me').execute()
            full_name = f"{parent_label_id}/{name}" if parent_label_id else name
            
            for label in existing_labels.get('labels', []):
                if label['name'] == full_name:
                    return label
            
            # If not found, create new label
            return self.create_label(name, parent_label_id)
            
        except Exception as e:
            print(f"Error getting/creating label {name}: {str(e)}")
            return None