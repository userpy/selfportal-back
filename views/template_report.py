from aiohttp import web
from scripts.help_functions import json_response, db_connect
from aiohttp_jwt import  check_permissions, match_any
from scripts.help_functions_zbx import async_zabbix_conn, zabbix_conn
import datetime

TemplateReport_Routes = web.RouteTableDef()

@TemplateReport_Routes.post('/api/template_report/get_templateslist')
@check_permissions([
    'templatereport'
], permissions_property = 'role', comparison=match_any)
async def get_templateslist(request):
    post_data = await request.json()
    try:
        zapi = await async_zabbix_conn(post_data['source'])
        search_query = {}
        if post_data['hostname']:
            search_query = {'host': post_data['hostname']}
        res = await zapi.template.get(output=['name'], search=search_query)
        hostlist = [host['name'] for host in res]
        await zapi.close()
        return json_response({'result': True, 'templatenamelist': hostlist})
    except BaseException as e:
        request.app['app_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False, 'text':str(e)})


@TemplateReport_Routes.post('/api/template_report/get_template')
@check_permissions([
    'templatereport'
], permissions_property = 'role', comparison=match_any)
async def get_template(request):
    try:
        post_data = await request.json()
        tr_priority = {
            '0': 'Не классифицировано',
            '1': 'Информация',
            '2': 'Предупреждение',
            '3': 'Средняя',
            '4': 'Высокая',
            '5': 'Чрезвычайная',
        }
        tr_status = {
            '0': 'Активирован',
            '1': 'Деактивирован',
        }
        value_type_map = {
            '0': 'Числовое с плавающей точкой',
            '1': 'Символ',
            '2': 'Журнал(лог)',
            '3': 'Числовое целое положительное',
            '4': 'Текст'
        }
        zapi = await async_zabbix_conn(post_data['source'])

        hostdeps = {
            'template_name': '',
            'items': [],
            'triggers': [],
            'discoveries': {}
        }

        templateid_res = await zapi.template.get(output=['templateid'],
                                       filter={'name': post_data['templatename']})
        templateid = templateid_res[0]['templateid']

        template_res = await zapi.template.get(templateids=templateid,
                                     output=['name'],
                                     selectItems=['name', 'key_', 'description', 'delay', 'history', 'trends','status','value_type','units','valuemapid'],
                                     selectDiscoveries=['itemid'],
                                     selectTriggers=['triggerid'])
        template_valuemap = await zapi.valuemap.get(output=['valuemapid','name'])
        template_valuemap = {value['valuemapid']:value['name'] for value in template_valuemap}
        template = template_res[0]
        hostdeps['template_name'] = template['name']

        lld_ids = [discovery['itemid'] for discovery in template['discoveries']]
        triggers_ids = [t['triggerid'] for t in template['triggers']]

        triggers = await zapi.trigger.get(output=['expression', 'description', 'comments', 'status', 'priority'],
                                    triggerids=triggers_ids,
                                    selectTags="extend",
                                    expandExpression=1,
                                    expandComment=1,
                                    expandDescription=1)

        discoveries = await zapi.discoveryrule.get(output=['name','status'],
                                             itemids=lld_ids,
                                             selectItems=['name', 'key_', 'description', 'delay', 'history','status', 'trends','value_type','units','valuemapid'],
                                             selectTriggers=['expression', 'description', 'comments', 'status', 'priority'])
        item_index = 0
        for item in template['items']:
            item_index = item_index + 1

            hostdeps['items'].append({"number": str(item_index),
                                      "name": item["name"],
                                      "description": item["description"],
                                      "key_": item["key_"],
                                      "delay": item["delay"],
                                      "history": item["history"],
                                      "trends": item["trends"],
                                      "status": tr_status[item["status"]],
                                      "value_type": value_type_map[item['value_type']],
                                      "units": item['units'],
                                      "valuemap": template_valuemap[item['valuemapid']] if item['valuemapid'] != '0' else ''})
        tr_index = 0
        for t in triggers:
            tr_index = tr_index + 1
            hostdeps['triggers'].append({"number": str(tr_index),
                                         "expression": t['expression'],
                                         "description": t['description'],
                                         "comments": t['comments'],
                                         "priority": tr_priority[t['priority']],
                                         "tags" : [f"{tag['tag']}:{tag['value']}" for tag in t['tags']],
                                         "status": tr_status[t['status']]})
        for d in discoveries:
            p_items = []
            p_triggers = []
            p_index = 0
            for i in d['items']:
                p_index = p_index + 1
                i['number'] = str(p_index)
                p_items.append(i)
                i['status'] = tr_status[i['status']]
                i['value_type'] = value_type_map[i['value_type']]
                i['valuemap'] = template_valuemap[i['valuemapid']] if i['valuemapid'] != '0' else ''
            p_index = 0
            for t in d['triggers']:
                p_index = p_index + 1
                t['number'] = str(p_index)
                t['status'] = tr_status[t['status']]
                t['priority'] = tr_priority[t['priority']]
                p_triggers.append(t)
                d_trigger = await zapi.triggerprototype.get(
                    output=['triggerid','expression'],
                    triggerids=t['triggerid'],
                    selectTags="extend", expandExpression=1)
                #print(d_trigger)
                if d_trigger:
                    t['tags'] =[f"{tag['tag']}:{tag['value']}" for tag in d_trigger[0]['tags']]
                    t['expression'] = d_trigger[0]['expression']
            hostdeps['discoveries'][d['itemid']] = {'name': d['name'], 'items': p_items, 'triggers': p_triggers,
                                                    'status':d['status']}
        await zapi.close()
        #print(hostdeps)
        return json_response({'result': True, 'template': hostdeps})
    except BaseException as e:
        raise
        request.app['app_logger'].error(f'Error in app: {str(e)}')
        return json_response({'result': False, 'text':str(e)})

