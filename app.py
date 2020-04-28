import hashlib
import time
import ldap
import jwt
import socketio
from aiohttp import web
from aiohttp_jwt import JWTMiddleware, check_permissions, match_any
from views import configs, zabbixFunc, service, sm_report, servicetasks, monitoring_add, monitoring_add_di, \
    event_dashboard, template_report, monitoring, server_report, zabbixWan, maintenance
from scripts.help_functions import json_response,db_connect,tbl_users, tbl_app_config, \
    create_logger, JWT_ALGORITHM, JWT_EXP_DELTA_SECONDS, JWT_IATEXP_DELTA_SECONDS, \
    JWT_SECRET,create_config, get_ldap_params, get_role
from views.ws import sio
import logging

#sio = socketio.AsyncServer(async_handlers=True) #client_manager=socketio.RedisManager('redis://127.0.0.1:6379/0'),

async def ldap_login(user,passw, conf):
    '''
    :param user:
    :param passw:
    :return: tuple of FIO, Alpha-Mail, Sigma-Mail
    '''
    FIO = mail = sigma_mail = ''
    conn = ldap.initialize(conf['url'])
    conn.protocol_version = 3
    conn.set_option(ldap.OPT_REFERRALS, 0)
    try:
        conn.simple_bind_s(user, passw)
    except ldap.INVALID_CREDENTIALS:
        return False
    else:
        ldap_base = conf['base']
        query = f'(cn={user.split("@")[0]})'
        res = conn.search_s(ldap_base, ldap.SCOPE_SUBTREE, query)
        if 'displayName' in res[0][1]:
            FIO = res[0][1]['displayName'][0].decode('utf8').strip()
        if 'mail' in res[0][1]:
            mail = res[0][1]['mail'][0].decode('utf8').strip()
        if 'extensionAttribute9' in res[0][1]:
            sigma_mail = res[0][1]['extensionAttribute9'][0].decode('utf8').strip()
        return FIO,mail,sigma_mail

async def obtaint(request):
    post_data = await request.json()
    username = post_data['username']
    if r'/' in username:
        domain, username = username.split(r'/')
        username = username + '@' + domain
    else:
        username = username + '@' +  request.app['ldap']['domain']
    username = username.lower()
    passw = post_data['password']
    try:
        engine = await db_connect()
        async with engine.acquire() as conn:
            res = await conn.execute(tbl_users.select().where(tbl_users.c.login == post_data['username'].lower()))
            result = await res.fetchall()
        engine.close()
        if len(result) > 0:
            result = result[0]
            if result[7] == True:
                role = get_role(request.app['app_config'],result[6])
                if result[2] == hashlib.md5(bytes(post_data['password'],encoding='utf8')).hexdigest():
                    payload = {
                        'role':role, #result[6],
                        'user_id': result[1],
                        'exp': int(time.time()) + JWT_EXP_DELTA_SECONDS,
                        'orig_iat': int(time.time()) + JWT_IATEXP_DELTA_SECONDS,
                        'name' : result[3]
                    }
                    jwt_token = jwt.encode(payload, JWT_SECRET, JWT_ALGORITHM)
                    return json_response({'token': jwt_token.decode('utf-8')})
                else:
                    ldap_result = await ldap_login(username, passw, request.app['ldap'])
                    if ldap_result:
                        firstname, mail, mail_sigma = ldap_result
                        engine = await db_connect()
                        async with engine.acquire() as conn:
                            await conn.execute(
                                tbl_users.update().values(pw_hash=hashlib.md5(
                                    bytes(passw, encoding='utf8')).hexdigest(), firstname=firstname, mail = mail, mail_sigma=mail_sigma).where(tbl_users.c.login == post_data['username'].lower()))
                            await conn.execute("commit")
                        payload = {
                            'role': role,#'guest',
                            'user_id': post_data['username'].lower(),
                            'exp': int(time.time()) + JWT_EXP_DELTA_SECONDS,
                            'orig_iat': int(time.time()) + JWT_IATEXP_DELTA_SECONDS,
                            'name': firstname
                        }
                        jwt_token = jwt.encode(payload, JWT_SECRET, JWT_ALGORITHM)
                        return json_response({'token': jwt_token.decode('utf-8')})
                    else:
                        return json_response({'message': 'Wrong credentials'}, status=400)
            else:
                return json_response({'message': 'Wrong credentials'}, status=400)
        else: #try to create uz from ldap
            ldap_result = await ldap_login(username, passw, request.app['ldap'])
            if ldap_result:
                firstname, mail, mail_sigma = ldap_result
                engine = await db_connect()
                async with engine.acquire() as conn:
                    await conn.execute(tbl_users.insert().values(login=post_data['username'].lower(), pw_hash=hashlib.md5(
                        bytes(post_data['password'],  encoding='utf8')).hexdigest(), firstname=firstname, mail = mail, mail_sigma = mail_sigma, groups='guest', enable=1))
                    await conn.execute("commit")
                engine.close()
                role = get_role(request.app['app_config'], 'guest')
                payload = {
                    'role': role,
                    'user_id': post_data['username'].lower(),
                    'exp': int(time.time()) + JWT_EXP_DELTA_SECONDS,
                    'orig_iat': int(time.time()) + JWT_IATEXP_DELTA_SECONDS,
                    'name': firstname
                }
                jwt_token = jwt.encode(payload, JWT_SECRET, JWT_ALGORITHM)
                return json_response({'token': jwt_token.decode('utf-8')})
            else:
                return json_response({'message': 'Wrong credentials'}, status=400)
    except Exception as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
    return json_response({'message': 'Wrong credentials'}, status=400)


async def refresht(request):
    post_data = await request.json()
    try:
        jwtd = jwt.decode(post_data['token'], JWT_SECRET,
                                         algorithms=[JWT_ALGORITHM],options={'verify_exp': False})
        engine = await db_connect()
        async with engine.acquire() as conn:
            res = await conn.execute(tbl_users.select().where(tbl_users.c.login == jwtd['user_id']))
            result = await res.fetchone()
        engine.close()
        if (jwtd['exp'] < jwtd['orig_iat']) and (get_role(request.app['app_config'],result[6]) == jwtd['role']) and (result[7] == True):
            jwtd['exp'] = int(time.time()) + JWT_EXP_DELTA_SECONDS
            jwt_token = jwt.encode(jwtd, JWT_SECRET, JWT_ALGORITHM)
            return json_response({'token': jwt_token.decode('utf-8')})
    except Exception as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
    return json_response({'result': False}, status=400)


@check_permissions([
    'admin'
], permissions_property = 'role', comparison=match_any)
async def get_user_list(request):
    engine = await db_connect()
    async with engine.acquire() as conn:
        res = await conn.execute(tbl_users.select())
        result = await res.fetchall()
    engine.close()
    return json_response({'result': 'True','rows': [dict(r) for r in result]})

@check_permissions([
    'admin'
], permissions_property = 'role', comparison=match_any)
async def update_user(request):
    post_data = await request.json()
    row = post_data['row']
    try:
        engine = await db_connect()
        async with engine.acquire() as conn:
            await conn.execute(
                tbl_users.update().values(groups=row['groups'],
                                          enable=row['enable']).where(tbl_users.c.login == row['login'].lower()))
            await conn.execute("commit")

        engine.close()
        return json_response({'result': 'True'})
    except BaseException as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
    return json_response({'result': False})

async def ping(request):
    return web.Response(body='Pong')

app = web.Application(middlewares=[
        JWTMiddleware(
            secret_or_pub_key=JWT_SECRET,
            request_property='user',
            credentials_required=False,
            whitelist=['/api/auth/*', '/api/ws/*'],
            algorithms=[JWT_ALGORITHM]
        )
    ])


jwt_logger = logging.getLogger('aiohttp_jwt.middleware')
jwt_logger.addHandler(logging.NullHandler())

app.add_routes([web.get('/api/auth/ping', ping),
                web.post('/api/auth/obtain_token', obtaint),
                web.post('/api/auth/refresh_token', refresht),
                web.post('/api/get_user_list', get_user_list),
                web.post('/api/update_user', update_user)])
app.add_routes(maintenance.MaintenanceRoutes)
app.add_routes(zabbixWan.zabbixWanRoutes)
app.add_routes(zabbixFunc.ZabbixRoutes)
app.add_routes(service.ServiceRoutes)
app.add_routes(configs.ConfigsRoutes)
app.add_routes(sm_report.SM_Routes)
app.add_routes(servicetasks.ServiceTasksRoutes)
app.add_routes(event_dashboard.EventDashboardRoutes)
app.add_routes(monitoring_add.MonitoringAddRoutes)
app.add_routes(monitoring_add_di.MonitoringAddDiRoutes) # deprecated
app.add_routes(monitoring.MonitoringRoutes)
app.add_routes(template_report.TemplateReport_Routes)
app.add_routes(server_report.ServerReport_Routes)
app['app_config'] = create_config('app.conf')
app['uz_logger'] = create_logger(app['app_config'],'fileuz')
app['uz_logger'].propagate = False
app['app_logger'] = create_logger(app['app_config'], 'app', 20000000)
app['app_logger'].propagate = False
app['zabbix_wan_logger'] = create_logger(app['app_config'], 'zabbix_wan')
app['zabbix_wan_logger'].propagate = False
app['config_logger'] = create_logger(app['app_config'], 'config')
app['config_logger'].propagate = False
app['monitoring_add_logger'] = create_logger(app['app_config'], 'monitoring_add')
app['monitoring_add_logger'].propagate = False
app['maintenance_logger'] = create_logger(app['app_config'],'maintenance')
app['maintenance_logger'].propagate = False
app['eventdashboard_logger'] = create_logger(app['app_config'], 'eventdashboard', 1000000000)
app['eventdashboard_logger'].propagate = False
app['ldap'] = get_ldap_params(app['app_config'])

sio.attach(app, socketio_path='/api/ws')

if __name__ == "__main__":
    web.run_app(app, host='127.0.0.1', port=8000) #comment line for prod
