

#########  updated with log    ###########
##########################################

import csv
from datetime import datetime as dt_datetime, timedelta
import time
import threading
import logging
import pandas as pd
from NorenRestApiPy.NorenApi import NorenApi
import pyotp

class ShoonyaApiPy(NorenApi):
    def __init__(self):
        super().__init__(host='https://api.shoonya.com/NorenWClientTP/', websocket='wss://api.shoonya.com/NorenWSTP/')

# Configuration Constants
USER = 'FA74468'
PWD = 'GURU222kore$'
TOKEN = 'XT2L66VT73Q22P33BNCHKN6WA2Q37KK6'
VC = 'FA74468_U'
APP_KEY = 'c98e82a190da8181c80fb94cf0a31144'
IMEI = 'abc1234'
CSV_FILE_PATH = "C:\\Users\\omkar\\Downloads\\Backtest BB Blast_Omk, Technical Analysis Scanner.csv"
REMOVE_STOCKS = ['M&M-EQ', 'M&MFIN-EQ', 'J&KBANK-EQ']
processed_stocks = set()

# Logging Configuration
logging.basicConfig(
    filename='D:\\AA_trading_Algos\\modified_ALgo\\trading_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)

# Initialize API
api = ShoonyaApiPy()
factor2 = pyotp.TOTP(TOKEN).now()
api.login(userid=USER, password=PWD, twoFA=factor2, vendor_code=VC, api_secret=APP_KEY, imei=IMEI)

def parse_datetime(date_str):
    formats = ["%d-%m-%Y %I:%M %p", "%d-%m-%Y %H:%M"]
    for fmt in formats:
        try:
            return dt_datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Date parsing error: time data '{date_str}' does not match any of the known formats.")

def extract_stock_list_from_csv(csv_file_path, target_datetime_str):
    stock_list = []
    try:
        target_datetime = parse_datetime(target_datetime_str)
        target_date = target_datetime.date()
        target_time = target_datetime.time()

        with open(csv_file_path, mode='r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            for row in reader:
                try:
                    row_datetime = parse_datetime(row['date'])
                except ValueError:
                    continue

                if row_datetime.date() == target_date and row_datetime.time() == target_time:
                    stock_list.append(f"{row['symbol']}-EQ")
    except Exception as e:
        logging.error(f"An error occurred while extracting stock list: {e}")
    return stock_list

def place_orders(target_datetime_str):
    global stocksList, slArray, tgtArray

    stocksList = extract_stock_list_from_csv(CSV_FILE_PATH, target_datetime_str)
    stocksList = [symbol for symbol in stocksList if symbol not in REMOVE_STOCKS]

    if len(stocksList) > 3:
        stocksList = []
        logging.info("More than 3 stocks found. No orders will be placed.")
    elif not stocksList:
        slArray = []
        tgtArray = []
        logging.info("No stocks found for the given time. Clearing previous stock lists.")
    else:
        slArray = []
        tgtArray = []

        for symbol in stocksList:
            try:
                quote = api.get_quotes(exchange='NSE', token=symbol)
                LTP = float(quote["lp"])

                stop_loss = round(LTP * 1.0045, 2)
                target = round(LTP * 0.992, 2)
                Qty_Stock = round(10000 / LTP)
                slArray.append(stop_loss)
                tgtArray.append(target)

                logging.info(f"LTP: {LTP}, Stop-Loss: {stop_loss}, Target: {target} for symbol: {symbol}")

                api.place_order(
                    buy_or_sell='S', product_type='I', exchange='NSE', tradingsymbol=symbol,
                    quantity=Qty_Stock, discloseqty=0, price_type='MKT', trigger_price=None,
                    retention='DAY', remarks='Place_order'
                )
                logging.info(f"Order placed for symbol: {symbol}")

            except Exception as e:
                logging.error(f"Error occurred for symbol {symbol}: {e}")

    logging.info("place_orders function completed.")

def check_positions_and_place_orders():
    positions = api.get_positions()

    if positions and isinstance(positions, list):
        df = pd.DataFrame(positions)

        if 'tsym' in df.columns and 'rpnl' in df.columns and 'daysellqty' in df.columns:
            df['rpnl'] = pd.to_numeric(df['rpnl'], errors='coerce')
            df = df.dropna(subset=['rpnl'])
            filtered_df = df[(df['rpnl'] <= -45) | (df['rpnl'] >= 75)]

            if filtered_df.empty:
                logging.info("No positions meet the criteria for placing orders.")
            
            for index, row in filtered_df.iterrows():
                stock_name = row['tsym']
                rpnl_value = float(row['rpnl'])
                quantity = row['daysellqty']
                
                if stock_name in processed_stocks:
                    continue
                
                logging.info(f"Checking position: {stock_name}, Quantity: {quantity}, PnL: {rpnl_value}")
                
                ret = api.place_order(
                    buy_or_sell='B', 
                    product_type='I',
                    exchange='NSE', 
                    tradingsymbol=stock_name, 
                    quantity=quantity, 
                    discloseqty=0,
                    price_type='MKT', 
                    retention='DAY', 
                    remarks='my_order_001'
                )
                logging.info(f"Order placed: {ret}")
                
                processed_stocks.add(stock_name)
        else:
            logging.error("'tsym', 'rpnl' or 'daysellqty' column not found in the data.")
    else:
        logging.error("No positions data found or the data is not in the expected format.")

    logging.info("check_positions_and_place_orders function completed.")

def round_down_to_nearest_15_minutes(dt):
    new_minute = (dt.minute // 15) * 15
    return dt.replace(minute=new_minute, second=0, microsecond=0)

def get_previous_timestamp():
    now = dt_datetime.now()
    previous_time = now - timedelta(minutes=15)
    rounded_time = round_down_to_nearest_15_minutes(previous_time)
    return rounded_time.strftime('%d-%m-%Y %I:%M %p')

def schedule_place_orders(start_time, end_time):
    while dt_datetime.now().time() <= end_time:
        if dt_datetime.now().time() >= start_time:
            target_datetime_str = get_previous_timestamp()
            logging.info(f"Placing orders for {target_datetime_str}")
            place_orders(target_datetime_str)
            time.sleep(15 * 60)  # Sleep for 15 minutes
        else:
            time.sleep(1)  # Wait until the start time is reached

def schedule_check_positions(start_time, end_time):
    while dt_datetime.now().time() <= end_time:
        if dt_datetime.now().time() >= start_time:
            logging.info("Checking positions and placing orders.")
            check_positions_and_place_orders()
            time.sleep(10)  # Sleep for 10 seconds
        else:
            time.sleep(1)  # Wait until the start time is reached

if __name__ == "__main__":
    # Custom Start and End Times (Adjust these for testing)
    place_orders_start_time = dt_datetime.strptime("10:15", "%H:%M").time()
    place_orders_end_time = dt_datetime.strptime("11:45", "%H:%M").time()

    check_positions_start_time = dt_datetime.strptime("10:18", "%H:%M").time()
    check_positions_end_time = dt_datetime.strptime("15:10", "%H:%M").time()

    # Start place_orders function on a separate thread
    place_orders_thread = threading.Thread(target=schedule_place_orders, args=(place_orders_start_time, place_orders_end_time))
    place_orders_thread.start()

    # Start check_positions_and_place_orders function on another thread
    check_positions_thread = threading.Thread(target=schedule_check_positions, args=(check_positions_start_time, check_positions_end_time))
    check_positions_thread.start()

    place_orders_thread.join()
    check_positions_thread.join()










