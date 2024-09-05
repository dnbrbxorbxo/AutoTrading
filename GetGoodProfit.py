import threading

import numpy as np
from flask import Flask, jsonify, request, render_template, redirect, url_for
import os
import json
import pytz  # 시간대 설정을 위한 라이브러리
import pandas as pd

from datetime import datetime , timedelta
import time
from binance.client import Client
import json
import os
from scipy.stats import linregress
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


###########################################################
## 선물 차트 제일 타점이 좋은 지표 찾기
###########################################################
app = Flask(__name__)

# 시간대 설정 (예: UTC, 서울 시간대 등)
utc = pytz.utc
timezone = pytz.timezone("Asia/Seoul")  # 원하는 시간대로 변경 가능

# 바이낸스 API 키와 시크릿 설정
api_key = 'JWqsyuCmFvRReL39NbCqsZowGqoBCCGnX6XCjRr7VjZySpj2TsL7AKYl6eq1tQcT'
api_secret = 'KxH5oV6EFqeTbOG3KpAlDXUAmhDxoldIdkSfX8QLDhR9BDIRmed9mKLi200Y1vIy'

# 클라이언트 인스턴스 생성
client = Client(api_key, api_secret)

# 데이터가 저장된 폴더 설정 (상대 경로)
base_directory = os.path.join(os.path.dirname(__file__), 'FUTURE_DATA')
# 전역 변수로 봇의 실행 상태와 스레드를 관리
bot_running = False
bot_thread = None
bot_symbol = "BTCUSDT"


def send_email(subject, body, to_email):
    """
    분석 결과를 이메일로 보내는 함수입니다.

    Parameters:
    - subject: 이메일 제목
    - body: 이메일 본문 내용
    - to_email: 수신자 이메일 주소
    """
    # SMTP 서버 설정 (여기서는 Gmail 사용 예시)
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    from_email = "rbxo@dnbsoft.com"  # 보내는 사람 이메일 주소
    from_password = "edrpyyalcctlnonr"      # 보내는 사람 이메일 비밀번호

    # 이메일 메시지 생성
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['From'] = f"코인 알리미 by 박규태"  # 송신자 이름과 이메일 주소 설정
    msg['Subject'] = subject

    # 메시지 본문 추가
    msg.attach(MIMEText(body, 'html'))

    # SMTP 서버에 연결하여 이메일 전송
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(from_email, from_password)
        server.send_message(msg)
        print("이메일 전송 완료")
    except Exception as e:
        print(f"이메일 전송 실패: {e}")
    finally:
        server.quit()


def create_email_body(result):
    """
    분석 결과를 HTML 표 형식으로 변환하는 함수입니다.

    Parameters:
    - result: 분석 결과 딕셔너리

    Returns:
    - HTML 형식의 문자열
    """
    # HTML 테이블 생성
    html = f"""
    <html>
    <body>
        <h2>시장 현황 분석 결과</h2>
        <table border="1" style="border-collapse: collapse; width: 100%;">
            <tr>
                <th>항목</th>
                <th>값</th>
            </tr>
            <tr>
                <td>종가</td>
                <td>{result['종가']}</td>
            </tr>
            <tr>
                <td>시가</td>
                <td>{result['시가']}</td>
            </tr>
            <tr>
                <td>거래량</td>
                <td>{result['거래량']}</td>
            </tr>
            <tr>
                <td>단기 이동평균</td>
                <td>{result['단기 이동평균']}</td>
            </tr>
            <tr>
                <td>장기 이동평균</td>
                <td>{result['장기 이동평균']}</td>
            </tr>
            <tr>
                <td>LRL 값</td>
                <td>{result['LRL 값']}</td>
            </tr>
            <tr>
                <td>LRL 기울기</td>
                <td>{result['LRL 기울기']}</td>
            </tr>
            <tr>
                <td>가격 흐름</td>
                <td>{result['가격 흐름']}</td>
            </tr>
            <tr>
                <td>거래량 흐름</td>
                <td>{result['거래량 흐름']}</td>
            </tr>
            <tr>
                <td>이동평균 추세</td>
                <td>{result['이동평균 추세']}</td>
            </tr>
            <tr>
                <td>LRL 추세</td>
                <td>{result['LRL 추세']}</td>
            </tr>
            <tr>
                <td>시장 현황</td>
                <td>{result['시장 현황']}</td>
            </tr>
        </table>
    </body>
    </html>
    """
    return html

def get_market_data(symbol):


    all_data = get_all_data(symbol)

    # 날짜 및 Close 가격 추출
    candle_data = [(record['open_time'], float(record['close']), float(record['open'])) for record in all_data]

    # Close 가격 추출
    close_prices = [float(record['close']) for record in all_data]

    # 지표 계산
    indicator_data = calculate_lrl(close_prices, 240)

    # 가장 최근(마지막) 캔들 데이터와 지표 데이터만 반환
    last_candle = candle_data[-1] if candle_data else None
    last_indicator = round(indicator_data[-1] if indicator_data else 0, 3)

    # 잔액 계산
    balance = calculate_quantity(last_candle[1])

    trade_log_to_json(symbol ,f"잔액 : {balance} {symbol} / 종가: {last_candle[1]} / 시가 : {last_candle[2]} / 지표 {last_indicator}")


    return last_candle, last_indicator


def execute_trade(symbol, position, entry_date, entry_price, exit_date, exit_price, indicator_value, action_type):
    log_entry = {}  # 로그를 기록할 딕셔너리 초기화
    order_response = None  # 주문 응답 초기화

    quantity = calculate_quantity(entry_price)
    if position == 'buy':
        if action_type == '진입':
            # 시장가 매수 주문 실행
            order_response = client.futures_create_order(
                symbol=symbol,
                side='BUY',
                type='MARKET',
                quantity=quantity
            )
            log_entry = {
                "action": "매수-진입",
                "entry_date": entry_date,
                "entry_price": entry_price,
                "indicator": indicator_value,
                "order_response": order_response
            }
            trade_log_to_json(symbol, f"[매수-진입] 진입 날짜: {entry_date}, 진입 가격: {entry_price}, 지표: {indicator_value}")
        elif action_type == '정산':
            # 시장가 매도 주문으로 포지션 정산
            order_response = client.futures_create_order(
                symbol=symbol,
                side='BUY',
                type='MARKET',
                closePosition=True
            )
            profit = round((exit_price - entry_price) / entry_price * 100, 3)
            log_entry = {
                "action": "매수-정산",
                "entry_date": entry_date,
                "entry_price": entry_price,
                "exit_date": exit_date,
                "exit_price": exit_price,
                "profit": profit,
                "indicator": indicator_value,
                "order_response": order_response
            }
            trade_log_to_json(symbol,
                              f"[매수-정산] 진입 날짜: {entry_date}, 진입 가격: {entry_price}, 정산 날짜: {exit_date}, 정산 가격: {exit_price}, 수익률: {profit}%, 지표: {indicator_value}")

    elif position == 'sell':
        if action_type == '진입':
            # 시장가 매도 주문 실행
            order_response = client.futures_create_order(
                symbol=symbol,
                side='SELL',
                type='MARKET',
                quantity=quantity
            )
            log_entry = {
                "action": "매도-진입",
                "entry_date": entry_date,
                "entry_price": entry_price,
                "indicator": indicator_value,
                "order_response": order_response
            }
            trade_log_to_json(symbol, f"[매도-진입] 진입 날짜: {entry_date}, 진입 가격: {entry_price}, 지표: {indicator_value}")
        elif action_type == '정산':
            # 시장가 매도 주문으로 포지션 정산
            order_response = client.futures_create_order(
                symbol=symbol,
                side='SELL',
                type='MARKET',
                closePosition=True
            )
            profit = round((entry_price - exit_price) / entry_price * 100, 3)
            log_entry = {
                "action": "매도-정산",
                "entry_date": entry_date,
                "entry_price": entry_price,
                "exit_date": exit_date,
                "exit_price": exit_price,
                "profit": profit,
                "indicator": indicator_value,
                "order_response": order_response
            }
            trade_log_to_json(symbol,
                              f"[매도-정산] 진입 날짜: {entry_date}, 진입 가격: {entry_price}, 정산 날짜: {exit_date}, 정산 가격: {exit_price}, 수익률: {profit}%, 지표: {indicator_value}")

    # 거래 로그를 JSON 파일에 기록
    trade_to_json(symbol, log_entry)

@app.route('/SetFuturesOrder', methods=['GET'])
def set_futures_order():
    symbol = request.args.get('symbol')
    order_type = request.args.get('Type')
    action = request.args.get('Action')

    # 여기서 Binance API를 호출하거나 다른 로직을 추가합니다.
    # 예: execute_trade(symbol, order_type, action) 등의 함수 호출

    all_data = get_all_data(symbol)

    # 날짜 및 Close 가격 추출
    candle_data = [(record['open_time'], float(record['close']), float(record['open'])) for record in all_data]


    # 가장 최근(마지막) 캔들 데이터와 지표 데이터만 반환
    last_candle = candle_data[-1] if candle_data else None
    price = last_candle[1]
    # 잔액 계산
    quantity = calculate_quantity(price)

    FutureType = order_type+"_"+action
    order_response = ""

    if FutureType == "매수_진입":
        order_response = client.futures_create_order(
            symbol=symbol,
            side='BUY',
            type='MARKET',
            quantity=quantity
        )
    elif FutureType == "매수_정산":
        order_response = client.futures_create_order(
            symbol=symbol,
            side='SELL',
            type='MARKET',
            quantity=quantity
        )
    elif FutureType == "매도_진입":
        order_response = client.futures_create_order(
            symbol=symbol,
            side='SELL',
            type='MARKET',
            quantity=quantity
        )
    elif FutureType == "매도_정산":
        order_response = client.futures_create_order(
            symbol=symbol,
            side='BUY',
            type='MARKET',
            quantity=quantity
        )

    print(order_response)
    # 응답 데이터
    response = {
        'status': 'success',
        'symbol': symbol,
        'order_type': order_type,
        'action': action
    }
    return jsonify(response)

def calculate_quantity(entry_price):
    # Binance 계좌의 USDT 잔액을 조회
    balance_info = client.futures_account_balance()

    # 잔액 정보에서 USDT 잔액을 추출
    usdt_balance = next(item for item in balance_info if item["asset"] == "USDT")["balance"]
    usdt_balance = float(usdt_balance)  # 잔액을 실수형으로 변환
    print(usdt_balance)
    # 사용 가능한 USDT 잔액의 70%를 사용
    usdt_to_use = usdt_balance * 0.7

    # 진입 가격을 기준으로 구매할 수 있는 자산의 수량을 계산
    quantity = usdt_to_use / entry_price
    quantity = round(quantity, 3)  # 소수점 3자리로 반올림

    return quantity  # 계산된 수량 반환

def trade_log_to_json(symbol ,message):
    """
    단순 메시지와 일시를 JSON 파일에 저장하는 함수
    :param message: 저장할 메시지 (string)
    :param json_file_path: 저장할 JSON 파일의 경로 (기본값: 'messages.json')
    """
    # 현재 시간 구하기
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    date = datetime.now().strftime('%Y-%m-%d')
    json_file_path = f'trade_log_{symbol}_{date}.json'

    # 데이터 구조 정의
    log_entry = {
        "timestamp": timestamp,
        "message": message
    }

    # JSON 파일이 존재하는지 확인
    if os.path.exists(json_file_path):
        with open(json_file_path, 'r') as file:
            logs = json.load(file)
    else:
        logs = []

    # 새로운 로그 데이터를 리스트에 추가
    logs.append(log_entry)

    # JSON 파일에 저장
    with open(json_file_path, 'w') as file:
        json.dump(logs, file, indent=4)


@app.route('/get_trade_logs', methods=['GET'])
def get_trade_logs():
    """
    trade_log.json 파일에서 데이터를 읽어 역순으로 반환하는 함수
    """
    symbol = request.args.get("symbol")

    date = datetime.now().strftime('%Y-%m-%d')
    json_file_path = f'trade_log_{symbol}_{date}.json'

    if os.path.exists(json_file_path):
        with open(json_file_path, 'r') as file:
            logs = json.load(file)
            # 데이터를 역순으로 정렬하고 상위 20개만 반환
            reversed_logs = logs[::-1][:20]
            return jsonify({'status': 'success', 'data': reversed_logs})
    else:
        return jsonify({'status': 'error', 'message': 'No data found'}), 404


def trade_to_json(symbol , log_entry):
    log_file = f"trading_{symbol}.json"

    # 기존 로그 읽기 (파일이 존재하는 경우)
    if os.path.exists(log_file):
        with open(log_file, 'r') as file:
            try:
                logs = json.load(file)
            except json.JSONDecodeError:
                logs = []
    else:
        logs = []

    # 새 로그 추가
    logs.append(log_entry)

    # 파일에 다시 쓰기
    with open(log_file, 'w') as file:
        json.dump(logs, file, ensure_ascii=False, indent=4)

def json_to_trades(symbol):
    log_file = f"trading_{symbol}.json"
    trades = []

    # 기존 로그 읽기 (파일이 존재하는 경우)
    if os.path.exists(log_file):
        with open(log_file, 'r') as file:
            try:
                logs = json.load(file)
            except json.JSONDecodeError:
                logs = []
    else:
        logs = []


    # 마지막 로그 확인
    last_log = logs[-1] if logs else None

    # 로그 데이터를 'trades' 리스트로 변환, '진입'은 제외하되 마지막 로그가 '진입'이면 포함
    for log in logs:
        action = log.get('action')
        if action and ('진입' not in action or log == last_log):  # '진입' 거래를 제외하되, 마지막 로그는 포함
            trade = {
                '포지션': action,
                '진입 날짜': log.get('entry_date'),
                '진입 가격': log.get('entry_price'),
                '정산 날짜': log.get('exit_date'),
                '정산 가격': log.get('exit_price'),
                '지표': log.get('indicator'),
                '수익률': log.get('profit')
            }

            # 마지막 로그가 '진입'이고 정산이 없는 경우
            if log == last_log and '진입' in action:
                if log.get('exit_date') is None:
                    trade['정산 날짜'] = '미정산'
                    trade['정산 가격'] = ''
                    trade['지표'] = ''
                    trade['수익률'] = '0'
            trades.append(trade)

    trades.reverse()
    return trades


# 전역 변수로 최소 보유 틱 수 설정
MIN_HOLD_TICKS = 90
MINUS_PROFIT = -0.02

def trading_bot():
    global bot_running
    global bot_symbol
    position = None
    entry_price = None
    entry_date = None
    isPosition = False
    entry_tick_count = 0
    was_inside_candle = False  # 캔들이 지표 내에 들어왔는지 추적

    while bot_running:
        try:
            candle_data, indicator_value = get_market_data(bot_symbol)
            date, close_price, open_price = candle_data

            if indicator_value is not None and date is not None and close_price is not None and open_price is not None :
                # 현재 캔들이 지표 내에 있는지 확인
                is_inside_candle = ( (close_price <= indicator_value <= open_price) or (open_price <= indicator_value <= close_price) )

                if was_inside_candle and not is_inside_candle and position is None:
                    # 캔들이 지표 내에 있다가 벗어난 다음 틱에서 매도/매수 체결
                    if indicator_value < close_price:
                        position = 'buy'
                        entry_price = close_price
                        entry_date = date
                        entry_tick_count = 0
                        execute_trade(bot_symbol , position, entry_date, entry_price, None, None, indicator_value, '진입')
                    elif indicator_value > close_price:
                        position = 'sell'
                        entry_price = close_price
                        entry_date = date
                        entry_tick_count = 0
                        execute_trade(bot_symbol , position, entry_date, entry_price, None, None, indicator_value, '진입')

                if position is not None :
                    if position  == "buy" :
                        profit = round((close_price - entry_price) / entry_price * 100, 3)
                    elif position  == "sell" :
                        profit = round((entry_price - close_price) / entry_price * 100, 3)

                    entry_tick_count += 1
                    trade_log_to_json(bot_symbol ,f"[{position}포지션 진입중 {entry_tick_count} ] 수익률: {profit}%, 진입 날짜: {entry_date}, 진입 가격: {entry_price}")

                    if position is not None and ((is_inside_candle and entry_tick_count >= MIN_HOLD_TICKS) or profit < MINUS_PROFIT):

                        # 포지션 정산 조건
                        if position == 'buy':
                            execute_trade(bot_symbol , position, entry_date, entry_price, date, close_price, indicator_value, '정산')
                            position = None
                        elif position == 'sell' :
                            execute_trade(bot_symbol , position, entry_date, entry_price, date, close_price, indicator_value, '정산')
                            position = None

                # 현재 상태를 다음 틱에서 사용할 수 있도록 업데이트
                was_inside_candle = is_inside_candle

        except Exception as e:
            print(f"예외 발생: {str(e)}")

        time.sleep(10)

    if position is not None:
        trade_log_to_json(symbol ,f"[포지션 종료] 현재 포지션을 종료합니다: {position}, 진입 날짜: {entry_date}, 진입 가격: {entry_price}")
        execute_trade(bot_symbol , position, entry_date, entry_price, date, close_price, None, '정산')
        position = None

# Flask 라우트 설정
@app.route('/start_bot', methods=['POST'])
def start_bot():

    symbol      = request.form.get("symbol")
    leverage    = 1
    is_isolated = 0

    client.futures_change_leverage(symbol=symbol, leverage=leverage)

    global bot_running, bot_thread , bot_symbol
    if not bot_running:
        bot_running = True
        bot_symbol = symbol
        bot_thread = threading.Thread(target=trading_bot)
        bot_thread.start()
        return jsonify({"status": symbol + "자동 매매 시작"})
    else:
        return jsonify({"status": "Bot is already running"})

@app.route('/stop_bot', methods=['POST'])
def stop_bot():

    symbol = request.form.get("symbol")

    global bot_running, bot_thread , bot_symbol
    if bot_running:
        bot_running = False
        bot_symbol = symbol
        bot_thread.join()  # 현재 실행 중인 스레드가 종료될 때까지 대기
        return jsonify({"status": symbol + " 자동 매매 종료"})
    else:
        return jsonify({"status": "Bot is not running"})

@app.route('/')
def home():
    return redirect(url_for('btc'))

# Define the 'main' endpoint
@app.route('/btc')
def main():

    return render_template('btc.html')


# Define the 'main' endpoint
@app.route('/eth')
def eth():

    return render_template('eth.html')

scope_tick = 1


def calculate_daily_low_high(data):
    """
    일별 저가 및 고가 라인을 계산하는 함수입니다.

    Parameters:
    - data: 리스트, 각 요소는 딕셔너리 형태로 'open_time', 'low', 'high' 정보를 포함.

    Returns:
    - daily_low_high: 딕셔너리, 일별 저가 및 고가 값을 포함한 리스트를 반환.
    """
    # 데이터프레임으로 변환
    df = pd.DataFrame(data)

    # open_time을 datetime 형식으로 변환 후 날짜만 추출
    df['datetime'] = pd.to_datetime(df['open_time'])
    df['date'] = df['datetime'].dt.date

    # 일별 저가 및 고가 계산
    daily_low_high = df.groupby('date').agg({'low': 'min', 'high': 'max'}).reset_index()
    # 일별 결과를 딕셔너리 형태로 변환
    daily_low_high = daily_low_high.to_dict(orient='records')

    return daily_low_high


def calculate_hourly_low_high(data):
    """
    시간별 저가 및 고가 라인을 계산하는 함수입니다.

    Parameters:
    - data: 리스트, 각 요소는 딕셔너리 형태로 'open_time', 'low', 'high' 정보를 포함.

    Returns:
    - hourly_low_high: 딕셔너리, 시간별 저가 및 고가 값을 포함한 리스트를 반환.
    """
    # 데이터프레임으로 변환
    df = pd.DataFrame(data)

    # open_time을 datetime 형식으로 변환 후 시간만 추출
    df['datetime'] = pd.to_datetime(df['open_time'])
    df['hour'] = df['datetime'].dt.strftime('%Y-%m-%d %H:00:00')

    # 시간별 저가 및 고가 계산
    hourly_low_high = df.groupby('hour').agg({'low': 'min', 'high': 'max'}).reset_index()

    # 시간별 결과를 딕셔너리 형태로 변환
    hourly_low_high = hourly_low_high.to_dict(orient='records')

    return hourly_low_high

# Linear Regression Line (LRL) 지표 계산 함수
def calculate_lrl_new(data, window_size=14):
    """
    주어진 기간(period) 동안의 Linear Regression Line(LRL)을 계산합니다.

    :param df: pandas DataFrame, 가격 데이터 (여기서는 'Close' 열을 사용)
    :param period: int, LRL을 계산할 기간 (기본값은 14일)
    :return: pandas Series, LRL 값
    """
    lrl = []  # LRL 값을 저장할 리스트

    for i in range(len(data)):
        if i < window_size - 1:
            lrl.append(None)  # 윈도우 크기 이전에는 None 추가
        else:
            # 윈도우 크기 내의 데이터를 선택
            y = data[i - window_size + 1:i + 1]
            x = np.arange(window_size)

            # 선형 회귀 계산
            slope, intercept, _, _, _ = linregress(x, y)
            # 마지막 x 값에서의 LRL 계산
            lrl_value = intercept + slope * (window_size - 1)
            lrl.append(lrl_value)

    return lrl

def calculate_lrl(data, window_size):
    lrl = []
    for i in range(len(data)):
        if i < window_size - 1:
            lrl.append(None)
        else:
            y = data[i - window_size + 1:i + 1]
            x = np.arange(window_size)
            A = np.vstack([x, np.ones(len(x))]).T
            m, c = np.linalg.lstsq(A, y, rcond=None)[0]
            lrl.append(m * (window_size - 1) + c)  # 마지막 시점의 값을 계산
    return lrl



def calculate_lrl_weight(data, window_size):
    weighted_lrl = []
    for i in range(len(data)):
        if i < window_size - 1:
            weighted_lrl.append(None)
        else:
            y = data[i - window_size + 1:i + 1]
            x = np.arange(window_size)
            A_matrix = np.vstack([x, np.ones(len(x))]).T
            m1, c1 = np.linalg.lstsq(A_matrix, y, rcond=None)[0]
            A = m1 * (window_size - 1) + c1

            y_A = [m1 * j + c1 for j in x]
            m2, c2 = np.linalg.lstsq(A_matrix, y_A, rcond=None)[0]
            A1 = m2 * (window_size - 1) + c2

            eq = A - A1
            VL = A + eq

            weighted_lrl.append(VL)
    return weighted_lrl


def calculate_lrl_with_volume(data, volume, window_size):
    """
    데이터와 거래량을 사용하여 LRL을 계산하는 함수
    :param data: 가격 데이터 리스트
    :param volume: 거래량 데이터 리스트
    :param window_size: 윈도우 크기 (이동 평균 길이)
    :return: LRL 리스트
    """
    lrl = []
    for i in range(len(data)):
        if i < window_size - 1:
            lrl.append(None)  # 윈도우 크기보다 작은 경우 None 추가
        else:
            y = data[i - window_size + 1:i + 1]  # 종가 데이터
            x = np.arange(window_size)  # 시간 축 데이터
            v = volume[i - window_size + 1:i + 1]  # 거래량 데이터

            # X 행렬 구성 (시간 축과 거래량을 합쳐서 사용)
            X = np.vstack([x, v, np.ones(len(x))]).T

            # 회귀 계산
            m, v_coef, c = np.linalg.lstsq(X, y, rcond=None)[0]

            # 마지막 시점의 LRL 값을 계산
            lrl_value = m * (window_size - 1) + v_coef * v[-1] + c
            lrl.append(lrl_value)

    return lrl


def calculate_lrv(data, window_size):
    lrv = [None] * (window_size - 1)  # 초기 None 값
    for i in range(window_size - 1, len(data)):
        y = data[i - window_size + 1:i + 1]
        x = np.arange(window_size)
        A = np.vstack([x, np.ones(len(x))]).T
        m, c = np.linalg.lstsq(A, y, rcond=None)[0]
        lrv.append(m * (window_size - 1) + c)  # 구간의 마지막 값에 대한 LRV 값을 추가
    return lrv



def calculate_lrv_ols(data, window_size):
    lrv = [None] * (window_size - 1)
    for i in range(window_size - 1, len(data)):
        y = data[i - window_size + 1:i + 1]
        x = np.arange(window_size)
        A = np.vstack([x, np.ones(len(x))]).T
        m, c = np.linalg.lstsq(A, y, rcond=None)[0]
        lrv.append(m * x[-1] + c)
    return lrv

def calculate_lrv_matrix(data, window_size):
    lrv = [None] * (window_size - 1)
    for i in range(window_size - 1, len(data)):
        y = data[i - window_size + 1:i + 1]
        x = np.arange(window_size)
        X_b = np.c_[np.ones((len(x), 1)), x]  # 절편을 포함하는 행렬 생성
        theta = np.linalg.lstsq(X_b, y, rcond=None)[0]
        lrv.append(theta[1] * x[-1] + theta[0])
    return lrv

def calculate_lrv_qr(data, window_size):
    lrv = [None] * (window_size - 1)
    for i in range(window_size - 1, len(data)):
        y = data[i - window_size + 1:i + 1]
        x = np.arange(window_size)
        X_b = np.c_[np.ones((len(x), 1)), x]
        Q, R = np.linalg.qr(X_b)
        theta = np.linalg.inv(R).dot(Q.T).dot(y)
        lrv.append(theta[1] * x[-1] + theta[0])
    return lrv

def calculate_lrv_svd(data, window_size):
    lrv = [None] * (window_size - 1)
    for i in range(window_size - 1, len(data)):
        y = data[i - window_size + 1:i + 1]
        x = np.arange(window_size)
        X_b = np.c_[np.ones((len(x), 1)), x]
        U, Sigma, VT = np.linalg.svd(X_b, full_matrices=False)
        theta = VT.T.dot(np.linalg.inv(np.diag(Sigma))).dot(U.T).dot(y)
        lrv.append(theta[1] * x[-1] + theta[0])
    return lrv

def calculate_lrv_poly(data, window_size, degree=2):
    lrv = [None] * (window_size - 1)
    for i in range(window_size - 1, len(data)):
        y = data[i - window_size + 1:i + 1]
        x = np.arange(window_size)
        p = np.polyfit(x, y, degree)
        lrv_value = np.polyval(p, x[-1])  # 구간의 마지막 값을 선택
        lrv.append(lrv_value)
    return lrv

def calculate_lrl_slope(data, window_size):
    """
    주어진 데이터에서 선형 회귀선의 기울기를 계산합니다.

    Parameters:
    - data: 리스트, 각 요소는 종가를 포함하는 데이터.
    - window_size: 회귀선을 계산할 기간.

    Returns:
    - slopes: 리스트, 각 요소는 계산된 LRL 기울기 값 또는 None.
    """
    slopes = []
    for i in range(len(data)):
        if i < window_size - 1:
            slopes.append(None)
        else:
            # 종가 데이터를 float 타입의 numpy 배열로 변환
            y = np.array([data[j] for j in range(i - window_size + 1, i + 1)], dtype=float)
            x = np.array(np.arange(window_size), dtype=float)
            A = np.vstack([x, np.ones(len(x), dtype=float)]).T
            # lstsq 함수를 사용하여 기울기와 절편 계산
            result = np.linalg.lstsq(A, y, rcond=None)
            coefficients = result[0]  # 계수는 첫 번째 요소에 포함되어 있음
            m = coefficients[0]  # 기울기 추출
            slopes.append(m)
    return slopes

def calculate_dmi(data, window_size=14):
    """
    DMI 지표를 계산하는 함수입니다.

    Parameters:
    - data: 리스트, 각 요소는 딕셔너리 형태로 시가, 고가, 저가, 종가, 거래량 등의 정보를 포함합니다.
    - window_size: DMI를 계산할 기간 (기본값: 14)

    Returns:
    - +DI, -DI, ADX 값을 리스트로 반환합니다.
    """
    plus_di = []
    minus_di = []
    adx = []

    tr_list = []
    pdm_list = []
    ndm_list = []

    for i in range(1, len(data)):
        high = data[i]['high']
        low = data[i]['low']
        close_prev = data[i - 1]['close']

        tr = max(high - low, abs(high - close_prev), abs(low - close_prev))
        pdm = max(high - data[i - 1]['high'], 0) if high - data[i - 1]['high'] > data[i - 1]['low'] - low else 0
        ndm = max(data[i - 1]['low'] - low, 0) if data[i - 1]['low'] - low > high - data[i - 1]['high'] else 0

        tr_list.append(tr)
        pdm_list.append(pdm)
        ndm_list.append(ndm)

    tr_smooth = np.cumsum(tr_list[:window_size])
    pdm_smooth = np.cumsum(pdm_list[:window_size])
    ndm_smooth = np.cumsum(ndm_list[:window_size])

    for i in range(window_size, len(tr_list)):
        tr_smooth = tr_smooth - tr_smooth / window_size + tr_list[i]
        pdm_smooth = pdm_smooth - pdm_smooth / window_size + pdm_list[i]
        ndm_smooth = ndm_smooth - ndm_smooth / window_size + ndm_list[i]

        plus_di_value = (pdm_smooth / tr_smooth) * 100
        minus_di_value = (ndm_smooth / tr_smooth) * 100
        plus_di.append(plus_di_value)
        minus_di.append(minus_di_value)

        dx = abs(plus_di_value - minus_di_value) / (plus_di_value + minus_di_value) * 100
        adx.append(np.mean(dx if len(adx) == 0 else adx[-window_size:] + [dx]))

    # 앞의 window_size - 1 구간은 None으로 설정
    plus_di = [None] * (window_size - 1) + plus_di
    minus_di = [None] * (window_size - 1) + minus_di
    adx = [None] * (window_size - 1) + adx

    return plus_di, minus_di, adx


def calculate_moving_average(data, window_size):
    """
    주어진 데이터에서 단기 이동 평균선을 계산하고 lrl 형태로 반환합니다.

    Parameters:
    - data: 리스트, 각 요소는 딕셔너리 형태로 시가, 고가, 저가, 종가, 거래량 등의 정보를 포함합니다.
    - window_size: 정수, 이동 평균을 계산할 기간(예: 5일, 10일 등).

    Returns:
    - result: 딕셔너리, 키는 lrl처럼 구조화되어 이동 평균 데이터가 저장됩니다.
    """
    moving_averages = []  # 이동 평균 값을 저장할 리스트

    # 데이터에서 이동 평균을 계산
    for i in range(len(data)):
        if i < window_size - 1:
            # window_size보다 데이터가 적을 때는 이동 평균을 계산할 수 없음, None 추가
            moving_averages.append(None)
        else:
            # 이동 평균 계산을 위한 데이터 슬라이스
            window_data = [item['close'] for item in data[i - window_size + 1:i + 1]]
            avg_close = sum(window_data) / window_size

            # 이동 평균 값 추가
            moving_averages.append(avg_close)

    return moving_averages


def analyze_market(data, short_window=120, long_window=640, lrl_window=120):
    """
    현재 종가, 시가, 거래량을 바탕으로 기술적 지표를 분석하여 현재 시장 현황을 평가하는 함수입니다.

    Parameters:
    - data: 리스트, 각 요소는 딕셔너리 형태로 시가, 고가, 저가, 종가, 거래량 등의 정보를 포함합니다.
    - short_window: 단기 이동평균선 계산 기간 (기본값: 120)
    - long_window: 장기 이동평균선 계산 기간 (기본값: 640)
    - lrl_window: LRL 계산 기간 (기본값: 120)

    Returns:
    - 분석 결과: 현재 시장 상황에 대한 기술적 분석 결과를 출력합니다.
    """
    # 이동 평균선과 LRL 계산
    short_ma = calculate_moving_average(data, short_window)
    long_ma = calculate_moving_average(data, long_window)
    record = []
    close_prices = [float(record['close']) for record in data]

    lrl_values = calculate_lrl(close_prices, lrl_window)
    lrl_slopes = calculate_lrl_slope(close_prices, lrl_window)

    # 리스트에서 마지막 값을 가져옵니다.
    latest_short_ma = short_ma[-1] if short_ma[-1] is not None else None
    latest_long_ma = long_ma[-1] if long_ma[-1] is not None else None
    latest_lrl = lrl_values[-1] if lrl_values[-1] is not None else None
    latest_lrl_slope = lrl_slopes[-1] if lrl_slopes[-1] is not None else None

    latest_close = data[-1]['close']
    latest_open = data[-1]['open']
    latest_volume = data[-1]['volume']

    # 거래량 변동 분석
    recent_volumes = [item['volume'] for item in data[-long_window:]]
    avg_volume = np.mean(recent_volumes)
    volume_trend = "증가" if latest_volume > avg_volume else "감소"

    # 종가와 시가 비교
    price_trend = "강세" if latest_close > latest_open else "약세"

    # 단기와 장기 이동 평균선 비교 및 횡보 판단
    if latest_short_ma is not None and latest_long_ma is not None:
        if abs(latest_short_ma - latest_long_ma) / latest_long_ma < 0.01:  # 이동평균선 차이가 1% 미만일 때 횡보로 판단
            ma_trend = "횡보"
        else:
            ma_trend = "상승 추세" if latest_short_ma > latest_long_ma else "하락 추세"
    else:
        ma_trend = "분석 불가"

    # LRL 지표를 기반으로 한 추가 추세 판단
    if latest_lrl is not None and latest_lrl_slope is not None:
        if abs(latest_lrl_slope) < 0.001:  # 기울기 절대값이 매우 작으면 횡보로 판단
            lrl_trend = "횡보"
        else:
            lrl_trend = "상승 추세" if latest_lrl_slope > 0 else "하락 추세"
    else:
        lrl_trend = "분석 불가"

    # 분석 결과 평가
    if price_trend == "강세" and ma_trend == "상승 추세" and volume_trend == "증가" and lrl_trend == "상승 추세":
        market_status = "시장 강세, 매수 신호"
    elif price_trend == "약세" and ma_trend == "하락 추세" and volume_trend == "증가" and lrl_trend == "하락 추세":
        market_status = "시장 약세, 매도 신호"
    elif ma_trend == "횡보" or lrl_trend == "횡보":
        market_status = "시장 횡보, 관망 추천"
    else:
        market_status = "관망 추천, 신호가 불확실함"

    # 결과 출력
    result = {
        "종가": latest_close,
        "시가": latest_open,
        "거래량": latest_volume,
        "단기 이동평균": latest_short_ma,
        "장기 이동평균": latest_long_ma,
        "LRL 값": latest_lrl,
        "LRL 기울기": latest_lrl_slope,
        "가격 흐름": price_trend,
        "거래량 흐름": volume_trend,
        "이동평균 추세": ma_trend,
        "LRL 추세": lrl_trend,
        "시장 현황": market_status
    }


    # 분석 결과를 이메일로 전송
    email_subject = "코인 시장 현황 분석 결과"
    email_body = create_email_body(result)

    # send_email(email_subject, email_body, "c476262@gmail.com")  # 수신자 이메일을 입력하세요


    return result

# 데이터를 요청할 함수 정의
def fetch_data(symbol, interval, start_date, end_date):
    client.FUTURES = True  # Futures 사용 설정

    # 밀리초 시간으로 변환
    start_timestamp = int(start_date.timestamp() * 1000)
    end_timestamp = int(end_date.timestamp() * 1000)

    # 데이터를 저장할 배열
    data = []

    # 데이터 요청 루프
    try:
        # 캔들스틱 데이터 가져오기
        klines = client.futures_klines(
            symbol=symbol,
            interval=interval,
            startTime=start_timestamp,
            endTime=end_timestamp,
        )

        # 데이터를 배열에 추가
        for kline in klines:
            record = {
                'open_time': datetime.fromtimestamp(kline[0] / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                'open': float(kline[1]),
                'high': float(kline[2]),
                'low': float(kline[3]),
                'close': float(kline[4]),
                'volume': float(kline[5])
            }
            data.append(record)

        # API 제한을 피하기 위해 잠시 대기
        time.sleep(0.1)

    except Exception as e:
        print(f"오류 발생: {e}")

    return data


# 사용 예시
# data = [...]  # 제공된 형식의 데이터
# window_size = 5  # 5일 단기 이동평균선 예시
# result = calculate_moving_average(data, window_size)
# print(result)


def get_all_data(symbol="BTCUSDT"):
    # 심볼과 간격 설정
    interval = Client.KLINE_INTERVAL_5MINUTE  # 5분 봉 설정
    total_data_points = 3000  # 총 2000개의 데이터가 필요
    limit = 200  # 요청당 최대 100개 데이터

    # 현재 시간과 종료 시간 설정
    end_date = datetime.now()
    print(end_date)
    combined_data = []

    # 데이터 요청 루프
    while len(combined_data) < total_data_points:
        start_date = end_date - timedelta(minutes= 5 * limit)  # 시작 시간 계산
        print(f"{start_date}부터 {end_date}까지 데이터를 가져오는 중...")

        # 데이터 요청
        data_chunk = fetch_data(symbol, interval, start_date, end_date)
        data_chunk.reverse()
        combined_data.extend(data_chunk)  # 가져온 데이터를 합침

        print(f"가져온 데이터 개수: {len(data_chunk)}")

        # 다음 요청을 위해 종료 시간을 업데이트
        end_date = start_date

        # 요청된 데이터가 없으면 중지
        if not data_chunk:
            print("더 이상 데이터를 가져올 수 없습니다.")
            break

    # 필요 개수만큼 데이터를 슬라이싱
    combined_data = combined_data[:total_data_points]


    # 결과 확인
    print(f"총 {len(combined_data)}개의 데이터를 가져왔습니다.")
    combined_data.reverse()
    return combined_data
# 모든 데이터 제공 API
@app.route('/get_data', methods=['GET'])
def get_data():

    symbol = request.args.get("symbol")

    print(symbol)
    all_data = get_all_data(symbol)

    if all_data:
        # Close 가격 추출
        close_prices = [float(record['close']) for record in all_data]
        volumes = [float(record['volume']) for record in all_data]

        # LRL 계산
        lrl_120 = calculate_lrl(close_prices, 120)
        lrl_640 = calculate_lrl(close_prices, 640)
        lrl_1200 = calculate_lrl(close_prices, 1200)

        # LRV 계산
        lrv_poly_1200 = calculate_lrv_poly(close_prices, 1200)

        # 이평선 계산
        moving_200 = calculate_lrl(close_prices , 800)
        moving_50 = calculate_lrl(close_prices , 200)

        day = calculate_daily_low_high(all_data)
        hour = calculate_hourly_low_high(all_data)

        #market_status = analyze_market(all_data , 120 , 1200)

        # dmi

        # slope_120 = calculate_slope(lrl_120)
        # slope_240 = calculate_slope(lrl_240)
        # slope_480 = calculate_slope(lrl_480)
        # slope_640 = calculate_slope(lrl_640)
        # slope_1200 = calculate_slope(lrl_1200)

        return jsonify({
            'status': 'success',
            'data': all_data,

            'lrl_120': lrl_120,
            'lrl_640': lrl_640,
            'lrl_1200': lrl_1200,

            'lrv_poly_1200': lrv_poly_1200,

            'moving_200': moving_200,
            'moving_50': moving_50,
            'day' : day ,
            'hour' : hour

        })
    else:
        return jsonify({'status': 'error', 'message': 'No data found'}), 404

# 지표 별 시뮬레이션
@app.route('/GetTradingLog', methods=['GET'])
def GetTradingLog():
    symbol = request.args.get("symbol")
    all_data = get_all_data(symbol)

    if all_data:
        # 날짜 및 Close 가격 추출
        candle_data = [(record['open_time'], float(record['close']), float(record['open'])) for record in all_data]

        # Close 가격 추출
        close_prices = [float(record['close']) for record in all_data]

        # 거래 시뮬레이션 실행
        Simulator = {}
        Simulator["LRL120"] = simulate_trading(candle_data, calculate_lrl(close_prices, 1200))
        Simulator["POLY120"] = simulate_trading(candle_data, calculate_lrv_poly(close_prices, 1200))

        # 결과 반환
        return jsonify(Simulator)
    else:
        return jsonify({'status': 'error', 'message': 'No data found'}), 404

def simulate_trading(candle_data, indicator_data, profit_threshold=1.0, stop_loss_threshold=-0.3):
    trades = []  # 거래 내역을 저장할 리스트
    position = None  # 현재 포지션 ('buy' or 'sell')
    entry_price = None  # 포지션 진입 가격
    entry_date = None  # 포지션 진입 날짜

    for i in range(1, len(candle_data) - 1):  # 마지막 틱은 진입을 확인할 수 없으므로 -1까지 반복
        # 이전 틱과 현재 틱의 데이터를 가져옴
        prev_date, prev_close_price, prev_open_price = candle_data[i - 1]
        date, close_price, open_price = candle_data[i]  # 현재 틱의 날짜와 종가, 시가 추출
        next_date, next_close_price = candle_data[i + 1][0], candle_data[i + 1][1]  # 다음 틱의 날짜와 종가
        indicator_value = indicator_data[i]

        if indicator_value is None:
            continue  # 지표 값이 없으면 건너뜀

        # 포지션이 있는 상태에서 정산 조건 확인
        if position == 'buy':
            # 수익률 계산
            profit = (close_price - entry_price) / entry_price * 100
            # 익절 또는 손절 조건: 설정한 수익률 이상일 때 정산 또는 손절
            if profit >= profit_threshold or profit <= stop_loss_threshold or (
                    open_price <= indicator_value <= close_price) or (close_price <= indicator_value <= open_price):
                exit_price = close_price
                trades.append({
                    '포지션': '매수-정산',
                    '진입 날짜': entry_date,
                    '진입 가격': entry_price,
                    '정산 날짜': date,
                    '정산 가격': exit_price,
                    '지표': indicator_value,
                    '수익률': round(profit, 3)
                })
                position = None  # 포지션 종료

        elif position == 'sell':
            # 수익률 계산
            profit = (entry_price - close_price) / entry_price * 100
            # 익절 또는 손절 조건: 설정한 수익률 이상일 때 정산 또는 손절
            if profit >= profit_threshold or profit <= stop_loss_threshold or (
                    open_price <= indicator_value <= close_price) or (close_price <= indicator_value <= open_price):
                exit_price = close_price
                trades.append({
                    '포지션': '매도-정산',
                    '진입 날짜': entry_date,
                    '진입 가격': entry_price,
                    '정산 날짜': date,
                    '정산 가격': exit_price,
                    '지표': indicator_value,
                    '수익률': round(profit, 3)
                })
                position = None  # 포지션 종료

        # 현재 틱에서 지표가 캔들을 타고 올라가는 경우 진입하지 않음
        if ((prev_open_price <= indicator_value <= prev_close_price) or
            (prev_close_price <= indicator_value <= prev_open_price)):
            continue  # 타고 올라가면 진입하지 않음

        # 현재 틱에서 지표가 캔들 안에 있고, 다음 틱에서 진입을 결정
        if (open_price <= indicator_value <= close_price) or (close_price <= indicator_value <= open_price):
            # 현재 포지션이 없는 상태에서 진입 조건 확인
            if position is None:
                if indicator_value < next_close_price:
                    position = 'buy'
                    entry_price = next_close_price  # 다음 틱에서 진입 가격 설정
                    entry_date = next_date  # 다음 틱의 날짜를 진입 날짜로 설정
                elif indicator_value > next_close_price:
                    position = 'sell'
                    entry_price = next_close_price  # 다음 틱에서 진입 가격 설정
                    entry_date = next_date  # 다음 틱의 날짜를 진입 날짜로 설정



    # 남아 있는 포지션 처리
    if position is not None:
        if position == "buy":
            trades.append({
                '포지션': '매수-포지션',
                '진입 날짜': entry_date,
                '진입 가격': entry_price,
                '정산 날짜': "-",
                '정산 가격': "-",
                '지표': "-",
                '수익률': "0"
            })
        elif position == "sell":
            trades.append({
                '포지션': '매도-포지션',
                '진입 날짜': entry_date,
                '진입 가격': entry_price,
                '정산 날짜': "-",
                '정산 가격': "-",
                '지표': "-",
                '수익률': "0"
            })

    trades.reverse()  # 거래 내역을 시간 역순으로 정렬
    return trades



if __name__ == '__main__':
    app.run(debug=True , port=5600)
