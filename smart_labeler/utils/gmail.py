from base64 import urlsafe_b64decode
import email
import json
from typing import Dict, Optional, Set, List
from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

class GmailUtils:
    def __init__(self, service: Resource):
        """Initialize Gmail utilities
        
        Args:
            service: Authenticated Gmail API service resource
        """
        self.service = service

    def get_email_content(self, message_id: str) -> Optional[Dict[str, str]]:
        """Get email content with robust error handling
        
        Args:
            message_id: The ID of the message to retrieve
            
        Returns:
            Dictionary containing email data or None if error
        """
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

            email_data = {
                'id': message_id,
                'subject': 'No Subject',
                'from': 'No Sender',
                'body': 'No Content'
            }

            headers = message.get('payload', {}).get('headers', [])
            for header in headers:
                name = header.get('name', '').lower()
                if name == 'subject':
                    email_data['subject'] = header.get('value', 'No Subject')
                elif name == 'from':
                    email_data['from'] = header.get('value', 'No Sender')

            payload = message.get('payload', {})
            body = ''

            def get_body_from_payload(part: Dict) -> str:
                if 'body' in part and 'data' in part['body']:
                    return urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                return ''

            if 'parts' in payload:
                for part in payload['parts']:
                    mime_type = part.get('mimeType', '')
                    if 'text/plain' in mime_type:
                        body = get_body_from_payload(part)
                        break
                
                if not body:
                    for part in payload['parts']:
                        mime_type = part.get('mimeType', '')
                        if 'text/html' in mime_type:
                            body = get_body_from_payload(part)
                            break
            else:
                body = get_body_from_payload(payload)

            email_data['body'] = body if body else 'No Content'
            return email_data

        except HttpError as e:
            print(f"Gmail API error getting message {message_id}: {str(e)}")
            return None
        except Exception as e:
            print(f"Error processing message {message_id}: {str(e)}")
            return None

    def create_label(self, name: str, parent_label_id: Optional[str] = None) -> Optional[Dict]:
        """
        Create a Gmail label with proper error handling
        
        Args:
            name: Name of the label to create
            parent_label_id: Optional parent label for hierarchy
            
        Returns:
            Label object or None if error
        """
        try:
            # First check if label exists
            existing_labels = self.service.users().labels().list(userId='me').execute()
            full_name = f"{parent_label_id}/{name}" if parent_label_id else name
            
            for label in existing_labels.get('labels', []):
                if label['name'] == full_name:
                    return label

            # Create new label
            label_object = {
                'name': full_name,
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

    def apply_label(self, message_id: str, label_id: str) -> bool:
        """
        Apply a label to an email
        
        Args:
            message_id: ID of the message to label
            label_id: ID of the label to apply
            
        Returns:
            Boolean indicating success
        """
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

    def remove_label(self, message_id: str, label_id: str) -> bool:
        """
        Remove a label from an email
        
        Args:
            message_id: ID of the message to modify
            label_id: ID of the label to remove
            
        Returns:
            Boolean indicating success
        """
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

    def get_messages_with_label(self, label_id: str, max_results: Optional[int] = None) -> Set[str]:
        """
        Get all message IDs with a specific label
        
        Args:
            label_id: ID of the label to search for
            max_results: Optional maximum number of results to return
            
        Returns:
            Set of message IDs
        """
        messages = set()
        try:
            page_token = None
            while True:
                results = self.service.users().messages().list(
                    userId='me',
                    labelIds=[label_id],
                    maxResults=min(500, max_results) if max_results else 500,
                    pageToken=page_token
                ).execute()
                
                if 'messages' in results:
                    messages.update(msg['id'] for msg in results['messages'])
                    
                    # Check if we've reached max_results
                    if max_results and len(messages) >= max_results:
                        return set(list(messages)[:max_results])
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                    
            return messages
            
        except Exception as e:
            print(f"Error getting messages for label {label_id}: {str(e)}")
            return set()

    def get_or_create_label(self, name: str, parent_label_id: Optional[str] = None) -> Optional[Dict]:
        """
        Get existing label or create new one
        
        Args:
            name: Name of the label
            parent_label_id: Optional parent label for hierarchy
            
        Returns:
            Label object or None if error
        """
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

    def get_all_messages(self, label_ids: Optional[List[str]] = None, 
                        max_results: Optional[int] = None) -> Set[str]:
        """
        Get all message IDs matching specified criteria
        
        Args:
            label_ids: Optional list of label IDs to filter by
            max_results: Optional maximum number of results to return
            
        Returns:
            Set of message IDs
        """
        messages = set()
        try:
            page_token = None
            while True:
                results = self.service.users().messages().list(
                    userId='me',
                    labelIds=label_ids,
                    maxResults=min(500, max_results) if max_results else 500,
                    pageToken=page_token
                ).execute()
                
                if 'messages' in results:
                    messages.update(msg['id'] for msg in results['messages'])
                    
                    # Check if we've reached max_results
                    if max_results and len(messages) >= max_results:
                        return set(list(messages)[:max_results])
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                    
            return messages
            
        except Exception as e:
            print(f"Error getting messages: {str(e)}")
            return set()