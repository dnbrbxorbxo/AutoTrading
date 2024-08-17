import socketio
import json

# 서버 URL
server_url = 'http://mps.socket.dnbsoft.com'

# 클라이언트 생성
sio = socketio.Client()

# 이벤트 핸들러 설정
@sio.event
def connect():
    print('Connection established')
    # 서버로 등록 정보 전송
    sio.emit('register', {'code': 'crefarm', 'from': 'your_from', 'name': 'your_name'})

@sio.event
def connect_error(data):
    print('Connection failed')

@sio.event
def disconnect():
    print('Disconnected from server')

@sio.on('response')
def on_message(data):
    print(f'Received message from server: {data}')

@sio.on('request_code')
def on_request_code(data):
    print(f'Server requested code: {data}')

# 서버에 연결
sio.connect(server_url)

# 대기
sio.wait()
