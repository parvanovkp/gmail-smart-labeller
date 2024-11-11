# src/utils/auth.py

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle

class GmailAuthenticator:
    def __init__(self, scopes=None):
        """Initialize authenticator with custom scopes"""
        default_scopes = [
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/gmail.labels'
        ]
        self.SCOPES = scopes if scopes else default_scopes
        self.TOKEN_PATH = 'credentials/token.pickle'
        self.CREDENTIALS_PATH = 'credentials/credentials.json'

    def get_gmail_service(self):
        """Get authenticated Gmail service with better error handling"""
        creds = None

        try:
            # Delete existing token if it exists to force new authentication
            if os.path.exists(self.TOKEN_PATH):
                os.remove(self.TOKEN_PATH)
                print("Removed old credentials to ensure proper permissions")

            # If no valid credentials available, let user login
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # Check if credentials file exists
                    if not os.path.exists(self.CREDENTIALS_PATH):
                        raise FileNotFoundError(
                            f"Credentials file not found at {self.CREDENTIALS_PATH}. "
                            "Please download your OAuth 2.0 credentials from Google Cloud Console "
                            "and save them as 'credentials/credentials.json'"
                        )
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.CREDENTIALS_PATH, self.SCOPES)
                    creds = flow.run_local_server(port=0)

                # Ensure credentials directory exists
                os.makedirs(os.path.dirname(self.TOKEN_PATH), exist_ok=True)
                
                # Save the credentials for the next run
                with open(self.TOKEN_PATH, 'wb') as token:
                    pickle.dump(creds, token)

            return build('gmail', 'v1', credentials=creds)

        except Exception as e:
            print(f"Authentication error: {str(e)}")
            if "credentials" in str(e).lower():
                print("\nMake sure you have:")
                print("1. Created a project in Google Cloud Console")
                print("2. Enabled the Gmail API")
                print("3. Created OAuth 2.0 credentials")
                print("4. Downloaded the credentials JSON file")
                print("5. Saved it as 'credentials/credentials.json'")
            raise