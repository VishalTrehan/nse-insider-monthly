#!/usr/bin/env python3
"""
NSE Insider Trades - Newsletter Sender Bot
Automatically sends monthly insider trading reports to subscribers
"""

import os
import sys
import gspread
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SubscriberManager:
    """Manages subscriber list from Google Sheets"""
    
    def __init__(self, sheet_id, credentials_json):
        """Initialize with sheet ID and credentials"""
        self.sheet_id = sheet_id
        self.credentials_json = credentials_json
        self.gc = None
        self.sheet = None
        
    def authenticate(self):
        """Authenticate with Google Sheets API"""
        try:
            # Parse credentials from environment variable (GitHub Actions)
            import json
            creds_dict = json.loads(self.credentials_json)
            creds = Credentials.from_service_account_info(
                creds_dict,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            self.gc = gspread.authorize(creds)
            logger.info("✓ Authenticated with Google Sheets API")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to authenticate: {str(e)}")
            return False
    
    def load_subscribers(self):
        """Load subscriber emails from Google Sheet"""
        try:
            self.sheet = self.gc.open_by_key(self.sheet_id)
            worksheet = self.sheet.get_worksheet(0)  # First sheet
            
            # Get all data
            data = worksheet.get_all_values()
            
            subscribers = []
            if len(data) > 1:  # Skip header
                for row in data[1:]:
                    if len(row) >= 2 and row[1]:  # Email in column B
                        subscribers.append({
                            'email': row[1].strip(),
                            'source': row[2] if len(row) > 2 else 'Unknown',
                            'name': row[3] if len(row) > 3 else 'Subscriber'
                        })
            
            logger.info(f"✓ Loaded {len(subscribers)} subscribers")
            return subscribers
        except Exception as e:
            logger.error(f"✗ Failed to load subscribers: {str(e)}")
            return []

class NewsletterSender:
    """Sends newsletter emails to subscribers"""
    
    def __init__(self, gmail_address, app_password):
        """Initialize with Gmail credentials"""
        self.gmail_address = gmail_address
        self.app_password = app_password
        self.sent_count = 0
        self.failed_count = 0
    
    def send_newsletter(self, subscriber_email, subscriber_name, report_content):
        """Send newsletter to individual subscriber"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.gmail_address
            msg['To'] = subscriber_email
            msg['Subject'] = f"NSE Insider Trades Report - {datetime.now().strftime('%B %Y')}"
            
            # Email body
            email_body = f"""Hello {subscriber_name},

Thank you for subscribing to NSE Insider Trading Analysis!

Here's your exclusive monthly insider trading report:

{report_content}

---
This comprehensive analysis is exclusively for our subscribers.
For more updates, visit our subscription page:
https://docs.google.com/forms/d/1BtlBVG0ULykK1swjHwOQVDHmUD26yG_K3HqCoG41GBQ/

Best Regards,
NSE Insider Trades Team
            """
            
            part = MIMEText(email_body, 'plain')
            msg.attach(part)
            
            # Send email
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
            server.login(self.gmail_address, self.app_password)
            server.send_message(msg)
            server.quit()
            
            self.sent_count += 1
            logger.info(f"✓ Email sent to {subscriber_email}")
            return True
        except Exception as e:
            self.failed_count += 1
            logger.error(f"✗ Failed to send email to {subscriber_email}: {str(e)}")
            return False
    
    def send_batch(self, subscribers, report_content):
        """Send newsletter to all subscribers"""
        logger.info(f"\n📧 Sending newsletters to {len(subscribers)} subscribers...\n")
        
        for subscriber in subscribers:
            self.send_newsletter(
                subscriber['email'],
                subscriber['name'],
                report_content
            )
        
        logger.info(f"\n✓ Newsletter campaign complete!")
        logger.info(f"  - Sent: {self.sent_count}")
        logger.info(f"  - Failed: {self.failed_count}\n")

def get_report_content():
    """Generate report content from CSV files"""
    try:
        report = "NSE INSIDER TRADING REPORT\n"
        report += f"Generated: {datetime.now().strftime('%B %d, %Y')}\n\n"
        
        # Try to read from buy_summary.csv
        if os.path.exists('buy_summary.csv'):
            report += "TOP BUYS (Insider Transactions):\n"
            with open('buy_summary.csv', 'r') as f:
                report += f.read()
            report += "\n\n"
        
        # Try to read from sell_summary.csv
        if os.path.exists('sell_summary.csv'):
            report += "TOP SELLS (Insider Transactions):\n"
            with open('sell_summary.csv', 'r') as f:
                report += f.read()
            report += "\n\n"
        
        if not os.path.exists('buy_summary.csv') and not os.path.exists('sell_summary.csv'):
            report += "No trading data available for this period.\n"
        
        return report
    except Exception as e:
        logger.error(f"Failed to generate report: {str(e)}")
        return "Report generation failed. Please check logs."

def main():
    """Main workflow"""
    logger.info("\n" + "="*60)
    logger.info("NSE Insider Trades - Newsletter Sender")
    logger.info("="*60 + "\n")
    
    # Get credentials from environment
    subscribers_sheet_id = os.getenv('SUBSCRIBERS_SHEET_ID')
    gmail_user = os.getenv('GMAIL_USER', 'ra.vishal.trehan@gmail.com')
    gmail_app_password = os.getenv('GMAIL_APP_PASSWORD')
    google_credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
    
    # Validate inputs
    if not all([subscribers_sheet_id, gmail_app_password, google_credentials_json]):
        logger.error("✗ Missing required environment variables:")
        if not subscribers_sheet_id:
            logger.error("  - SUBSCRIBERS_SHEET_ID")
        if not gmail_app_password:
            logger.error("  - GMAIL_APP_PASSWORD")
        if not google_credentials_json:
            logger.error("  - GOOGLE_CREDENTIALS_JSON")
        sys.exit(1)
    
    logger.info("✓ Environment variables loaded\n")
    
    # Load subscribers
    logger.info("📋 Loading subscribers from Google Sheet...")
    manager = SubscriberManager(subscribers_sheet_id, google_credentials_json)
    if not manager.authenticate():
        logger.error("✗ Failed to authenticate with Google Sheets")
        sys.exit(1)
    
    subscribers = manager.load_subscribers()
    if not subscribers:
        logger.warning("⚠ No subscribers found")
        return
    
    # Generate report
    logger.info("\n📊 Generating insider trading report...")
    report_content = get_report_content()
    
    # Send newsletters
    sender = NewsletterSender(gmail_user, gmail_app_password)
    sender.send_batch(subscribers, report_content)
    
    logger.info("\n" + "="*60)
    logger.info("✓ Workflow completed successfully!")
    logger.info("="*60 + "\n")

if __name__ == "__main__":
    main()
