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

import matplotlib.pyplot as plt
import pandas as pd
import matplotlib

matplotlib.use('TkAgg')  # 백엔드를 Agg로 설정


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




def plot_rsi_chart(indices, rsi14, rsi20, rsi50 , rsi100 ,price):
    """
    RSI 값을 차트로 그리는 함수

    :param time: 시간 데이터 (리스트 또는 pandas Series)
    :param rsi1: 첫 번째 RSI 데이터 (리스트 또는 pandas Series)
    :param rsi2: 두 번째 RSI 데이터 (리스트 또는 pandas Series)
    :param rsi3: 세 번째 RSI 데이터 (리스트 또는 pandas Series)
    """
    fig, ax1 = plt.subplots(figsize=(14, 7))

    # 첫 번째 y축 (RSI)
    ax1.plot(indices, rsi14, label='RSI 14', color='blue')
    ax1.plot(indices, rsi20, label='RSI 20', color='green')
    ax1.plot(indices, rsi50, label='RSI 50', color='red')
    ax1.plot(indices, rsi100, label='RSI 100', color='purple')

    ax1.set_xlabel('Index')
    ax1.set_ylabel('RSI Value')
    ax1.legend(loc='upper left')
    ax1.grid(True)

    # 두 번째 y축 (Price)
    ax2 = ax1.twinx()
    ax2.plot(indices, price, label='Price', color='orange', alpha=0.6)
    ax2.set_ylabel('Price')
    ax2.legend(loc='upper right')

    plt.title('RSI and Price Chart')

    # x축 값들이 잘 보이도록 설정
    # x 축 레이블 회전
    plt.xticks(rotation=45)

    plt.show()


query = (Market
             .select()
             .where(Market.MarketID == TargetMarket[0] )
             .order_by(Market.MarketTime.desc())
             .limit(1000))

indices = []
RSI14 = []
RSI20 = []
RSI50 = []
RSI100 = []
price = []

# 쿼리를 실행하고 결과를 리스트로 변환
results = list(query)

# 결과를 뒤집기
results.reverse()
# 쿼리 결과를 순회하며 RSI 계산을 위한 가격 데이터 입력
for RSIList in results:

    # 문자열을 datetime 객체로 파싱
    dt = datetime.strptime(RSIList.MarketTime, "%Y-%m-%d %H:%M:%S")

    # 시간 부분만 추출하여 문자열로 변환
    time_str = dt.strftime("%M:%S")
    indices.append(time_str)

    RSI14.append(float(RSIList.MarketRSI14))
    RSI20.append(float(RSIList.MarketRSI20))
    RSI50.append(float(RSIList.MarketRSI50))
    RSI100.append(float(RSIList.MarketRSI100))
    price.append(float(RSIList.MarketPrice))


# RSI 차트 그리기
plot_rsi_chart(indices, RSI14, RSI20, RSI50 , RSI100 , price)

