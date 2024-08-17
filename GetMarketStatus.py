import time
from datetime import datetime

import jwt
import hashlib
import os
import requests
import uuid
import requests
from urllib.parse import urlencode, unquote
import sqlite3
from peewee import SqliteDatabase, Model, CharField, IntegerField

server_url = "https://api.upbit.com/"
# 배열 정의
TargetMarket = ["KRW-ETC" , "KRW-XRP" , "KRW-ETH"]


MarketDB = SqliteDatabase('AutoTrading.db')
# 모델 정의
class Market(Model):
    MarketKOR = CharField()
    MarketID = CharField()
    MarketENG = CharField()

    MarketPrice = CharField()
    MarketTime = CharField()

    MarketHighPrice = CharField()
    MarketLowPrice = CharField()

    MarketRSI14 = CharField()
    MarketRSI20 = CharField()
    MarketRSI50 = CharField()
    MarketRSI100 = CharField()

    class Meta:
        database = MarketDB

class MarketRSI(Model):
    MarketKOR = CharField()
    MarketID = CharField()
    MarketENG = CharField()

    MarketRSI14 = CharField()
    MarketRSI20 = CharField()
    MarketRSI50 = CharField()
    MarketRSI100 = CharField()

    class Meta:
        database = MarketDB

# 데이터베이스 연결 (해당 파일이 없으면 새로 생성)
MarketDB.connect()
MarketDB.create_tables([Market , MarketRSI])

print("데이터 베이스 연결")


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

        if row["market"] in TargetMarket:
            SetMarketStatus(row["market"] , row["korean_name"] , row["english_name"])

def SetMarketStatus(MarketID , korean_name , english_name) :
    print("####################################################################################################")
    MarketStatus = GetCoinTick(MarketID)[0]

    # RSI 계산을 위해 현재 시세 데이터 배열에 추가
    MarketList_RSI = []
    MarketList_RSI.append(float(MarketStatus["trade_price"]))

    RSI14 = CalcRSI(MarketID , MarketList_RSI , 14)
    RSI20 = CalcRSI(MarketID , MarketList_RSI , 20)
    RSI50 = CalcRSI(MarketID , MarketList_RSI , 50)
    RSI100 = CalcRSI(MarketID , MarketList_RSI , 100)


    MarketData = {
        "MarketKOR": korean_name,
        "MarketID": MarketID,
        "MarketENG": english_name,

        "MarketPrice": MarketStatus["trade_price"],
        "MarketTime": TimeStampToDate(MarketStatus["trade_timestamp"]),

        "MarketHighPrice": MarketStatus["high_price"],
        "MarketLowPrice": MarketStatus["low_price"],

        "MarketRSI14": RSI14,
        "MarketRSI20": RSI20,
        "MarketRSI50": RSI50,
        "MarketRSI100": RSI100
    }
    print(MarketData)
    Market.create(**MarketData)

    # 새로운 데이터를 삽입
    query = MarketRSI.delete().where(MarketRSI.MarketID == MarketID)
    query.execute()
    MarketRSIData = {
        "MarketKOR": korean_name,
        "MarketID": MarketID,
        "MarketENG": english_name,

        "MarketRSI14": RSI14,
        "MarketRSI20": RSI20,
        "MarketRSI50": RSI50,
        "MarketRSI100": RSI100
    }
    print(MarketRSIData)
    MarketRSI.create(**MarketRSIData)

    print("####################################################################################################")

    # 0.1 초 동안 대기 , too many request를 피하기 위함
    time.sleep(0.5)


def GetCoinTick(CoinID) :
    import requests

    url = "https://api.upbit.com/v1/ticker?markets="+CoinID

    headers = {"accept": "application/json"}

    response = requests.get(url, headers=headers)
    return response.json()


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