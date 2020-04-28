from scripts.help_functions_zbx import async_zabbix_conn
from aiohttp import web
from scripts.help_functions import json_response, JWT_ALGORITHM, JWT_SECRET
from scripts.schema_chanels import get_scheme_to_send, update_chanel,  groups_updater, update_cnl_num
from aiohttp_jwt import  check_permissions, match_any
from scripts.read_line_in_xlsx import xls_to_json_dict_parser
import jwt

async def get_jwt_info(request, key):
    token = request.headers.get('authorization', None).split()[1]
    jwtd = jwt.decode(token, JWT_SECRET,
                      algorithms=[JWT_ALGORITHM], options={'verify_exp': False})
    return jwtd[key]

async def usermacrosearch(macro, search, search_key, api):
    hostid = await api.usermacro.get(filter=dict(macro=macro),
                                     search=dict(value=search.get(search_key, None)[0]),
                                     output=['hostid']
                                     )
    hosts = await api.host.get(hostids=list(map(lambda X: X['hostid'], hostid)),
                                                   selectParentTemplates=['name'],
                                                   selectMacros='extend',
                                                   selectInterfaces='extend')
    return hosts




zabbixWanRoutes = web.RouteTableDef()
@check_permissions([
    'channel_manager'
], permissions_property = 'role', comparison=match_any)
@zabbixWanRoutes.post('/api/zabbixwan/gethosts')
async def zabbixWanGetHosts(request):
    try:
        post_data = await request.json()
        zabbix = post_data['zabbix']
        search = post_data['search']
        api = await async_zabbix_conn(zabbix, 'net')
        if search.get('host', None):
            search_name = {'name': [search['host'][0]], 'host': [search['host'][0]]}
            hosts = await api.host.get(search=search_name, selectParentTemplates=['name'], selectMacros='extend',
                                       selectInterfaces='extend', searchByAny=True)

        elif search.get('MangmentIpAddres', None):
            search = {'ip': [f"{search.get('MangmentIpAddres')[0]}"]}
            hostid = await api.hostinterface.get(search=search,
                                                 output=['hostid', 'type'])

            hosts = await api.host.get(hostids=list(map(lambda X: X['hostid'], hostid)), selectParentTemplates=['name'],
                                       selectMacros='extend',
                                       selectInterfaces='extend')
        elif search.get('SNMPcommunity', None):
            hosts = await usermacrosearch(macro='{$SNMP_COMMUNITY}', api=api, search=search, search_key='SNMPcommunity')

        elif search.get('Interfaces:ALL', None):
            hosts = await usermacrosearch(macro='{$CNL_IFS}', api=api, search=search, search_key='Interfaces:ALL')

        elif search.get('Interfaces:ISIS', None):
            hosts = await usermacrosearch(macro='{$ISIS_INTERFACES}', api=api, search=search,
                                          search_key='Interfaces:ISIS')

        elif search.get('BGPpeers', None):
            hosts = await usermacrosearch(macro='{$BGP_PEERS}', api=api, search=search, search_key='BGPpeers')

        elif search.get('OSPFpeers', None):
            hosts = await usermacrosearch(macro='{$OSPF_PEERS}', api=api, search=search, search_key='OSPFpeers')

        elif search.get('EIBGPpeers', None):
            hosts = await usermacrosearch(macro='{$EIGRP_PEERS}', api=api, search=search, search_key='EIBGPpeers')

        elif search.get('SLAtests', None):
            hosts = await usermacrosearch(macro='{$SLA_TESTS}', api=api, search=search, search_key='SLAtests')
        hosts = await groups_updater(hosts, api=api)
        await api.close()
        return json_response({'hosts': hosts})
    except:
        return json_response({'hosts': hosts})


@check_permissions([
    'channel_manager'
], permissions_property = 'role', comparison=match_any)
@zabbixWanRoutes.post('/api/zabbixwan/create_channel')
async def zabbixWanCreateChannels(request):
    user_id = await get_jwt_info(request, 'user_id')
    request['user_id'] = user_id
    post_data = await request.json()
    zabbix = post_data['zabbix']
    chanel = post_data['chanel']
    try:
        api = await async_zabbix_conn(zabbix, 'net')
        host, group = await get_scheme_to_send(i=chanel, zapi=api, zabbix=zabbix, proxy_balanser=1, request=request)
        hostid = await api.host.create(host)
        await update_chanel(api=api, SM_HOSTID=hostid['hostids'][0])
        await api.close()
        await update_cnl_num(db='configs', group=group, zabbix=zabbix)
        chanel.pop('_showDetails', None)
        request.app['zabbix_wan_logger'].info(f'USER ({user_id})|Info in app: create channel {chanel}')
        return json_response({'result': True, 'text': f"Данные отправлены успешно"})
    except Exception as err:
        await api.close()
        if str(err) == 'list index out of range':
            err = 'Обязательные поля не заполненны'
        request.app['app_logger'].error(f'Error in app: {str(err)}')
        request.app['zabbix_wan_logger'].error(f'USER ({user_id})|Error in app: {str(err)}')
        return json_response({'result': False, 'text': f"{err}"})




@check_permissions([
    'channel_manager'
], permissions_property = 'role', comparison=match_any)
@zabbixWanRoutes.post('/api/zabbixwan/del_channel')
async def zabbixWanDelChannel(request):
    post_data = await request.json()
    user_id = await get_jwt_info(request, 'user_id')
    zabbix = post_data['zabbix']
    channel_id = str(post_data['channel_id'])
    api = await async_zabbix_conn(zabbix, 'net')
    try:
        channel_info=await api.host.get(hostids=[channel_id], output=['name', 'host'])
        await api.host.delete(channel_id)
        await api.close()
        request.app['zabbix_wan_logger'].info(f'USER ({user_id})| Info in app: del channel {channel_info}')
        return json_response({'result': True, 'text': f"Канал удалён {channel_id}"})
    except Exception as err:
        await api.close()
        request.app['zabbix_wan_logger'].error(f'USER ({user_id})|Error in app: {str(err)}')
        return json_response({'result': False, 'text': f"Канал не существует {channel_id} {err}"})



@check_permissions([
    'channel_manager'
], permissions_property = 'role', comparison=match_any)
@zabbixWanRoutes.post('/api/zabbixwan/update_channel')
async def zabbixWanUpdateChannel(request):
    post_data = await request.json()
    user_id = await get_jwt_info(request, 'user_id')
    request['user_id'] = user_id
    zabbix = post_data['zabbix']
    chanel = post_data['chanel']
    host_id = chanel['hostid']
    host_name = chanel['host']
    api = await async_zabbix_conn(zabbix, 'net')
    try:
        host, group = await get_scheme_to_send(i=chanel, zapi=api, zabbix=zabbix, proxy_balanser=1,request=request)
        host['host'] = host_name
        host["hostid"] = host_id
        hostinterface =  await api.host.get(hostids=[host_id], selectInterfaces=["interfaceid"], output=['interfaces'] )
        host['interfaces'][0]['interfaceid'] = hostinterface[0]['interfaces'][0]['interfaceid']
        await api.host.update(host)
        macros = await api.usermacro.get(hostids=[host_id])
        macros.extend([{'macro': '{$SM_HOSTID}', 'value': host_id},
                       {'macro': '{$SCREEN_LINK}',
                        'value': f'https://zabbix-cssm.sigma.sbrf.ru/zabbix_wan/'
                                 f'zabbix.php?action=problem.view&page=1&filter_'
                                 f'show=1&filter_hostids[]={host_id}&filter_se'
                                 f'verity=2&filter_set=1'}])

        await api.host.update({'hostid': host_id, 'macros': macros})
        await api.close()
        host_info = host
        request.app['zabbix_wan_logger'].info(f'USER ({user_id})|Info in app: update channel {chanel}')
        return json_response({'result': True, 'text': f"Данные ({host_name}) успешно обновлены"})
    except Exception as err:
        await api.close()
        request.app['zabbix_wan_logger'].error(f'USER ({user_id})|Error in app: {str(err)}')
        return json_response({'result': False, 'text': f"{err}"})




@check_permissions([
    'channel_manager'
], permissions_property = 'role', comparison=match_any)
@zabbixWanRoutes.post('/api/zabbixwan/get_channels')
async def zabbixWanGetChannels(request):
    try:
        post_data = await request.json()
        zabbix = post_data['zabbix']
        hostgroup = post_data['hostgroup']
        api = await async_zabbix_conn(zabbix, 'net')
        hostgroup = await api.hostgroup.get(output=['name'], search={'name':[hostgroup+'/']})
        hostgroup = list(filter(lambda x:  len(x['name'].split('/')) > 2, hostgroup))
        hostgroup = list(map(lambda x: dict(value=x['name'],text=x['name']), hostgroup))
    except:
        hostgroup = []
    await api.close()
    return json_response(hostgroup)

@check_permissions([
    'channel_manager'
], permissions_property = 'role', comparison=match_any)
@zabbixWanRoutes.post('/api/zabbixwan/get_channels_master')
async def zabbixWanGetChannelsMaster(request):
    try:
        post_data = await request.json()
        zabbix = post_data['zabbix']
        hostgroup_search = ['Core Wan', 'External node', 'Internet node', 'VDI Node']
        api = await async_zabbix_conn(zabbix, 'net')
        hostgroup = []
        for hg in hostgroup_search:
            Fhostgroup = await api.hostgroup.get(output=['name'], search={'name': [hg]})
            hostgroup.extend(Fhostgroup)
        hostgroup = list(filter(lambda x:  len(x['name'].split('/')) == 2, hostgroup))
        hostgroup = list(map(lambda x: dict(value=x['name'],text=x['name']), hostgroup))
    except:
        hostgroup = []
    await api.close()
    return json_response(hostgroup)

@check_permissions([
    'channel_manager'
], permissions_property = 'role', comparison=match_any)
@zabbixWanRoutes.post('/api/zabbixwan/upload_channels')
async def zabbixWanUploadChannels(request):
    try:
        user_id = await get_jwt_info(request, 'user_id')
        data = await request.post()
        filename=str(data['file'].filename).split('.')[-1]
        if filename not in ['xlsx']:
            raise TypeError('Not xlsx')
        sheet_name=data['listname']
        if sheet_name.replace(' ','') == '':
            raise TypeError('Not list name')
        file_xlsx = data['file'].file
        json_str= await xls_to_json_dict_parser(file_xlsx=file_xlsx, sheet_name=sheet_name)
        request.app['zabbix_wan_logger'].info(f'USER ({user_id})|Info in app: Chanel upload xlsx to json')
        return json_response({'result': True, 'text': f"Добавлено ","xlsx":json_str})
    except Exception as err:
        request.app['zabbix_wan_logger'].error(f'USER ({user_id})|Error in app: {str(err)}')
        return json_response({'result': False, 'text': f"{err}"})
