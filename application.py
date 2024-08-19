import numpy as np
from flask import Flask, jsonify, request, render_template, redirect, url_for
import os
import json
from datetime import datetime

app = Flask(__name__)

# 데이터가 저장된 폴더 설정 (상대 경로)
base_directory = os.path.join(os.path.dirname(__file__), 'FUTURE_DATA')


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
        if lrl[i] != None and lrl[i - scope_tick] != None :
            slope = (lrl[i] - lrl[i - scope_tick]) / scope_tick
            slopes.append(1 if slope >= 0 else -1)
        else:
            slopes.append(0)
    slopes.insert(0, 0)  # 첫 번째 값은 0으로 삽입
    return []

# 모든 데이터 제공 API
@app.route('/get_data', methods=['GET'])
def get_data():
    all_data = []

    # FUTURE_DATA 폴더 내의 모든 JSON 파일을 읽음
    for filename in os.listdir(base_directory):
        if filename.endswith('.json'):
            json_file = os.path.join(base_directory, filename)
            with open(json_file, 'r') as file:
                data = json.load(file)
                all_data.extend(data)  # 모든 데이터를 결합

    if all_data:
        # Close 가격 추출
        close_prices = [float(record['close']) for record in all_data]

        # LRL 계산
        lrl_120 = calculate_lrl(close_prices, 120)
        lrl_240 = calculate_lrl(close_prices, 240)
        lrl_480 = calculate_lrl(close_prices, 480)
        lrl_640 = calculate_lrl(close_prices, 640)
        lrl_1200 = calculate_lrl(close_prices, 1200)

        # LRV 계산
        lrv_poly = calculate_lrv_poly(close_prices, 640)

        slope_120 = calculate_slope(lrl_120)
        slope_240 = calculate_slope(lrl_240)
        slope_480 = calculate_slope(lrl_480)
        slope_640 = calculate_slope(lrl_640)
        slope_1200 = calculate_slope(lrl_1200)

        return jsonify({
            'status': 'success',
            'data': all_data,

            'lrl_120': lrl_120,
            'lrl_240': lrl_240,
            'lrl_480': lrl_480,
            'lrl_640': lrl_640,
            'lrl_1200': lrl_1200,

            'lrv_poly': lrv_poly,

            'slope_120': slope_120,
            'slope_240': slope_240,
            'slope_480': slope_480,
            'slope_640': slope_640,
            'slope_1200': slope_1200
        })
    else:
        return jsonify({'status': 'error', 'message': 'No data found'}), 404

# 지표 별 시뮬레이션
@app.route('/GetTradingSimulate', methods=['GET'])
def GetTradingSimulate():
    all_data = []

    # FUTURE_DATA 폴더 내의 모든 JSON 파일을 읽음
    for filename in os.listdir(base_directory):
        if filename.endswith('.json'):
            json_file = os.path.join(base_directory, filename)
            with open(json_file, 'r') as file:
                data = json.load(file)
                all_data.extend(data)  # 모든 데이터를 결합

    if all_data:
        # 날짜 및 Close 가격 추출
        candle_data = [(record['open_time'], float(record['close'])) for record in all_data]

        # Close 가격 추출
        close_prices = [float(record['close']) for record in all_data]

        # 거래 시뮬레이션 실행
        Simulator = {}
        Simulator["poly"] = simulate_trading(candle_data, calculate_lrv_poly(close_prices, 640))
        Simulator["LRL640"] = simulate_trading(candle_data, calculate_lrl(close_prices, 640))
        Simulator["LRL1200"] = simulate_trading(candle_data, calculate_lrl(close_prices, 1200))

        # 결과 반환
        return jsonify(Simulator)
    else:
        return jsonify({'status': 'error', 'message': 'No data found'}), 404

def simulate_trading(candle_data, indicator_data):
    trades = []  # 거래 내역을 저장할 리스트
    position = None  # 현재 포지션 ('buy' or 'sell')
    entry_price = None  # 포지션 진입 가격
    entry_date = None  # 포지션 진입 날짜

    for i in range(len(candle_data)):
        date, close_price = candle_data[i]  # 날짜와 종가 추출
        indicator_value = indicator_data[i]

        if indicator_value is None:
            continue  # 지표 값이 없으면 건너뜀

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
                profit = round((exit_price - entry_price) / entry_price * 100 , 3)  # 수익률 계산
                trades.append({
                    '포지션': '매수-정산',
                    '진입 날짜': entry_date,
                    '진입 가격': entry_price,
                    '정산 날짜': date,
                    '정산 가격': exit_price,
                    '수익률': profit
                })
                position = None  # 포지션 종료
            elif position == 'sell' and indicator_value <= close_price:
                exit_price = close_price
                profit = round((entry_price - exit_price) / entry_price * 100 , 3)  # 수익률 계산
                trades.append({
                    '포지션': '매도-정산',
                    '진입 날짜': entry_date,
                    '진입 가격': entry_price,
                    '정산 날짜': date,
                    '정산 가격': exit_price,
                    '수익률': profit
                })
                position = None  # 포지션 종료

    return trades


if __name__ == '__main__':
    app.run(debug=True , port=5600)
