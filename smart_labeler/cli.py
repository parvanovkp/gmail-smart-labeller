import click
import os
import sys
import subprocess
from pathlib import Path
from tqdm import tqdm
from dotenv import load_dotenv, set_key
import logging
from .logger import setup_logger
from .core import GmailLabeler

CONFIG_DIR = Path(__file__).parent / 'config'
CONFIG_PATH = CONFIG_DIR / 'categories.yaml'
USER_CONFIG_DIR = Path.home() / '.gmail-smart-labeler'
ENV_PATH = USER_CONFIG_DIR / '.env'

# Setup logger
logger = setup_logger(USER_CONFIG_DIR)

def get_editor():
    """Get the default system editor"""
    return os.environ.get('EDITOR', 'vim' if os.name == 'posix' else 'notepad')

@click.group()
def cli():
    """Gmail Smart Label - Organize your inbox with smart categories."""
    pass

@cli.command()
def configure():
    """Configure OpenAI API key."""
    # Ensure user config directory exists
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    logger.info("Starting configuration process")
    
    # Check if API key already exists
    load_dotenv(ENV_PATH)
    existing_key = os.getenv('OPENAI_API_KEY')
    
    if existing_key:
        logger.info("Existing API key found")
        if not click.confirm('OpenAI API key already exists. Do you want to update it?'):
            logger.info("Configuration cancelled by user")
            return

    # Get API key from user
    api_key = click.prompt('Please enter your OpenAI API key', type=str, hide_input=True)
    
    # Validate API key format (basic check)
    if not api_key.startswith('sk-') or len(api_key) < 20:
        logger.error("Invalid API key format provided")
        click.echo('❌ Invalid API key format. Key should start with "sk-" and be longer.')
        return

    # Save to .env file
    try:
        set_key(str(ENV_PATH), 'OPENAI_API_KEY', api_key)
        logger.info("API key saved successfully")
        click.echo('✅ API key saved successfully!')
        click.echo(f'Configuration saved to: {ENV_PATH}')
    except Exception as e:
        logger.error(f"Error saving API key: {str(e)}", exc_info=True)
        click.echo(f'❌ Error saving API key: {str(e)}')
        return

@cli.command()
def analyze():
    """Analyze inbox and generate category suggestions."""
    logger.info("Starting analyze command")
    
    if CONFIG_PATH.exists():
        logger.warning("Existing configuration found")
        if not click.confirm('⚠️  This will delete existing Smart labels and generate new categories. Continue?'):
            logger.info("Analysis cancelled by user")
            click.echo('Operation cancelled.')
            return

    try:
        logger.info("Initializing GmailLabeler")
        labeler = GmailLabeler()
        
        with click.progressbar(
            length=3,
            label='🔍 Analyzing inbox',
            show_eta=True,
            show_percent=True,
            fill_char='▰',
            empty_char='▱'
        ) as bar:
            logger.info("Starting email analysis")
            click.echo('Fetching emails...')
            bar.update(1)
            
            labeler.analyze()
            bar.update(1)
            
            logger.info("Generating categories")
            click.echo('Generating categories...')
            bar.update(1)
            
        logger.info("Analysis completed successfully")
        click.echo('✅ Categories generated and saved to config.')
        click.echo('\nRun "gmail-smart-label setup" to review and edit categories.')
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        click.echo(f'❌ Error during analysis: {str(e)}', err=True)
        sys.exit(1)

@cli.command()
def setup():
    """Review and edit category configuration."""
    logger.info("Starting setup command")
    
    if not CONFIG_PATH.exists():
        logger.error("No configuration file found")
        click.echo('❌ No configuration file found. Run "gmail-smart-label analyze" first.', err=True)
        return

    editor = get_editor()
    try:
        logger.info(f"Opening config in {editor}")
        click.echo(f'📝 Opening config in {editor}...')
        subprocess.call([editor, str(CONFIG_PATH)])
        logger.info("Configuration updated")
        click.echo('✅ Configuration updated.')
    except Exception as e:
        logger.error(f"Error opening editor: {str(e)}", exc_info=True)
        click.echo(f'❌ Error opening editor: {str(e)}', err=True)
        sys.exit(1)

@cli.command()
@click.option('--dry-run', is_flag=True, help='Show what would be labeled without making changes.')
def label(dry_run):
    """Label emails using current configuration."""
    logger.info(f"Starting label command (dry-run: {dry_run})")
    
    if not CONFIG_PATH.exists():
        logger.error("No configuration file found")
        click.echo('❌ No configuration file found. Run "gmail-smart-label analyze" first.', err=True)
        return

    try:
        logger.info("Initializing GmailLabeler")
        labeler = GmailLabeler()
        click.echo('🏷️  Starting email labeling...')
        
        if dry_run:
            logger.info("Running in dry-run mode")
            click.echo('(Dry run mode - no changes will be made)')
        
        stats = labeler.label(dry_run=dry_run)
        
        logger.info(f"Labeling complete - Processed: {stats['processed']}, "
                   f"Labeled: {stats['labeled']}, Errors: {stats['errors']}")
        
        click.echo('\n✅ Labeling complete!')
        click.echo(f"Processed: {stats['processed']} emails")
        click.echo(f"Labeled: {stats['labeled']} emails")
        if stats.get('errors', 0) > 0:
            click.echo(f"Errors: {stats['errors']}")
        
    except Exception as e:
        logger.error(f"Labeling failed: {str(e)}", exc_info=True)
        click.echo(f'❌ Error during labeling: {str(e)}', err=True)
        sys.exit(1)

def main():
    """Main entry point for the CLI."""
    try:
        logger.info("Starting gmail-smart-label CLI")
        cli()
    except KeyboardInterrupt:
        logger.warning("Operation cancelled by user (KeyboardInterrupt)")
        click.echo('\n⚠️  Operation cancelled by user.')
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        click.echo(f'❌ Unexpected error: {str(e)}', err=True)
        sys.exit(1)

if __name__ == '__main__':
    main()