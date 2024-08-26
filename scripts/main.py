import json
import yfinance as yf
from flask import Flask, jsonify
from utils import calculate_emas, check_crossover, send_email_alert, add_row_to_google_sheets


app = Flask(__name__)

# Load stock list
with open('scripts/stocks.json', 'r') as f:
    stock_list = json.load(f)['stocks']

def filter_stocks():
    short_periods = [3, 5, 8, 10, 12, 15]
    long_periods = [30, 35, 40, 45, 50, 60]
    filtered_stocks = []
    stock_data_list = []
    short_ema_list = []
    long_ema_list = []

    for stock in stock_list:
        try:
            data = yf.download(stock, period='5d', interval='60m')
            data = data.resample('4H').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()
            
            if data.empty:
                print(f"No data available for {stock}. Skipping.")
                continue
        
            short_emas, long_emas = calculate_emas(data, short_periods, long_periods)

            if check_crossover(short_emas, long_emas):
                filtered_stocks.append(stock)
                stock_data_list.append(data)
                short_ema_list.append(short_emas)
                long_ema_list.append(long_emas)

        except Exception as e:
            print(f"Error processing {stock}: {e}")


    return filtered_stocks, stock_data_list, short_ema_list, long_ema_list

def job():
    filtered_stocks, stock_data, short_emas, long_emas = filter_stocks()
    if filtered_stocks:
        
        #print("data after filter: ", filtered_stocks,stock_data)
        for stock, data, short_ema_set, long_ema_set in zip(filtered_stocks, stock_data, short_emas, long_emas):
            row_data = [
                stock,  # Stock symbol
                data['Open'].iloc[-1],  # Open price
                data['High'].iloc[-1],  # High price
                data['Low'].iloc[-1],  # Low price
                data['Close'].iloc[-1],  # Last price
                data['Volume'].iloc[-1],  # Volume
            ]
            # Append all EMA values
            row_data.extend([ema.iloc[-1] for ema in short_ema_set])
            row_data.extend([ema.iloc[-1] for ema in long_ema_set])
            
            # Add row to Google Sheets with timestamp
            add_row_to_google_sheets(row_data)
        #send_email_alert(filtered_stocks, stock_data, short_emas, long_emas)


@app.route('/run', methods=['GET'])
def run():
    filtered_stocks = filter_stocks()
    return jsonify(filtered_stocks=filtered_stocks)

@app.route('/',methods=['GET'])
def home():
    return("Welcome to GMMA trading app")

if __name__ == "__main__":
    job()
