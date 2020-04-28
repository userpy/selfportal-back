import os
from scripts.help_functions import db_connect
from scripts.help_functions_zbx import async_zabbix_conn
import cx_Oracle
import re
import logging

async def find_ci_in_sm(ci):
    try:
        engine = await db_connect('configs')
        async with engine.acquire() as conn:
            res = await conn.execute(
                f"select * from configs.databases where name='ORACLESM'")
            result = await res.fetchall()
        engine.close()
        hpsm_config = result[0]
        os.environ['NLS_LANG'] = 'American_America.AL32UTF8'
        con = cx_Oracle.connect('{}/{}@{}:{}/{}'.format(hpsm_config[4],
                                                        hpsm_config[5],
                                                        hpsm_config[1],
                                                        hpsm_config[2],
                                                        hpsm_config[3]))  # @UndefinedVariable
        cur = con.cursor()
        os.environ['NLS_LANG'] = 'American_America.AL32UTF8'
        ci_query = u"""
            with t as
                (
                select distinct
                  p.logical_name as p_logical_name,
                  p.type as p_type,
                  nvl(p.subtype,'N\A') as p_subtype,
                  p.hpc_status as p_hpc_status,
                  (select listagg(i.ip_addresses,', ') within group (order by i.logical_name) 
                   from smprimary.DEVICE2A2 i where i.logical_name = p.logical_name) as p_ip_address
                 from
                  smprimary.cirelationsm1 r,
                  smprimary.device2m1 p
                 where p.logical_name=r.tps_related_cis
                  and p.type in ('server','infresource')
                 connect by NOCYCLE prior r.tps_related_cis=r.logical_name
                  start with r.tps_related_cis IN ('{}')
                )
                 select distinct
                  t.p_logical_name as ls_id,
                  t.p_ip_address as ls_ip_address
                 from t  where t.p_hpc_status != 'Удаленный'
                 and t.p_type ='server'
                 and t.p_subtype IN ('Виртуальный', 'LDOM', 'LPAR', 'Логический', 'nPAR')""".format(ci)

        cur.execute(ci_query)
        host_list = cur.fetchall()
        """ Ответ будет выглядеть так:
        [
            ('CI00755980', '10.116.118.220'), 
            ('CI00476468', '10.68.16.103'), 
            ('CI00755981', '10.116.118.221'), 
            ('CI00721261', '10.116.105.171'), 
        ]
        """
        cur.close()
        con.close()

        # hosts_ci = [h[0] for h in host_list]
    except Exception as err:
        logger = logging.getLogger('app')
        logger.error(f'Server_report - error connecting to SM: {err}')
        host_list = []

        """ Возвращаем список:
        ['CI01088076', 'CI01088079', 'CI01088084', 'CI01088107', 'CI00867077']
        """

    return host_list


async def get_host_result(filestring, source):
    logger = logging.getLogger('app')
    if not filestring:
        return None
    ip_regexp = "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}"
    num_regexp = "{[0-9]+}"
    ci_regexp = "CI[0-9]{8}"
    item_regexp = "\[.*\]"

    is_ip = 0
    is_ci = 0
    string_info = str(filestring).splitlines()[0].split(' ')[0]
    if re.match(ip_regexp, string_info) is not None:
        is_ip = 1
    elif re.match(ci_regexp, string_info) is not None:
        is_ci = 1

    # The hostname at which the Zabbix web interface is available
    z = await async_zabbix_conn(source)

    if is_ip:
        host_ids = await z.host.get(output=['name', 'status'], filter={'ip': string_info})
    elif is_ci:
        # Делаем запрос в реплику SM
        # Вернет список: [('CI00755980', '10.116.118.220'), ('CI00755981', '10.116.118.221')]
        hosts_ci = await find_ci_in_sm(string_info)

        ips = [h[1] for h in hosts_ci]

        interfaces = await z.hostinterface.get(output=['ip'],
                                         filter={'ip': ips},
                                         selectHosts=['name', 'status'])

        host_ids = [h['hosts'][0] for h in interfaces]
    else:
        host_ids = await z.host.get(output=['name', 'status'], search={'host': string_info}, limit=10)

    # Создаём список hostid
    ids = [h['hostid'] for h in host_ids if h['status'] == '0']

    host_all_info = await z.host.get(output=['name','status'],
                               hostids=ids,
                               selectMacros='extend',
                               selectTriggers=['priority', 'status', 'tags', 'templateid'],
                               selectInterfaces=['ip'],
                               selectParentTemplates=['name'],
                               selectTags='extend',
                               preservekeys=1)

    # Добавляем id метрик к шаблонам
    templateids = [t['templateid'] for h in host_all_info for t in host_all_info[h]['parentTemplates']]
    templates = await z.template.get(output=['name'],
                               templateids=templateids,
                               selectItems=['name', 'itemid'],
                               selectTriggers=['name', 'triggerid'],
                               selectDiscoveries=['itemid'])

    # Собираем все элементы данных
    item_dict = await z.item.get(output=['hostid', 'name', 'key_', 'type', 'description', 'value_type',
                                   'delay', 'history', 'trends', 'status', 'templateid'],
                           webitems=1,
                           selectDiscoveryRule=['templateid'],
                           hostids=ids)

    value_types = {
        '0': 'число с точкой',
        '1': 'символ',
        '2': 'лог',
        '3': 'целое число',
        '4': 'текст'
    }

    # Добавляем имя шаблона в items
    for item in item_dict:  # Для элементов данных
        item['template_name'] = ''
        item['value_type'] = value_types[item['value_type']]
        for t in templates:
            if item['templateid'] != '0':
                if 'web.test' not in item['key_']:
                    for i in t['items']:
                        if i['itemid'] == item['templateid']:
                            item['template_name'] = t['name']
                else:
                    item['template_name'] = 'WEB'
            else:
                if len(item['discoveryRule']) > 0:
                    for d in t['discoveries']:
                        if item['discoveryRule']['templateid'] == d['itemid']:
                            item['template_name'] = t['name']
                else:
                    item['template_name'] = 'Нет шаблона'

    # Собираем все триггеры еще раз
    host_triggers = await z.trigger.get(output=['expression', 'description', 'comments', 'templateid'],
                                  hostids=ids,
                                  expandExpression=1,
                                  expandComment=1,
                                  expandDescription=1,
                                  selectTags='extend',
                                  selectDiscoveryRule=['templateid'],
                                  preservekeys=1)
    await z.close()

    # Добавляем имя шаблона к триггеру
    for tr in host_triggers:
        host_triggers[tr]['template_name'] = ''
        for t in templates:
            if host_triggers[tr]['templateid'] == '0':
                if len(host_triggers[tr]['discoveryRule']) > 0:
                    for d in t['discoveries']:
                        if host_triggers[tr]['discoveryRule']['templateid'] == d['itemid']:
                            host_triggers[tr]['template_name'] = t['name']
                else:
                    host_triggers[tr]['template_name'] = 'Нет шаблона'
            else:
                for trig in t['triggers']:
                    if host_triggers[tr]['templateid'] == trig['triggerid']:
                        host_triggers[tr]['template_name'] = t['name']

    result = {}
    types = {
        '0': 'Zabbix агент',
        '1': 'SNMPv1 агент',
        '2': 'Zabbix траппер',
        '3': 'простая проверка',
        '4': 'SNMPv2 агент',
        '5': 'Zabbix внутренний',
        '6': 'SNMPv3 агент',
        '7': 'Zabbix агент (активный)',
        '8': 'Zabbix агрегированный',
        '9': 'веб элемент данных',
        '10': 'внешняя проверка',
        '11': 'монитор баз данных',
        '12': 'IPMI агент',
        '13': 'SSH агент',
        '14': 'TELNET агент',
        '15': 'вычисляемый',
        '16': 'JMX агент',
        '17': 'SNMP трап',
        '18': 'Зависимый элемент данных',
    }

    for h in host_all_info:
        # Меняем на развернутые выражения из второго запроса
        for t in host_all_info[h]['triggers']:
            t['template_name'] = host_triggers[t['triggerid']]['template_name']
            t['description'] = host_triggers[t['triggerid']]['description']
            t['expression'] = host_triggers[t['triggerid']]['expression']
            t['comments'] = host_triggers[t['triggerid']]['comments']
            t['tags'] = host_triggers[t['triggerid']]['tags']
        host_all_info[h]['items'] = []
        result[h] = host_all_info[h]
        # Добавляем метрики в список метрик хоста
        for i in item_dict:
            if h == i['hostid']:
                result[h]['items'].append(i)

    for res in result:
        for item in result[res]['items']:
            if '$' in item['name']:
                # Составляем список всех параметров в метрике
                keysblock = re.findall(item_regexp, item['key_'])[0].replace('[', '').replace(']', '').split(',')
                # Для каждого параметра $1 $2 и т.д.
                for i in range(len(keysblock)):
                    # заменяем в имени item значение на параметр в метрике
                    item['name'] = item['name'].replace('${0}'.format(i + 1), keysblock[i])
            # Рвскрываем {HOSTNAME}
            if '{HOST.IP}' in item['key_']:
                item['key_'] = item['key_'].replace('{HOST.IP}', result[res]['name'])
            if '{HOST.CONN}' in item['key_']:
                item['key_'] = item['key_'].replace('{HOST.CONN}', result[res]['name'])
            if '{HOST' in item['key_']:
                item['key_'] = item['key_'].replace('{HOST.NAME}', result[res]['name']) \
                    .replace('{HOST.HOST}', result[res]['name']) \
                    .replace('{HOSTNAME}', result[res]['name'])
            if '{HOST.HOST}' in item['name']:
                item['name'] = item['name'].replace('{HOST.HOST}', result[res]['name'])
            # Раскрываем тип метрики
            item['type'] = types[item['type']]
        # Раскрываем {#HOSTNAME} в триггерах
        for tr in result[res]['triggers']:
            if '{#HOSTNAME}' in tr['description']:
                tr['description'] = tr['description'].replace('{#HOSTNAME}', result[res]['name'])
        result[res]['items'] = sorted(result[res]['items'], key=lambda x: x['status'])
        try:
            result[res]['triggers'] = sorted(sorted(result[res]['triggers'],
                                                    key=lambda x: x['priority'],
                                                    reverse=True),
                                             key=lambda x: x['status'])
        except Exception as err:
            logger.error(f"Error at server report with host {filestring}: {err}")
        #result = result[res]
    return result