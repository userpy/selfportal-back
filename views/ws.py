import socketio
import jwt
from scripts.help_functions import JWT_ALGORITHM, JWT_SECRET


sio = socketio.AsyncServer(async_handlers=True, client_manager=socketio.AsyncRedisManager('redis://localhost:6379/0'))

@sio.on('connect')
async def connect(sid, environ):
    room = environ['QUERY_STRING'].split('&')[0].split('=')[1]
    token = environ['QUERY_STRING'].split('&')[1].split('=')[1]
    role = jwt.decode(token, JWT_SECRET,algorithms=[JWT_ALGORITHM],options={'verify_exp': False})['role']
    sio.enter_room(sid,room)
    #print("connect ", sid, role,room)
    if not list(set(role.split(';')) & set(['eventdashboard'])):
        return False
    #return True

@sio.on('disconnect')
async def disconnected(sid):
    pass
    #sio.leave_room(sid,'eventdashboard')
    #(sio.rooms(sid))
    #print("disconnect ", sid)
