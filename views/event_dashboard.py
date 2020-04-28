from aiohttp import web, ClientSession, TCPConnector
from aiohttp_jwt import check_permissions, match_any
import re
import json
import sqlalchemy as sa
import datetime
from scripts.help_functions_zbx import async_zabbix_conn, zabbix_conn, get_showed_zabbix, get_zabbix_conf
from views.ws import sio
from scripts.help_functions import json_response, db_connect, JWT_ALGORITHM, JWT_SECRET
import jwt
import pymysql
import asyncio

EventDashboardRoutes = web.RouteTableDef()

metadata = sa.MetaData()
tbl_eventdashboard_filters = sa.Table('eventdashboard_filters', metadata,
                sa.Column('author', sa.String(100), primary_key=True),
                sa.Column('name', sa.String(128), primary_key=True),
                sa.Column('query', sa.String(500), unique=True),
                sa.Column('time', sa.String(128), unique=True),
                sa.Column('row_count', sa.String(30), unique=True),
                sa.Column('severities', sa.String(500), unique=True),
                sa.Column('selected_cols', sa.String(500), unique=True),
                sa.Column('colors', sa.String(1000), unique=True),
                sa.Column('width', sa.String(500), unique=True)
                )

def eventsortkey(val):
    return val['clock']

@EventDashboardRoutes.post('/api/eventdashboard/update_event')
@check_permissions([
    'eventdashboard'
], permissions_property = 'role', comparison=match_any)
async def update_event(request):
    try:
        post_data = await request.json()
        token = request.headers.get('authorization',None).split()[1]
        jwtd = jwt.decode(token, JWT_SECRET,
                          algorithms=[JWT_ALGORITHM], options={'verify_exp': False})
        ids = post_data['ids']
        action = post_data['action']
        message = post_data['message']
        ids_by_source = {}
        result = {}
        errors = []
        for id in ids:
            if id['source'] not in ids_by_source:
                ids_by_source[id['source']] = {}
                ids_by_source[id['source']] = set()
            ids_by_source[id['source']].add(id['id'])
        for source in ids_by_source:
            zapi = await async_zabbix_conn(source)
            try:
                await zapi.event.acknowledge(action=action,eventids=list(ids_by_source[source]),message=jwtd['user_id']+': '+message)
            except BaseException as e:
                errors.append(str(e))
            await zapi.close()
        return json_response({'result': True, 'errors': errors})
    except BaseException as e:
        request.app['eventdashboard_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False, 'text':str(e)})

@EventDashboardRoutes.post('/api/eventdashboard/get_history')
@check_permissions([
    'eventdashboard'
], permissions_property = 'role', comparison=match_any)
async def get_history(request):
    try:
        post_data = await request.json()
        time = post_data['time']
        hosts = post_data['hosts']
        hosts_by_source = {}
        result = {}
        for host in hosts:
            if host['source'] not in hosts_by_source:
                result[host['source']] = {}
                hosts_by_source[host['source']] = set()
            hosts_by_source[host['source']].add( host['host'])
        for source in hosts_by_source:
            zapi = await async_zabbix_conn(source)
            zabbix_hosts = await zapi.host.get(output=['hostid','host'],filter={'host':list(hosts_by_source[source])})
            hostids = {host['hostid']:host['host'] for host in zabbix_hosts}
            host_history = await zapi.event.get(value='1',hostids = list(hostids.keys()), selectHosts=['extend'],time_from=int((datetime.datetime.now() - datetime.timedelta(seconds=int(time))).timestamp()))
            await zapi.close()
            for event in host_history:
                if hostids[event['hosts'][0]['hostid']] not in result[source]:
                    result[source][hostids[event['hosts'][0]['hostid']]] = []
                result[source][hostids[event['hosts'][0]['hostid']]].append(event)
        return json_response({'result': True, 'events': result})
    except BaseException as e:
        request.app['eventdashboard_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False, 'text':str(e)})

@EventDashboardRoutes.post('/api/eventdashboard/save_filter')
@check_permissions([
    'eventdashboard_filters'
], permissions_property = 'role', comparison=match_any)
async def save_filter(request):
    try:
        token = request.headers.get('authorization',None).split()[1]
        jwtd = jwt.decode(token, JWT_SECRET,
                          algorithms=[JWT_ALGORITHM], options={'verify_exp': False})
        post_data = await request.json()
        filters = post_data['filters']
        engine = await db_connect('configs')
        async with engine.acquire() as conn:
            try:
                await conn.execute(tbl_eventdashboard_filters.insert().values(author=jwtd['user_id'],
                                                                                    name=filters['name'],
                                                                                    query=filters['query'],
                                                                                    time=filters['time'],
                                                                                    row_count=filters['row_count'],
                                                                                    severities=json.dumps(filters['severities'],ensure_ascii=False),
                                                                                    selected_cols=json.dumps(filters['selected_cols'],ensure_ascii=False),
                                                                                    colors=json.dumps(filters['colors'],ensure_ascii=False),
                                                                                    width=json.dumps(filters['width'],ensure_ascii=False)))
                await conn.execute("commit")
            except pymysql.err.IntegrityError:
                await conn.execute(tbl_eventdashboard_filters.update().values(query=filters['query'],
                                                                              time=filters['time'],
                                                                              row_count=filters['row_count'],
                                                                              severities=json.dumps(
                                                                                  filters['severities'],
                                                                                  ensure_ascii=False),
                                                                              selected_cols=json.dumps(
                                                                                  filters['selected_cols'],
                                                                                  ensure_ascii=False),
                                                                              colors=json.dumps(
                                                                                  filters['colors'],
                                                                                  ensure_ascii=False),
                                                                              width=json.dumps(
                                                                                  filters['width'],
                                                                                  ensure_ascii=False)).where(sa.and_(tbl_eventdashboard_filters.c.name == filters['name'],tbl_eventdashboard_filters.c.author == jwtd['user_id'])))
                await conn.execute("commit")


        engine.close()
        return json_response({'result': True})
    except BaseException as e:
        request.app['eventdashboard_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False, 'text':str(e)})

@EventDashboardRoutes.post('/api/eventdashboard/get_filter')
@check_permissions([
    'eventdashboard'
], permissions_property = 'role', comparison=match_any)
async def get_filter(request):
    try:
        engine = await db_connect('configs')
        async with engine.acquire() as conn:
            res = await conn.execute(tbl_eventdashboard_filters.select())
            result = await res.fetchall()
        engine.close()
        filters_dict = {}
        for item in result:
            filters_dict[item['author']+':'+item['name']] = {
                'name':item['name'],
                'query':item['query'],
                'time': item['time'],
                'row_count': item['row_count'],
                'severities': json.loads(item['severities']),
                'selected_cols': json.loads(item['selected_cols']),
                'colors': json.loads(item['colors']),
                'width': json.loads(item['width'])
            }
        return json_response({'result': True, 'filters':filters_dict})
    except BaseException as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
    return json_response({'result': False})

@EventDashboardRoutes.post('/api/eventdashboard/delete_filter')
@check_permissions([
    'eventdashboard_filters'
], permissions_property = 'role', comparison=match_any)
async def delete_filter(request):
    try:
        post_data = await request.json()
        author,name = post_data['key'].split(':')
        engine = await db_connect('configs')
        async with engine.acquire() as conn:
            await conn.execute(tbl_eventdashboard_filters.delete().where(sa.and_(tbl_eventdashboard_filters.c.name == name,tbl_eventdashboard_filters.c.author == author)))
            await conn.execute("commit")
        engine.close()

        return json_response({'result': True})
    except BaseException as e:
        request.app['eventdashboard_logger'].error(f'Error in app: {str(e)}')
    return json_response({'result': False})


@EventDashboardRoutes.post('/api/eventdashboard/get_problems')
@check_permissions([
    'eventdashboard'
], permissions_property = 'role', comparison=match_any)
async def get_problems(request):
    try:
        post_data = await request.json()
        filter_seconds = int(post_data['filters']['time'])
        filter_query = post_data['filters']['query']
        filter_severities= post_data['filters']['severities']
        #print(filter_query,filter_severities)
        #regexp_query = await create_regexp_query(filter_query)
        #print(datetime.datetime.now(),filter_seconds)
        rows = []
        errors = [] #'Test errors', 'Test error2'
        zbx_list = await get_showed_zabbix()
        zbx_list = [zbx[0] for zbx in zbx_list]
        for source in zbx_list:
            try:
                if 'source' in filter_query and not (re.match(filter_query['source'],source)):
                    continue
                zapi = await async_zabbix_conn(source)

                get_params = {}
                hostgroup_ids = []
                host_ids = []
                application_ids = []
                trigger_ids = []
                filter_get_params = {}
                if filter_severities:
                    get_params['severities'] = filter_severities
                if 'groups' in filter_query:
                    hostgroups = await zapi.hostgroup.get(real_hosts=True, output=['groupid','name'])
                    for hotgroup in hostgroups:
                        if re.match(filter_query['groups'],hotgroup['name']):
                            hostgroup_ids.append(hotgroup['groupid'])
                    get_params['groupids'] = hostgroup_ids
                if 'host' in filter_query:
                    if 'groupids' in get_params:
                        filter_get_params['groupids'] = get_params['groupids']
                    hosts = await zapi.host.get(output=['hostid','host'], **filter_get_params)
                    for host in hosts:
                        if re.match(filter_query['host'],host['host']):
                            host_ids.append(host['hostid'])
                    get_params['hostids'] = host_ids
                if 'application' in filter_query:
                    if 'hostids' in get_params:
                        filter_get_params['hostids'] = get_params['hostids']
                    applications = await zapi.application.get(output=['applicationid','hostid','name'], **filter_get_params)
                    for application in applications:
                        if re.match(filter_query['application'],application['name']):
                            application_ids.append(application['applicationid'])
                    get_params['applicationids'] = application_ids
                # if 'name' in filter_query and len(filter_get_params) != 0:
                #     if 'applicationids' in get_params:
                #         filter_get_params['applicationids'] = get_params['applicationids']
                #     items = await zapi.item.get(output=['itemid','name'], **filter_get_params)
                #     item_ids = [item['itemid'] for item in items]
                #     filter_get_params['itemids'] = item_ids
                #     triggers = await zapi.trigger.get(output=['triggerid', 'description'], **filter_get_params)
                #     for trigger in triggers:
                #         if re.match(filter_query['name'],trigger['description']):
                #             trigger_ids.append(trigger['triggerid'])
                #     get_params['objectids'] = trigger_ids

                events = await zapi.problem.get(output='extend', **get_params, sortfield='eventid', sortorder = 'DESC',
                                                selectTags='extend', selectAcknowledges=['clock','action','message','userid'], time_from=int((datetime.datetime.now() - datetime.timedelta(seconds=filter_seconds)).timestamp()))
                triggerids = [event['objectid'] for event in events if event['object'] == '0']
                triggers = await zapi.trigger.get(output=['itemid','comments'], triggerids=triggerids, selectHosts=['host','hostid'])
                hostids = [trigger['hosts'][0]['hostid'] for trigger in triggers]
                inventorys = await zapi.host.get(output=['hostid','host'], hostids=hostids, selectInventory=['tag','url_b'],selectGroups=['name'], selectApplications=['name'])
                groups = {}
                applications = {}
                for inventory in inventorys:
                    #print([group['name'] for group in inventory['groups']])
                    groups[inventory['host']] = ','.join([group['name'] for group in inventory['groups']])
                    applications[inventory['host']] = ','.join([group['name'] for group in inventory['applications']])
                inventorys = {inventory['host']: {'tag':inventory['inventory']['tag'],'url_b':inventory['inventory']['url_b']} for inventory in inventorys if
                              type(inventory['inventory']) == dict}
                hosts = {item['triggerid']:item for item in triggers}
                success_events = []
                for event in events:
                    if 'severity' not in event:
                        continue
                    event['source'] = source
                    event['status'] = 'PROBLEM'
                    if event['objectid'] in hosts and 'comments' in hosts[event['objectid']]:
                        event['comments'] = hosts[event['objectid']]['comments']
                    else:
                        event['comments'] = ''
                    if event['objectid'] in hosts and hosts[event['objectid']]['hosts'][0]['host'] in applications:
                        event['application'] = applications[hosts[event['objectid']]['hosts'][0]['host']]
                    else:
                        event['application'] = ''
                    if event['objectid'] in hosts and hosts[event['objectid']]['hosts'][0]['host'] in groups:
                        event['groups'] = groups[hosts[event['objectid']]['hosts'][0]['host']]
                    else:
                        event['groups'] = ''
                    if event['objectid'] in hosts and hosts[event['objectid']]['hosts'][0]['host'] in inventorys:
                        event['inventory'] = inventorys[hosts[event['objectid']]['hosts'][0]['host']]['tag']
                    else:
                        event['inventory'] = ''
                    if event['objectid'] in hosts and hosts[event['objectid']]['hosts'][0]['host'] in inventorys:
                        event['criticalLevel'] = inventorys[hosts[event['objectid']]['hosts'][0]['host']]['url_b']
                    else:
                        event['criticalLevel'] = ''
                    event['tags'] = ','.join([f"{tag['tag']}:{tag['value']}" for tag in event['tags']])
                    if event['objectid'] in hosts:
                        event['host'] = hosts[event['objectid']]['hosts'][0]['host']
                    else:
                        event['host'] = 'UNKNOWN'
                    event['clock'] = datetime.datetime.fromtimestamp(int(event['clock'])).strftime('%d-%m-%Y %H:%M:%S')
                    for regkey in filter_query:
                        if not re.match(filter_query[regkey],event[regkey]):
                            break
                    else:
                        success_events.append(event)
                rows.extend(success_events)
                await zapi.close()
            except BaseException as e:
                errors.append(str(e))
                request.app['app_logger'].error(f'Error in app: {str(e)}')
        #print(datetime.datetime.now(),len(events))
        rows.sort(key=eventsortkey,reverse=True)
        return json_response({'result': True, 'rows' : rows, 'errors': errors})
    except BaseException as e:
        request.app['eventdashboard_logger'].error(f'Error in app: {str(e)}')
    return json_response({'result': False})

@EventDashboardRoutes.post('/api/eventdashboard/new_problem')
async def new_problem(request):
    try:
        post_data = await request.json()
        asyncio.get_event_loop().create_task(new_problem_generate(request))
        return json_response({'result': True})
    except BaseException as e:
        request.app['eventdashboard_logger'].error(f'Error {str(type(e))}in app: {str(e)}, header: {post_data["id"]}, msg:{post_data["msg"]}')
    return json_response({'result': False})

async def new_problem_generate(request):
    try:
        post_data = await request.json()
        #print(post_data)
        msg = post_data['msg']
        source = post_data['id'].split(':')[0]
        event = {'clock':'','eventid':'','host':'','name':'',
                 'severity':'','itemid':'','inventory':'','groups':'',
                 'tags':'','acknowledged':'','criticalLevel':'','updateaction':'','updatemessage':''}
        for key in event:
            if key == 'clock':
                date = re.findall('\\[date\\]:(.*)',msg)[0].strip()
                time = re.findall('\\[time\\]:(.*)', msg)[0].strip()
                event[key] = datetime.datetime.strptime(' '.join([date,time]),'%Y.%m.%d %H:%M:%S').strftime('%d-%m-%Y %H:%M:%S')
            else:
                event[key] = re.findall(f'\\[{key}\\]:(.*)',msg)[0].strip()
        try:
            zapi = await async_zabbix_conn(source) #await async_zabbix_conn(source)
            applications = await zapi.item.get(itemids=[event['itemid']], selectApplications=['name'])
        except BaseException as e:
            request.app['eventdashboard_logger'].error(
                f'Error {str(type(e))}in application get: {str(e)}, header: {post_data["id"]} event: {event}')
            applications = ''
        else:
            await zapi.close()

        if applications:
            applications = [application['name'] for application in applications[0]['applications']]
        else:
            applications = ['not loaded']
        event['application'] = ','.join(applications)
        event['source'] = source
        event['acknowledged'] = '1' if event['acknowledged'] == 'Yes' else '0'
        if post_data['id'].split(':')[1] == 'OK':
            await sio.emit('new_event_ok', data=event, room='eventdashboard')
        elif post_data['id'].split(':')[1] == 'Problem':
            await sio.emit('new_event_problem', data=event, room='eventdashboard')
        elif post_data['id'].split(':')[1] == 'Update':
            if event['updateaction'][:16] == 'changed severity':
                await sio.emit('new_event_severitychange', data=event, room='eventdashboard')
            elif event['updateaction'] == 'closed':
                await sio.emit('new_event_ok', data=event, room='eventdashboard')
            elif event['updateaction'] == 'commented':
                await sio.emit('new_event_commented', data=event, room='eventdashboard')
            else:
                await sio.emit('new_event_ack', data=event, room='eventdashboard')
        request.app('eventdashboard_logger').info(f"New event with title: {post_data['id']} Data: {event}")
    except BaseException as e:
        request.app['eventdashboard_logger'].error(f'Error {str(type(e))}in app: {str(e)}, header: {post_data["id"]} event: {event}')