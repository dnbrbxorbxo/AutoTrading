import threading

import numpy as np
from flask import Flask, jsonify, request, render_template, redirect, url_for
import os
import json
from datetime import datetime
import time
from binance.client import Client
import json
import os

app = Flask(__name__)

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


def get_market_data():
    all_data = get_all_data()

    # 날짜 및 Close 가격 추출
    candle_data = [(record['open_time'], float(record['close']), float(record['open'])) for record in all_data]

    # Close 가격 추출
    close_prices = [float(record['close']) for record in all_data]

    # 지표 계산
    indicator_data = calculate_lrl(close_prices, 120)

    # 가장 최근(마지막) 캔들 데이터와 지표 데이터만 반환
    last_candle = candle_data[-1] if candle_data else None
    last_indicator = indicator_data[-1] if indicator_data else None
    trade_log_to_json(f"종가: {last_candle[1]} / 시가 : {last_candle[2]} / 지표 {last_indicator}")

    return last_candle, last_indicator


def execute_trade(position, entry_date, entry_price, exit_date, exit_price, indicator_value, action_type):
    log_entry = {}
    if position == 'buy':
        if action_type == '진입':
            log_entry = {
                "action": "매수-진입",
                "entry_date": entry_date,
                "entry_price": entry_price,
                "indicator": indicator_value
            }
            trade_log_to_json(f"[매수-진입] 진입 날짜: {entry_date}, 진입 가격: {entry_price}, 지표: {indicator_value}")
        elif action_type == '정산':
            profit = round((exit_price - entry_price) / entry_price * 100, 3)
            log_entry = {
                "action": "매수-정산",
                "entry_date": entry_date,
                "entry_price": entry_price,
                "exit_date": exit_date,
                "exit_price": exit_price,
                "profit": profit,
                "indicator": indicator_value
            }
            trade_log_to_json(
                f"[매수-정산] 진입 날짜: {entry_date}, 진입 가격: {entry_price}, 정산 날짜: {exit_date}, 정산 가격: {exit_price}, 수익률: {profit}%, 지표: {indicator_value}")
    elif position == 'sell':
        if action_type == '진입':
            log_entry = {
                "action": "매도-진입",
                "entry_date": entry_date,
                "entry_price": entry_price,
                "indicator": indicator_value
            }
            trade_log_to_json(f"[매도-진입] 진입 날짜: {entry_date}, 진입 가격: {entry_price}, 지표: {indicator_value}")
        elif action_type == '정산':
            profit = round((entry_price - exit_price) / entry_price * 100, 3)
            log_entry = {
                "action": "매도-정산",
                "entry_date": entry_date,
                "entry_price": entry_price,
                "exit_date": exit_date,
                "exit_price": exit_price,
                "profit": profit,
                "indicator": indicator_value
            }
            trade_log_to_json(
                f"[매도-정산] 진입 날짜: {entry_date}, 진입 가격: {entry_price}, 정산 날짜: {exit_date}, 정산 가격: {exit_price}, 수익률: {profit}%, 지표: {indicator_value}")

    # 로그를 JSON 파일에 기록
    trade_to_json(log_entry)


def trade_log_to_json(message):
    """
    단순 메시지와 일시를 JSON 파일에 저장하는 함수
    :param message: 저장할 메시지 (string)
    :param json_file_path: 저장할 JSON 파일의 경로 (기본값: 'messages.json')
    """
    # 현재 시간 구하기
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    date = datetime.now().strftime('%Y-%m-%d')
    json_file_path = f'trade_log_{date}.json'

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

    date = datetime.now().strftime('%Y-%m-%d')
    json_file_path = f'trade_log_{date}.json'

    if os.path.exists(json_file_path):
        with open(json_file_path, 'r') as file:
            logs = json.load(file)
            # 데이터를 역순으로 정렬하고 상위 20개만 반환
            reversed_logs = logs[::-1][:20]
            return jsonify({'status': 'success', 'data': reversed_logs})
    else:
        return jsonify({'status': 'error', 'message': 'No data found'}), 404


def trade_to_json(log_entry):
    log_file = "trading.json"

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


def json_to_trades():
    log_file = "trading.json"
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
MIN_HOLD_TICKS = 30


def trading_bot():
    global bot_running
    position = None
    entry_price = None
    entry_date = None
    isPosition = False
    entry_tick_count = 0  # 포지션 진입 후 유지된 틱 수를 추적

    while bot_running:
        try:
            # 데이터 및 지표값 가져오기
            candle_data, indicator_value = get_market_data()
            date, close_price, open_price = candle_data

            # 시가와 종가를 이용한 캔들 범위 계산
            low_price = min(open_price, close_price)
            high_price = max(open_price, close_price)

            # 이전 상태에서 지표가 캔들 내에 있었는지 여부
            was_inside_candle = low_price <= previous_indicator_value <= high_price

            # 현재 상태에서 지표가 캔들 내에서 벗어났는지 여부
            is_outside_candle = not (low_price <= indicator_value <= high_price)

            # 포지션 진입 조건: 지표가 캔들 내에 위치할 때
            # 횡보 구간 고려 하여 , 지표가 캔들 내에 위치 하다가 지표가 캔들 범위 내에서 벗어 났을때 포지션 진입 하도록 포지션 접근 로직 수정
            # 포지션이 없을 때 진입
            if isPosition and is_outside_candle and position is None:
                if indicator_value < close_price:
                    position = 'buy'
                    entry_price = close_price
                    entry_date = date
                    entry_tick_count = 0  # 진입 시 틱 카운트 초기화
                    execute_trade(position, entry_date, entry_price, None, None, indicator_value, '진입')
                elif indicator_value > close_price:
                    position = 'sell'
                    entry_price = close_price
                    entry_date = date
                    entry_tick_count = 0  # 진입 시 틱 카운트 초기화
                    execute_trade(position, entry_date, entry_price, None, None, indicator_value, '진입')

            # 지표가 캔들 내에 있을때
            # 포지션이 있을 때
            if was_inside_candle and position is not None:

                entry_tick_count += 1  # 포지션 진입 후 틱 수 증가

                # 최소 보유 틱 이상일 때만 정산 가능
                if position == 'buy' and entry_tick_count >= MIN_HOLD_TICKS and indicator_value >= close_price:
                    execute_trade(position, entry_date, entry_price, date, close_price, indicator_value, '정산')
                    position = None
                elif position == 'sell' and entry_tick_count >= MIN_HOLD_TICKS and indicator_value <= close_price:
                    execute_trade(position, entry_date, entry_price, date, close_price, indicator_value, '정산')
                    position = None

            if was_inside_candle:
                isPosition = True
            else:
                isPosition = False

        except Exception as e:
            # 예외 발생 시 오류 메시지 출력
            print(f"예외 발생: {str(e)}")

        time.sleep(1)

    # 종료 시 포지션이 남아 있으면 정산
    if position is not None:
        trade_log_to_json(f"[포지션 종료] 현재 포지션을 종료합니다: {position}, 진입 날짜: {entry_date}, 진입 가격: {entry_price}")
        # 여기서 강제 정산 수행 (None으로 처리)
        execute_trade(position, entry_date, entry_price, date, close_price, None, '정산')
        position = None


# Flask 라우트 설정
@app.route('/start_bot', methods=['POST'])
def start_bot():
    global bot_running, bot_thread
    if not bot_running:
        bot_running = True
        bot_thread = threading.Thread(target=trading_bot)
        bot_thread.start()
        return jsonify({"status": "Bot started"})
    else:
        return jsonify({"status": "Bot is already running"})


@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    global bot_running, bot_thread
    if bot_running:
        bot_running = False
        bot_thread.join()  # 현재 실행 중인 스레드가 종료될 때까지 대기
        return jsonify({"status": "Bot stopped"})
    else:
        return jsonify({"status": "Bot is not running"})


@app.route('/')
def home():
    return redirect(url_for('main'))


# Define the 'main' endpoint
@app.route('/main')
def main():
    return render_template('main.html')


scope_tick = 1


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


def calculate_slope(lrl):
    if lrl is None:
        return []
    slopes = []
    for i in range(1, len(lrl)):
        if lrl[i] != None and lrl[i - scope_tick] != None:
            slope = (lrl[i] - lrl[i - scope_tick]) / scope_tick
            slopes.append(1 if slope >= 0 else -1)
        else:
            slopes.append(0)
    slopes.insert(0, 0)  # 첫 번째 값은 0으로 삽입
    return []


def get_all_data():
    data = []

    # 선물 마켓을 사용하려면 다음과 같이 futures를 True로 설정합니다.
    client.FUTURES = True

    # 심볼과 시간 간격을 설정하여 캔들스틱 데이터를 가져옵니다.
    symbol = 'BTCUSDT'
    interval = Client.KLINE_INTERVAL_1MINUTE  # 1분 간격의 데이터
    start_str = "1 day ago UTC"  # 1일 전부터 현재까지의 데이터
    klines = client.futures_klines(symbol=symbol, interval=interval, start_str=start_str)

    # 데이터를 처리할 때 사용
    for index, kline in enumerate(klines):
        open_time = datetime.fromtimestamp(kline[0] / 1000).strftime('%Y-%m-%d %H:%M:%S')
        open_price = kline[1]
        high_price = kline[2]
        low_price = kline[3]
        close_price = kline[4]
        volume = kline[5]

        record = {
            'open_time': open_time,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume
        }

        data.append(record)
    return data


# 모든 데이터 제공 API
@app.route('/get_data', methods=['GET'])
def get_data():
    all_data = get_all_data()

    if all_data:
        # Close 가격 추출
        close_prices = [float(record['close']) for record in all_data]

        # LRL 계산
        lrl = calculate_lrl(close_prices, 150)
        lrl_120 = calculate_lrl(close_prices, 120)
        lrl_240 = calculate_lrl(close_prices, 240)
        # lrl_480 = calculate_lrl(close_prices, 480)
        # lrl_640 = calculate_lrl(close_prices, 640)
        # lrl_1200 = calculate_lrl(close_prices, 1200)

        # LRV 계산
        lrv_poly = calculate_lrv_poly(close_prices, 150)
        lrv_poly_120 = calculate_lrv_poly(close_prices, 120)
        lrv_poly_240 = calculate_lrv_poly(close_prices, 240)

        # slope_120 = calculate_slope(lrl_120)
        # slope_240 = calculate_slope(lrl_240)
        # slope_480 = calculate_slope(lrl_480)
        # slope_640 = calculate_slope(lrl_640)
        # slope_1200 = calculate_slope(lrl_1200)

        return jsonify({
            'status': 'success',
            'data': all_data,

            'lrl': lrl,
            'lrl_120': lrl_120,
            'lrl_240': lrl_240,

            'lrv_poly': lrv_poly,
            'lrv_poly_120': lrv_poly_120,
            'lrv_poly_240': lrv_poly_240,

        })
    else:
        return jsonify({'status': 'error', 'message': 'No data found'}), 404


# 지표 별 시뮬레이션
@app.route('/GetTradingLog', methods=['GET'])
def GetTradingLog():
    all_data = get_all_data()

    if all_data:
        # 날짜 및 Close 가격 추출
        candle_data = [(record['open_time'], float(record['close']), float(record['open'])) for record in all_data]

        # Close 가격 추출
        close_prices = [float(record['close']) for record in all_data]

        # 거래 시뮬레이션 실행
        # Simulator = {}
        # Simulator["LRL120"] = simulate_trading(candle_data, calculate_lrl(close_prices, 120))
        # Simulator["POLY120"] = simulate_trading(candle_data, calculate_lrv_poly(close_prices, 120))

        TradeList = {}
        TradeList["거래내역"] = json_to_trades()

        # 결과 반환
        return jsonify(TradeList)
    else:
        return jsonify({'status': 'error', 'message': 'No data found'}), 404


def simulate_trading(candle_data, indicator_data):
    trades = []  # 거래 내역을 저장할 리스트
    position = None  # 현재 포지션 ('buy' or 'sell')
    entry_price = None  # 포지션 진입 가격
    entry_date = None  # 포지션 진입 날짜

    for i in range(len(candle_data)):
        date, close_price, open_price = candle_data[i]  # 날짜와 종가 추출
        indicator_value = indicator_data[i]

        if indicator_value is None:
            continue  # 지표 값이 없으면 건너뜀

        if (open_price <= indicator_value and indicator_value <= close_price) or \
                (close_price <= indicator_value and indicator_value <= open_price):
            if position is None:
                # 포지션이 없는 상태
                if indicator_value < close_price:
                    position = 'buy'
                    entry_price = close_price
                    entry_date = date
                elif indicator_value > close_price:
                    position = 'sell'
                    entry_price = close_price
                    entry_date = date

            else:
                # 포지션이 있는 상태에서 정산 조건 확인
                if position == 'buy' and indicator_value >= close_price:
                    exit_price = close_price
                    profit = round((exit_price - entry_price) / entry_price * 100, 3)  # 수익률 계산
                    trades.append({
                        '포지션': '매수-정산',
                        '진입 날짜': entry_date,
                        '진입 가격': entry_price,
                        '정산 날짜': date,
                        '정산 가격': exit_price,
                        '지표': indicator_value,
                        '수익률': profit
                    })
                    position = None  # 포지션 종료
                elif position == 'sell' and indicator_value <= close_price:
                    exit_price = close_price
                    profit = round((entry_price - exit_price) / entry_price * 100, 3)  # 수익률 계산
                    trades.append({
                        '포지션': '매도-정산',
                        '진입 날짜': entry_date,
                        '진입 가격': entry_price,
                        '정산 날짜': date,
                        '정산 가격': exit_price,
                        '지표': indicator_value,
                        '수익률': profit
                    })
                    position = None  # 포지션 종료

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
    trades.reverse()
    return trades


if __name__ == '__main__':
    app.run(debug=True, port=5600)
