from aiohttp import web
from scripts.help_functions import json_response, db_connect, tbl_users, JWT_ALGORITHM, JWT_SECRET
from scripts.help_functions_zbx import get_allowed_grps, zabbix_conn, get_zabbix_conf, get_showed_zabbix, async_zabbix_conn
from scripts.help_functions_stand_check import get_proxy_ip, getsearch
from scripts.add_user import add_user
from aiohttp_jwt import check_permissions, match_any
import re
import jwt
from functools import partial
import asyncio

ZabbixRoutes = web.RouteTableDef()


@ZabbixRoutes.post('/api/zabbix/user_exist_check')
@check_permissions([
    'zabbixuz'
], permissions_property='role', comparison=match_any)
async def user_exist_check(request):
    try:
        post_data = await request.json()
        username = post_data['username']
        source = post_data['source']
        zapi = await async_zabbix_conn(source)
        user = await zapi.user.get(output='extend', filter={'alias': username},
                             selectMedias=['mediatypeid', 'sendto', 'active'], selectMediatype='extend',
                             selectUsrgrps=['name'])
        await zapi.close()
    except BaseException as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False})
    else:
        if len(user) > 0:
            user = user[0]
            ZabbixConfig = await get_zabbix_conf()
            if '(' in user['surname']:
                res = re.findall('(.*)\((.+)\)', user['surname'])[0]
                user['surname'] = res[0]
                user['sigma_login'] = res[1]
            else:
                user['sigma_login'] = ''

            user['phonemedia'] = {'sendto': '', 'active': 1}
            user['sigmamailmedia'] = {'sendto': '', 'active': 1}
            user['mailmedia'] = {'sendto': '', 'active': 1}
            for media in user['medias']:
                if media['mediatypeid'] == str(ZabbixConfig[source]['phone_media_type']):
                    user['phonemedia'] = media
                elif media['mediatypeid'] == str(ZabbixConfig[source]['email_media_type']):
                    str_for_chechk = media['sendto'] if isinstance(media['sendto'], str) else media['sendto'][0]
                    if '@sberbank.ru' in str_for_chechk:
                        user['sigmamailmedia'] = media
                    else:
                        user['mailmedia'] = media
            allowed_groups = await get_allowed_grps(source, with_id=True)
            user['selected_grps'] = []
            for grp in user['usrgrps']:
                if grp['name'] in allowed_groups:
                    user['selected_grps'].append(grp['name'])
                elif grp['name'].split('_')[-1] in allowed_groups.values():
                    user['selected_grps'].append(
                        list(allowed_groups.keys())[list(allowed_groups.values()).index(grp['name'].split('_')[-1])])
            return json_response({'result': True, 'user': user, 'allowed_groups': list(allowed_groups.keys())})
        else:
            return json_response({'result': False})

@ZabbixRoutes.post('/api/zabbix/get_user_params')
@check_permissions([
    'zabbixuz'
], permissions_property='role', comparison=match_any)
async def get_user_params(request):
    try:
        post_data = await request.json()
        username = post_data['username']
        source = post_data['source']
        engine = await db_connect()
        async with engine.acquire() as conn:
            res = await conn.execute(tbl_users.select().where(tbl_users.c.login == username))
            result = await res.fetchall()
        engine.close()
        if len(result) > 0:
            result = result[0]
            allowed_groups = await get_allowed_grps(source)
            sigmamail = ''
            alphamail = ''
            for mail in result.as_tuple()[4:6]:
                if '@sberbank.ru' in mail:
                    sigmamail = mail
                else:
                    alphamail = mail
            params = dict(mail=alphamail, mail_sigma=sigmamail, allowed_groups=allowed_groups)
            return json_response({'result': True, 'params': params})
    except BaseException as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
    return json_response({'result': False})


@ZabbixRoutes.post('/api/zabbix/create_uz')
@check_permissions([
    'zabbixuz'
], permissions_property='role', comparison=match_any)
async def create_uz(request):
    try:
        post_data = await request.json()
        token = request.headers.get('authorization', None).split()[1]
        jwtd = jwt.decode(token, JWT_SECRET,
                          algorithms=[JWT_ALGORITHM], options={'verify_exp': False})
        user = post_data['user']
        user['login'] = jwtd['user_id']
        source = post_data['source']
        action = post_data['action']
        zapi = await async_zabbix_conn(source)
        if await add_user(zapi, user, source, action, request.app['uz_logger']):
            await zapi.close()
            return json_response({'result': True})
        await zapi.close()
    except BaseException as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
    return json_response({'result': False})


@ZabbixRoutes.post('/api/zabbix/get_proxy')
async def get_proxy(request):
    try:
        post_data = await request.json()
        linux_proxy = await get_proxy_ip('http://10.68.195.110/pub/zabbix_agent/Linux/zabbix_agentd.conf')
        win_proxy = await get_proxy_ip('http://10.68.195.110/pub/customer/zabbix_agent/windows/zabbix_agentd.win.conf')
        aix_proxy = await get_proxy_ip('http://10.68.195.110/pub/zabbix_agent/AIX/zabbix_agentd.conf')
        solaris_proxy = await get_proxy_ip('http://10.68.195.110/pub/zabbix_agent/Solaris/zabbix_agentd_SOL11ZONE.conf')
        proxies = {'linux': linux_proxy, 'win': win_proxy, 'aix': aix_proxy, 'solaris': solaris_proxy}
        return json_response({'result': True, 'proxies': proxies})
    except BaseException as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
    return json_response({'result': False})


async def run_task_with_executor(loop, func, *args):
    func_for_execute = partial(func, *args)
    return loop.run_in_executor(None, func_for_execute)


@ZabbixRoutes.post('/api/zabbix/check_stand')
@check_permissions([
    'standcheck'
], permissions_property='role', comparison=match_any)
async def check_stand(request):
    try:
        post_data = await request.json()
        # source = post_data['source']
        ZabbixConfig = await get_zabbix_conf()
        engine = await db_connect('configs')
        async with engine.acquire() as conn:
            res = await conn.execute(f"select * from configs.databases where name='ORACLESM'")
            db_config = await res.fetchall()
        engine.close()
        db_config = db_config[0].as_tuple()
        func_for_execute = partial(getsearch, post_data['query'], ZabbixConfig, post_data['source'], db_config)
        search_result = await asyncio.get_event_loop().run_in_executor(None, func_for_execute)
        return json_response({'result': True, 'rows': search_result})
    except BaseException as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
    return json_response({'result': False})


@ZabbixRoutes.post('/api/zabbix/get_select')
async def get_select(request):
    try:
        params = await get_showed_zabbix()
        dict_params = {}
        for arr in params:
            dict_params[arr[0]] = {'url': arr[1], 'name': arr[2], 'search_url': arr[3], 'zabbixType': arr[4]}
        return json_response({'result': True, 'params': dict_params})
    except BaseException as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
    return json_response({'result': False})
