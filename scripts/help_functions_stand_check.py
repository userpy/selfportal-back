import json
import aiohttp
import re
import os
import cx_Oracle
from pyzabbix import ZabbixAPI
from scripts.help_functions_zbx import zabbix_conn, get_zabbix_conf

def delete_spaces(a):
    while a[0:1] == " ":
        a = a[1:]
    while a[len(a)-1:] == " ":
        a = a[0:-1]
    return a

def find_lists(zapi, littlelist, filteris, hostKE='None'):
    biglist = []
    ci_dict = {}
    if hostKE == 'true':
        for item in littlelist:
            ci_dict[item[1]] = item[0]

        littlelist = [h[1] for h in littlelist]

    if len(littlelist) > 0:
        for scanname in littlelist:
            # print(scanname, filteris, hostKE)
            hostIP = 'Not Found'
            if filteris == 'host':
                testip = zapi.host.get(output=['host', 'status', 'hostid', 'ipmi_available',
                                               'jmx_available', 'snmp_available', 'available', 'proxy_hostid'],
                                       search={filteris: scanname},
                                       selectInventory=['tag'],
                                       selectGroups=['name'],
                                       selectParentTemplates=['name'],
                                       selectInterfaces=['ip'])
            else:
                testip = zapi.host.get(output=['host', 'status', 'hostid', 'ipmi_available',
                                               'jmx_available', 'snmp_available', 'available', 'proxy_hostid'],
                                       filter={filteris: scanname.replace('\xa0', '')},
                                       selectInventory=['tag'],
                                       selectGroups=['name'],
                                       selectParentTemplates=['name'],
                                       selectInterfaces=['ip'])
            # pprint(testip)
            proxy_name = ''
            #print(testip)
            if testip:
                for host in testip:
                    # print(host)
                    # hostId = host[0]['hostid']
                    hostName = host['host']
                    hostStatus = host['status']
                    hostGroupsStr = ''
                    host_templates_string = ''
                    try:
                        proxy_name = zapi.host.get(output=['host'], hostids=host['proxy_hostid'], proxy_hosts=1)[0][
                            'host']
                        proxy_ip = zapi.host.get(output=['name'],
                                                 search={'name': proxy_name},
                                                 selectInterfaces=['ip'])[0]['interfaces'][0]['ip']
                        if proxy_ip:
                            proxy = proxy_name + ' ({})'.format(proxy_ip)
                        else:
                            proxy = proxy_name
                    except IndexError as err:
                        proxy = 'Без прокси'

                    if len(host['interfaces']) > 0:
                        hostInterfaces = host['interfaces'][0]
                        if hostInterfaces['ip']:
                            hostIP = hostInterfaces['ip']

                    if len(host['inventory']) > 0:
                        hostInventory = host['inventory']
                        if hostInventory['tag']:
                            hostKE = hostInventory['tag']

                    if len(host['groups']) > 0:
                        hostGroupsStr = ''
                        hostGroups = host['groups']
                        for groupname in hostGroups:
                            if groupname['name']:
                                hostGroupsStr += '{0}; '.format(groupname['name'])

                    if len(host['parentTemplates']) > 0:
                        host_templates_string = ''
                        host_templates = host['parentTemplates']
                        for t_name in host_templates:
                            if t_name['name']:
                                host_templates_string += '{0}; '.format(t_name['name'])

                    biglist.append({'id': hostKE,
                                    'name': hostName,
                                    'ip': hostIP,
                                    'status': hostStatus,
                                    'ismon': not bool(hostStatus),
                                    'groups': hostGroupsStr,
                                    'templates': host_templates_string,
                                    'ipmi_available': host['ipmi_available'],
                                    'jmx_available': host['jmx_available'],
                                    'snmp_available': host['snmp_available'],
                                    'available': host['available'],
                                    'proxy': proxy
                                    })
            else:
                biglist.append({'id': ci_dict[scanname] if ci_dict else 'NONE',
                                'name': scanname if filteris == 'host' else 'Not Found',
                                'ip': scanname if filteris == 'ip' else 'Not Found',
                                'ismon': '0',
                                'groups': 'None',
                                'templates': 'None',
                                'proxy': proxy_name})
    # pprint(biglist)
    return biglist



def returnquery(query_ci_list):
    all_ci_query = u"""
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
                      start with r.tps_related_cis IN {}
                    )
                     select distinct
                      t.p_logical_name as ls_id,
                      t.p_ip_address as ls_ip_address
                     from t  where t.p_hpc_status != 'Удаленный'
                     and t.p_type ='server'
                     and t.p_subtype IN ('Виртуальный', 'LDOM', 'LPAR', 'Логический', 'nPAR', 'Физический')""".format(query_ci_list)
    return all_ci_query

async def get_proxy_ip(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            config_lines = await resp.text()
            config_lines = config_lines.split("\n")
            for line in config_lines:
                if ('ServerActive=' in line) and (line.find("=") == 12):
                    return line.split("=")[1]


def getsearch(TS_CI_IDs, ZabbixConfig, source, db_config):
    zapi = ZabbixAPI(ZabbixConfig[source]['url'], user=ZabbixConfig[source]['login'],
                     password=ZabbixConfig[source]['password'])
    ip_regexp = "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}"
    ci_regexp = "CI[0-9]{8}"
    # Обновление - не только КЭ, но и ip
    if TS_CI_IDs is None or TS_CI_IDs == "":
        return ""
    else:
        if TS_CI_IDs[:6] == 'group:':
            group_name = TS_CI_IDs.split(":")[1]
            group = zapi.hostgroup.get(output=['groupid'],
                                       filter={'name': group_name})
            g_id = [g['groupid'] for g in group]
            hosts = zapi.host.get(output=['hostid'],
                                  groupids=g_id,
                                  selectInterfaces=['ip'])
            ips = [h['interfaces'][0]['ip'] for h in hosts]
            TS_CI_IDs = "; ".join(ips)

        TS_CI_IDs = delete_spaces(re.sub("/", " ", TS_CI_IDs.replace(';', ' ').replace(',', ' '))).split()
    my_ip = []
    ci_list = []
    allist = []
    Test_TS_CI_IDs = list(TS_CI_IDs)

    for ips in Test_TS_CI_IDs:
        if re.match(ip_regexp, ips) is not None:
            my_ip.append(ips)
            TS_CI_IDs.remove(ips)
        elif re.match(ci_regexp, ips) is not None:
            ci_list.append(ips)
            TS_CI_IDs.remove(ips)

    if len(my_ip) > 0:
        try:
            allist.extend(find_lists(zapi, my_ip, 'ip'))
        except Exception as err:
            #print(err)
            allist.append({'id': None,
                           'name': u"Нет доступа к Zabbix API. Обратитесь к администраторам Zabbix",
                           'ip': None, 'ismon': '0', 'groups': 'None'})

    if len(TS_CI_IDs) > 0:
        try:
            allist.extend(find_lists(zapi, TS_CI_IDs, 'host'))
        except Exception as err:
            #print(err)
            allist.append({'id': None,
                           'name': u"Нет доступа к Zabbix API. Обратитесь к администраторам Zabbix",
                           'ip': None, 'ismon': '0', 'groups': 'None'})

    if len(ci_list) > 0:
        try:
            os.environ['NLS_LANG'] = 'American_America.AL32UTF8'
            con = cx_Oracle.connect('{}/{}@{}:{}/{}'.format(db_config[4],
                                                    db_config[5],
                                                    db_config[1],
                                                    db_config[2],
                                                    db_config[3]))  # @UndefinedVariable
            cur = con.cursor()
            query_ci_list = ""
            index = 0
            for ci in ci_list:
                if index == 0:
                    query_ci_list = query_ci_list + "('" + ci
                    index += 1
                else:
                    query_ci_list = query_ci_list + "','" + ci

            query_ci_list += "')"

            all_ci_query = returnquery(query_ci_list)


            cur.execute(all_ci_query)
            all_ci_list = cur.fetchall()
            cur.close()
            con.close()

            if not all_ci_list:
                allist.append({'id': None,
                               'name': u"Что-то пошло не так.",
                               'ip': None, 'ismon': '0', 'groups': 'Not Found'})

            ips = [h[1] for h in all_ci_list]

            if len(ips) > 0:
                try:
                    allist.extend(find_lists(zapi, all_ci_list, 'ip', hostKE='true'))
                except Exception as err:
                    #print(err)
                    allist.append({'id': None,
                                   'name': u"Нет доступа к Zabbix API. Обратитесь к администраторам Zabbix",
                                   'ip': None, 'ismon': '0', 'groups': 'None'})
        except Exception as err:
            allist.append({'id': None,
                           'name': u"Нет доступа к SM реплике. обратитесь к администратору.",
                           'ip': None, 'ismon': '0'})
            #print(err)

    allist = json.dumps(allist, ensure_ascii=False)
    allist = json.loads(allist)
    return allist