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

#############################
## 자동 매매 설정
#############################

server_url = "https://api.upbit.com/"

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

# UPBIT API 연동 키 값 설정
def GetAuth(params):
    access_key = "VdBOjwKA7Xbrz1N33l33hg2xeUUuv94pTPwRMEOJ"
    secret_key = "p4fGRAL8DL3RxFx5Y8eDHeYBoKclg09CkA8kBLKJ"

    # 쿼리 문자열 생성 및 해싱
    query_string = unquote(urlencode(params, doseq=True)).encode("utf-8")
    m = hashlib.sha512()
    m.update(query_string)
    query_hash = m.hexdigest()

    # JWT 페이로드 생성
    payload = {
        'access_key': access_key,
        'nonce': str(uuid.uuid4()),
        'query_hash': query_hash,
        'query_hash_alg': 'SHA512',
    }

    # JWT 토큰 생성
    jwt_token = jwt.encode(payload, secret_key)
    authorization = 'Bearer {}'.format(jwt_token)
    headers = {
        'Authorization': authorization,
    }
    return headers

# 현재 잔액 확인 방법
def GetBalance(currency):
    # API 요청에 필요한 params 정의 (여기서는 비어있는 상태로 설정)
    params = {}

    if currency == "KRW" :
        currency = "KRW"
    else:
        currency = currency.replace("KRW-" , "")

    res = requests.get(server_url + 'v1/accounts', params=params, headers=GetAuth(params))
    for item in res.json():
        if item['currency'] == currency:
            return float(item['balance'])  # 'balance'를 float으로 변환하여 반환
    return 0  # 해당 통화가 없을 경우 None 반환


def SetMarketOrder(market, side, ord_type, price = "", volume = ""):
    # 요청 파라미터 정의
    params = {
        'market': market,
        'side': side,
        'ord_type': ord_type,
        'price': price,
        'volume': volume
    }

    # 주문 요청 전송
    res = requests.post(server_url + '/v1/orders', json=params, headers=GetAuth(params))
    print(res.json())
    # 응답을 JSON 형식으로 반환
    return res.json()

def GetNowTime() :
    # 현재 날짜와 시간 가져오기
    now = datetime.now()

    # 특정 형식으로 날짜와 시간 출력 (예: YYYY-MM-DD HH:MM:SS)
    return now.strftime('%Y-%m-%d %H:%M:%S')


def SellAllMarket() :
    # 구매 되어야 할 코인
    # RSI 값이 0 이상이고 BuyRSI 값보다 작은 것 검색

    print("################## 전량 매도 "+GetNowTime()+" ###########################")


    # 결과 출력
    url = "https://api.upbit.com/v1/market/all?isDetails=false"

    headers = {"accept": "application/json"}

    res = requests.get(url, headers=headers)

    for row in res.json():
        MarketID = row["market"]
        if "KRW" not in row["market"]:
            continue
        MarketBalance = GetBalance(MarketID)
        if MarketBalance > 0 :
            print(MarketID + "를 매도 합니다.  해당 코인 보유액 : " + str(MarketBalance))
            SetMarketOrder(MarketID , "ask" , "market" , "" , MarketBalance)

    print("########################################################################")
    print("")
    print("")

    # 1 초 동안 대기 , too many request를 피하기 위함
    time.sleep(1)

SellAllMarket()


MarketDB.close()