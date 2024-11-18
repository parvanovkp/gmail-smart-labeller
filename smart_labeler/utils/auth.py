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
        
        # Create config directory in user's home
        self.CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.gmail-smart-labeler')
        self.TOKEN_PATH = os.path.join(self.CONFIG_DIR, 'token.pickle')
        self.CREDENTIALS_PATH = os.path.join(self.CONFIG_DIR, 'credentials.json')
        
        # Ensure config directory exists
        os.makedirs(self.CONFIG_DIR, exist_ok=True)

    def get_gmail_service(self):
        """Get authenticated Gmail service with better error handling"""
        creds = None

        try:
            # Try to load existing credentials
            if os.path.exists(self.TOKEN_PATH):
                with open(self.TOKEN_PATH, 'rb') as token:
                    creds = pickle.load(token)

            # If credentials are invalid or don't exist, handle authentication
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    print("Refreshing expired credentials...")
                    creds.refresh(Request())
                else:
                    # Check if credentials file exists
                    if not os.path.exists(self.CREDENTIALS_PATH):
                        raise FileNotFoundError(
                            f"\nCredentials file not found at {self.CREDENTIALS_PATH}\n"
                            "Please follow these steps:\n"
                            "1. Go to Google Cloud Console\n"
                            "2. Create a project and enable Gmail API\n"
                            "3. Create OAuth 2.0 credentials\n"
                            "4. Download the credentials JSON file\n"
                            f"5. Save it to: {self.CREDENTIALS_PATH}"
                        )
                    
                    print("Initiating OAuth2 authorization flow...")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.CREDENTIALS_PATH, self.SCOPES)
                    creds = flow.run_local_server(port=0)

                # Save valid credentials
                with open(self.TOKEN_PATH, 'wb') as token:
                    pickle.dump(creds, token)
                print("Credentials saved successfully.")

            return build('gmail', 'v1', credentials=creds)

        except Exception as e:
            print(f"\nAuthentication error: {str(e)}")
            if "credentials" in str(e).lower():
                print("\nMake sure you have:")
                print("1. Created a project in Google Cloud Console")
                print("2. Enabled the Gmail API")
                print("3. Created OAuth 2.0 credentials")
                print("4. Downloaded the credentials JSON file")
                print(f"5. Saved it as: {self.CREDENTIALS_PATH}")
            raise