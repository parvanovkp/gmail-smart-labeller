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
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    logger.info("Starting configuration process")
    load_dotenv(ENV_PATH)
    existing_key = os.getenv('OPENAI_API_KEY')
    
    if existing_key and not click.confirm('OpenAI API key already exists. Do you want to update it?'):
        return

    api_key = click.prompt('Please enter your OpenAI API key', type=str, hide_input=True)
    
    if not api_key.startswith('sk-') or len(api_key) < 20:
        logger.error("Invalid API key format provided")
        click.echo('❌ Invalid API key format. Key should start with "sk-" and be longer.')
        return

    try:
        set_key(str(ENV_PATH), 'OPENAI_API_KEY', api_key)
        click.echo('✅ API key saved successfully!')
        click.echo(f'Configuration saved to: {ENV_PATH}')
    except Exception as e:
        logger.error(f"Error saving API key: {str(e)}", exc_info=True)
        click.echo(f'❌ Error saving API key: {str(e)}')
        return

@cli.command()
def analyze():
    """Analyze inbox and generate category suggestions."""
    if CONFIG_PATH.exists() and not click.confirm('⚠️  This will delete existing Smart labels and generate new categories. Continue?'):
        return

    try:
        labeler = GmailLabeler()
        with click.progressbar(
            length=3,
            label='🔍 Analyzing inbox',
            show_eta=True,
            show_percent=True,
            fill_char='▰',
            empty_char='▱'
        ) as bar:
            click.echo('Fetching emails...')
            bar.update(1)
            
            labeler.analyze()
            bar.update(1)
            
            click.echo('Generating categories...')
            bar.update(1)
            
        click.echo('✅ Categories generated and saved to config.')
        click.echo('\nRun "gmail-smart-label setup" to review and edit categories.')
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        click.echo(f'❌ Error during analysis: {str(e)}', err=True)
        sys.exit(1)

@cli.command()
def setup():
    """Review and edit category configuration."""
    if not CONFIG_PATH.exists():
        click.echo('❌ No configuration file found. Run "gmail-smart-label analyze" first.', err=True)
        return

    editor = get_editor()
    try:
        click.echo(f'📝 Opening config in {editor}...')
        subprocess.call([editor, str(CONFIG_PATH)])
        click.echo('✅ Configuration updated.')
    except Exception as e:
        logger.error(f"Error opening editor: {str(e)}", exc_info=True)
        click.echo(f'❌ Error opening editor: {str(e)}', err=True)
        sys.exit(1)

@cli.command()
@click.option('--dry-run', is_flag=True, help='Show what would be labeled without making changes.')
def label(dry_run):
    """Label emails using current configuration."""
    if not CONFIG_PATH.exists():
        click.echo('❌ No configuration file found. Run "gmail-smart-label analyze" first.', err=True)
        return

    try:
        labeler = GmailLabeler()
        
        if dry_run:
            click.echo('(Dry run mode - no changes will be made)')
            
        stats = labeler.label(dry_run=dry_run)
        
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
        cli()
    except KeyboardInterrupt:
        click.echo('\n⚠️  Operation cancelled by user.')
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        click.echo(f'❌ Unexpected error: {str(e)}', err=True)
        sys.exit(1)

if __name__ == '__main__':
    main()