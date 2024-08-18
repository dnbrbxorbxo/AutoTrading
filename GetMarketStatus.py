import json
import time
from datetime import datetime

import jwt
import os
import uuid
import requests

server_url = "https://api.upbit.com/"

# UPBIT API 연동 키 값 설정
def GetAuth():
    access_key = "VdBOjwKA7Xbrz1N33l33hg2xeUUuv94pTPwRMEOJ"
    secret_key = "p4fGRAL8DL3RxFx5Y8eDHeYBoKclg09CkA8kBLKJ"

    payload = {
        'access_key': access_key,
        'nonce': str(uuid.uuid4()),
    }

    jwt_token = jwt.encode(payload, secret_key, algorithm='HS256')
    authorization = 'Bearer {}'.format(jwt_token)
    headers = {
        'Authorization': authorization,
    }
    return headers


# 현재 잔액 확인 방법
def GetBalance(currency):
    # API 요청에 필요한 params 정의 (여기서는 비어있는 상태로 설정)
    params = {}

    res = requests.get(server_url + 'v1/accounts', params=params, headers=GetAuth())
    print(res.json())
    for item in res.json():
        if item['currency'] == currency:
            return float(item['balance'])  # 'balance'를 float으로 변환하여 반환
    return 0  # 해당 통화가 없을 경우 None 반환

def GetCoinList() :
    url = "https://api.upbit.com/v1/market/all?isDetails=false"

    headers = {"accept": "application/json"}

    res = requests.get(url, headers=headers)

    for row in res.json():
        if "KRW" not in row["market"]:
            continue

        SetMarketStatus(row["market"] , row["korean_name"] , row["english_name"])


def SetMarketStatus(MarketID, korean_name, english_name):
    print("####################################################################################################")
    print(f"종목 ID: {MarketID}, 한글 이름: {korean_name}, 영어 이름: {english_name}")

    # URL to fetch the JSON data
    url = f"https://api.upbit.com/v1/candles/minutes/1?market={MarketID}&count=1200"
    print(f"데이터를 가져올 URL: {url}")

    # Fetch the JSON data from the URL
    response = requests.get(url)
    print("데이터를 요청 중입니다...")

    # Check if the request was successful
    if response.status_code == 200:
        print("데이터 요청 성공!")

        # Parse the JSON data
        new_data = response.json()

        # Create the folder path based on the market ID
        folder_path = f"./MarketData/{MarketID}"
        print(f"폴더 경로: {folder_path}")

        # Create the folder if it doesn't exist
        os.makedirs(folder_path, exist_ok=True)
        print("폴더가 존재하지 않으면 새로 만듭니다.")

        # Get the current date for the filename
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Define the filename based on the market ID and the current date
        filename = f"{folder_path}/{MarketID}_{current_date}.json"
        print(f"저장할 파일 이름: {filename}")

        # Load existing data if the file exists
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            print("기존 데이터를 불러왔습니다.")
        else:
            existing_data = []
            print("기존 데이터가 없습니다. 새로운 파일을 생성합니다.")

        # Filter out duplicate data
        existing_timestamps = {entry['timestamp'] for entry in existing_data}
        unique_new_data = [entry for entry in new_data if entry['timestamp'] not in existing_timestamps]

        if unique_new_data:
            # Append new unique data to the existing data
            updated_data = existing_data + unique_new_data

            # Save the updated JSON data to the file
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(updated_data, f, ensure_ascii=False, indent=4)

            print(f"새로운 데이터가 {filename}에 성공적으로 업데이트되었습니다.")
        else:
            print("추가할 새로운 데이터가 없습니다.")

        time.sleep(0.2)

    else:
        print(f"데이터 요청 실패! 상태 코드: {response.status_code}")
def TimeStampToDate(timestamp ) :
    # 타임스탬프를 밀리초 단위에서 초 단위로 변환
    timestamp_seconds = timestamp / 1000

    # 변환된 타임스탬프를 datetime 객체로 변환
    dt_object = datetime.fromtimestamp(timestamp_seconds)

    # 문자열로 변환하여 출력
    formatted_datetime = dt_object.strftime('%Y-%m-%d %H:%M:%S')
    return formatted_datetime


def CalcRSI(MarketID , MarketList_RSI , window) :
    # Market 테이블에서 MarketID와 MarketTime이 최근순으로 정렬된 결과 중 상위 100개 선택
    query = (Market
             .select()
             .where(Market.MarketID == MarketID)
             .order_by(Market.MarketTime.desc())
             .limit(window))

    # 쿼리 결과를 순회하며 RSI 계산을 위한 가격 데이터 입력
    for TradingData in query:
        MarketList_RSI.append(float(TradingData.MarketPrice))

    RSI = GetMarketRSI(MarketList_RSI, len(MarketList_RSI))
    return RSI

def GetMarketRSI(prices, period=14) :
    """
    Calculate the Relative Strength Index (RSI) for a given list of prices.

    :param prices: List of closing prices (most recent price at the end of the list)
    :param period: RSI period, default is 14
    :return: RSI value
    """
    deltas = [prices[i + 1] - prices[i] for i in range(len(prices) - 1)]
    gains = [delta if delta > 0 else 0 for delta in deltas]
    losses = [-delta if delta < 0 else 0 for delta in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(prices)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100
    else:
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))


# 함수 호출 및 결과 출력
KRW = GetBalance("KRW")
print("KRW Balance: " + str(KRW))

while True:
    GetCoinList()

MarketDB.close()