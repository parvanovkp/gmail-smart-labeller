# Gmail Smart Labeler

Gmail Smart Labeler is a command-line tool that helps you organize your Gmail inbox using intelligent categorization and automated labeling. It analyzes your email patterns and leverages OpenAI's language models to suggest meaningful labels for your emails, allowing you to keep your inbox tidy and easily find important messages.

## Key Features

- **Automatic Email Categorization**: The tool analyzes your inbox and generates smart category suggestions based on common email patterns, such as senders, subjects, and content types.
- **Customizable Categories**: You can review and edit the suggested categories to ensure they match your needs and preferences.
- **Automated Labeling**: Once the categories are set up, the tool can automatically apply the appropriate labels to your incoming emails, keeping your inbox organized.
- **Dry Run Mode**: The tool provides a dry run mode to show you what labels would be applied without actually modifying your emails.

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/gmail-smart-labeler.git
   ```
2. Navigate to the project directory:
   ```
   cd gmail-smart-labeler
   ```
3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Configuration

1. Configure the OpenAI API key:
   ```
   gmail-smart-label configure
   ```
   This will prompt you to enter your OpenAI API key, which is required for the categorization process.

2. (Optional) Review and edit the generated categories:
   ```
   gmail-smart-label setup
   ```
   This will open the category configuration file in your default text editor, allowing you to customize the categories as needed.

## Usage

1. Analyze your inbox and generate category suggestions:
   ```
   gmail-smart-label analyze
   ```
   This will scan your inbox, identify common patterns, and suggest a set of categories to use for labeling your emails.

2. Apply the labels to your emails:
   ```
   gmail-smart-label label
   ```
   This will apply the labels to your unlabeled emails based on the configured categories.

   You can also run this in "dry run" mode to see the labels that would be applied without actually modifying your emails:
   ```
   gmail-smart-label label --dry-run
   ```

## Contributing

Contributions to this project are welcome. If you find any issues or have suggestions for improvements, please feel free to open an issue or submit a pull request.

## License

This project is licensed under the [MIT License](LICENSE).