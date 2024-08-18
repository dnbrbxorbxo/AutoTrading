import json
import os
import time
from binance.client import Client
from datetime import datetime

# 바이낸스 API 키와 시크릿 설정
api_key = 'JWqsyuCmFvRReL39NbCqsZowGqoBCCGnX6XCjRr7VjZySpj2TsL7AKYl6eq1tQcT'
api_secret = 'KxH5oV6EFqeTbOG3KpAlDXUAmhDxoldIdkSfX8QLDhR9BDIRmed9mKLi200Y1vIy'

# 클라이언트 인스턴스 생성
client = Client(api_key, api_secret)

# 선물 마켓을 사용하려면 다음과 같이 futures를 True로 설정합니다.
client.FUTURES = True

# 심볼과 시간 간격을 설정하여 캔들스틱 데이터를 가져옵니다.
symbol = 'BTCUSDT'
interval = Client.KLINE_INTERVAL_1MINUTE  # 1분 간격의 데이터
start_str = "1 day ago UTC"  # 1일 전부터 현재까지의 데이터

# 데이터를 저장할 상대 경로 설정
base_directory = os.path.join(os.path.dirname(__file__), 'FUTURE_DATA')


while True:
    # 캔들스틱 데이터 요청
    klines = client.futures_klines(symbol=symbol, interval=interval, start_str=start_str)

    # 데이터를 처리할 때 사용
    for index, kline in enumerate(klines):
        open_time = datetime.fromtimestamp(kline[0] / 1000).strftime('%Y-%m-%d %H:%M:%S')
        open_price = kline[1]
        high_price = kline[2]
        low_price = kline[3]
        close_price = kline[4]
        volume = kline[5]

        # 날짜별로 파일명을 생성
        date_key = open_time.split(' ')[0]
        json_file = os.path.join(base_directory, f'{date_key}.json')

        # JSON 파일에서 기존 데이터를 불러옵니다.
        if os.path.exists(json_file):
            with open(json_file, 'r') as file:
                data = json.load(file)
        else:
            data = []

        # 중복된 시간이 아닌 경우에만 데이터를 추가
        record = {
            'open_time': open_time,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume
        }

        # 이미 존재하는지 확인
        if not any(item['open_time'] == open_time for item in data):
            data.append(record)
            print(f"Data for {symbol} at {open_time} added to {json_file}")
        else:
            # 마지막 데이터 포인트의 경우 업데이트를 강제 수행
            if index == len(klines) - 1:
                for i in range(len(data)):
                    if data[i]['open_time'] == open_time:
                        data[i] = record
                        print(f"Data for {symbol} at {open_time} updated in {json_file}")
                        break

        # 업데이트된 데이터를 JSON 파일에 기록
        with open(json_file, 'w') as file:
            json.dump(data, file, indent=4)

    # 일정 시간 대기 후 다시 요청 (여기서는 60초 대기)
    time.sleep(20)