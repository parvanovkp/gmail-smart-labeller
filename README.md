# Gmail Smart Labeler

Gmail Smart Labeler is a command-line tool that automatically organizes your Gmail inbox using AI-powered categorization. It analyzes email patterns and uses OpenAI's language models to intelligently label messages, making inbox management effortless.

## Key Features

- **AI-Powered Categorization**: Automatically analyzes inbox patterns and suggests relevant categories
- **Smart Label Management**: Creates and manages Gmail labels hierarchically
- **Customizable Categories**: Edit and customize suggested categories to match your workflow
- **Dry Run Mode**: Preview label changes before applying them
- **Detailed Logging**: Comprehensive logging with colored console output
- **Batch Processing**: Efficiently processes multiple emails in batches
- **Error Handling**: Robust error handling with helpful error messages

## Prerequisites

- Python 3.8 or higher
- Gmail account
- OpenAI API key
- Google Cloud project with Gmail API enabled

## Installation

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/gmail-smart-labeler.git
   cd gmail-smart-labeler
   ```

2. Install in development mode:
   ```bash
   pip install -e .
   ```

This makes the `gmail-smart-label` command available globally while allowing source code modifications.

## Gmail API Setup

1. Create Google Cloud Project:
   - Visit [Google Cloud Console](https://console.cloud.google.com/)
   - Create new project or select existing one
   - Enable billing (required for API access)

2. Enable Gmail API:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Gmail API"
   - Click "Enable"

3. Configure OAuth Consent:
   - Go to "APIs & Services" > "OAuth consent screen"
   - Select "External" user type
   - Complete required fields:
     - App name
     - User support email
     - Developer contact info
   - Add scopes: `gmail.modify` and `gmail.labels`
   - Add your email as test user if using development credentials

4. Create OAuth Credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Select "Desktop application"
   - Download the credentials JSON file

5. Set Up Credentials:
   ```bash
   mkdir -p ~/.gmail-smart-labeler
   mv ~/Downloads/client_secret_*.json ~/.gmail-smart-labeler/credentials.json
   ```

## Configuration

1. Set up OpenAI API key:
   ```bash
   gmail-smart-label configure
   ```

2. First-time authorization:
   - Run any command (e.g., `gmail-smart-label analyze`)
   - Browser will open for Gmail authorization
   - Grant requested permissions
   - Token is saved automatically for future use

## Usage

### Analyze Inbox

Generate category suggestions based on your email patterns:
```bash
gmail-smart-label analyze
```

### Review Categories

Open category configuration in your default editor:
```bash
gmail-smart-label setup
```

Example category configuration:
```yaml
categories:
  financial:
    description: Banking and financial transactions
    priority: high
  social-network:
    description: Social media notifications
    priority: medium
  newsletters:
    description: Subscription newsletters and updates
    priority: low
```

### Apply Labels

Label emails using configured categories:
```bash
gmail-smart-label label
```

Preview changes without applying:
```bash
gmail-smart-label label --dry-run
```

## Command Reference

- `configure`: Set up OpenAI API key
- `analyze`: Generate category suggestions
- `setup`: Edit category configuration
- `label`: Apply labels to emails
  - Options:
    - `--dry-run`: Preview changes without applying

## Files and Directories

- `~/.gmail-smart-labeler/`
  - `credentials.json`: Google OAuth credentials
  - `token.pickle`: Gmail API access token
  - `.env`: OpenAI API key
  - `logs/`: Application logs

## Troubleshooting

### Common Issues

1. **Authentication Errors**:
   - Ensure `credentials.json` is in the correct location
   - Delete `token.pickle` to re-authenticate
   - Verify you're added as a test user in Google Cloud Console

2. **API Key Issues**:
   - Run `gmail-smart-label configure` to update OpenAI API key
   - Check `.env` file exists in `~/.gmail-smart-labeler/`

3. **Label Creation Failures**:
   - Verify Gmail API scopes include `gmail.modify`
   - Check Google Cloud Console API quotas

### Logging

View detailed logs in `~/.gmail-smart-labeler/logs/`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

Guidelines:
- Follow PEP 8 style guide
- Add tests for new features
- Update documentation as needed

## License

MIT License - See [LICENSE](LICENSE) file for details

## Security

- Credentials are stored locally
- OAuth tokens use restricted scopes
- No email content is stored permanently
- API keys are encrypted in logs

## Support

- Open an issue for bugs or feature requests
- Check existing issues before creating new ones