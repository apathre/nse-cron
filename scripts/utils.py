import pandas as pd
import smtplib
import gspread
import numpy as np 
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os
from google.oauth2.service_account import Credentials
import time

# Load environment variables from .env file
load_dotenv()

# Define the correct scopes
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# Fetch the private key and handle the case where it's missing
private_key = os.getenv('GOOGLE_PRIVATE_KEY')
if private_key is None:
    raise ValueError("The GOOGLE_PRIVATE_KEY environment variable is not set or is incorrect.")

# Replace \n with actual newlines
private_key = private_key.replace('\\n', '\n')

# Print environment variables for debugging
#print("GOOGLE_PROJECT_ID:", os.getenv('GOOGLE_PROJECT_ID'))
#print("GOOGLE_PROJECT_KEY_ID:", os.getenv('GOOGLE_PROJECT_KEY_ID'))
#print("GOOGLE_PRIVATE_KEY:", private_key)
#print("GOOGLE_CLIENT_EMAIL:", os.getenv('GOOGLE_CLIENT_EMAIL'))
#print("GOOGLE_TOKEN_URI:", os.getenv('GOOGLE_TOKEN_URI'))

# Create a dictionary that represents the credentials
credentials_info = {
    "private_key": private_key,
    "type": "service_account",
    "project_id": os.getenv('GOOGLE_PROJECT_ID'),
    "private_key_id": os.getenv('GOOGLE_PROJECT_KEY_ID'),
    "client_email": os.getenv('GOOGLE_CLIENT_EMAIL'),
    "client_id": "100932991345744246437",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": os.getenv('GOOGLE_TOKEN_URI'),
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "your-client-x509-cert-url",
    "universe_domain": "googleapis.com"
}

#print("Environment Variables:")
#for key, value in os.environ.items():
#    print(f"{key}: {value}")
#print("info:", credentials_info)
  

# Initialize credentials using the dictionary
creds = Credentials.from_service_account_info(credentials_info, scopes=scope)

def calculate_emas(stock_data, short_periods, long_periods):
    short_emas = [stock_data['Close'].ewm(span=period).mean() for period in short_periods]
    long_emas = [stock_data['Close'].ewm(span=period).mean() for period in long_periods]
    return short_emas, long_emas

def check_crossover(short_emas, long_emas):
    for short_ema, long_ema in zip(short_emas, long_emas):
        if short_ema.iloc[-1] > long_ema.iloc[-1] and short_ema.iloc[-2] <= long_ema.iloc[-2]:
            return True
    return False

def send_email_alert(filtered_stocks, stock_data, short_emas, long_emas):
    sender_email = "pathreaig@gmail.com"
    receiver_email = "adi.iitk@gmail.com"
    subject = "Stock Alert - Trading Opportunities"
    
    # Create the email body with detailed stock information
    body = "The following stocks are ready for a long position:\n\n"
    
    for stock, data, short_ema_set, long_ema_set in zip(filtered_stocks, stock_data, short_emas, long_emas):
        body += f"Stock: {stock}\n"
        body += f"Current Price: {data['Close'].iloc[-1]:.2f}\n"
        for i, ema in enumerate(short_ema_set):
            body += f"EMA{i+1} (Short): {ema.iloc[-1]:.2f}\n"
        for i, ema in enumerate(long_ema_set):
            body += f"EMA{i+7} (Long): {ema.iloc[-1]:.2f}\n"
        body += "\n"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    print("mesg body: ", body)

    # Send the email
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender_email, "Xbox@123&4")
        server.send_message(msg)

def convert_data_types(data):
    """
    Convert numpy data types to native Python types.
    """
    return [int(x) if isinstance(x, np.integer) else float(x) if isinstance(x, np.floating) else x for x in data]

def add_row_to_google_sheets(data):
    #scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    #creds = ServiceAccountCredentials.from_json_keyfile_name("google_sheets_credentials.json", scope)
    
    max_retries = 5
    retry_delay = 1  # Start with 1 second
    client = gspread.authorize(creds)

    for attempt in range(max_retries):
        try:
            sheet = client.open("GMMA trading sheet").sheet1
            
            # Get current date and time
            current_date = datetime.now().strftime('%Y-%m-%d')
            current_time = datetime.now().strftime('%H:%M:%S')

            # Prepend the date and time to the data
            data_with_timestamp = [current_date, current_time] + data
            
            # Convert data types to native Python types
            data_with_timestamp = convert_data_types(data_with_timestamp)

            # Add data row to Google Sheet
            sheet.append_row(data_with_timestamp)
            print("Row added successfully")
            return

        except gspread.exceptions.APIError as e:
            if e.response.status_code == 429:
                print(f"Quota exceeded, retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print(f"API Error: {e}")
                return
        except gspread.SpreadsheetNotFound:
            print("Spreadsheet not found. Please check the name and sharing permissions.")
            return
        except Exception as e:
            print(f"Unexpected error: {e}")
            return