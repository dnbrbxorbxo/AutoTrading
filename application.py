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

        return jsonify({
            'status': 'success',
            'data': all_data,
            'lrl_120': lrl_120,
            'lrl_240': lrl_240,
            'lrl_480': lrl_480,
            'lrl_640': calculate_lrl(close_prices, 640),
            'lrl_1200': calculate_lrl(close_prices, 1200)
        })
    else:
        return jsonify({'status': 'error', 'message': 'No data found'}), 404


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
            lrl.append(m * (window_size - 1) + c)
    return lrl

if __name__ == '__main__':
    app.run(debug=True , port=5600)
