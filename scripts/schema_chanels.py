import re
import numpy
from scripts.help_functions import db_connect
# Поступает одно значнени Имя % Цифра, либо много [Имя % Цифра, Имя % Цифра, Имя % Цифра]
# Example  'Te0/1/2%0.5, Tu2840110%0.8,  Ethernet48%10'
# Example Ethernet48%10

async def get_cnl_num(db, zabbix, group):
    engine = await db_connect(db)
    async with engine.acquire() as conn:
        exec = await conn.execute(f"SELECT {group.lower()} FROM host_counter_zabbix_wan WHERE zabbix_name ='{zabbix}'")
        res = await exec.fetchall()
    engine.close()
    return res[0][0]

async def update_cnl_num(db, zabbix, group):
    engine = await db_connect(db)
    async with engine.acquire() as conn:
        await conn.execute(f"UPDATE host_counter_zabbix_wan SET {group} = {group} + 1 WHERE zabbix_name = '{zabbix}'")
        await conn.execute("commit")
    engine.close()

async def get_groups(groups):
    master_groups = ['Core Wan','External Node','Internet node']
    groups_final = []
    for i in master_groups:
        slave_group = list(filter(lambda x: x.split('/')[0].upper() == i.upper(),groups))
        max_slave_group = list(map(lambda x: len(x),slave_group))
        if len(max_slave_group) != 0:
            max_slave_group_len=max(max_slave_group)
            max_slave_group= list(filter(lambda x: len(x) == max_slave_group_len,slave_group))
            groups_final.extend(max_slave_group)
    return groups_final

async def logn_group_to_Id(host_id ,hg):
    hg =list(filter(lambda x: len(x['hosts']) > 0,hg))
    groups = []
    for i in hg:
        if host_id in list(map(lambda x: x['hostid'],i['hosts'])):
            groups.append(i['name'])
    groups_final = await get_groups(groups)
    return groups_final

async def groups_updater(hosts,api):
    hg = await api.hostgroup.get(selectHosts='extend')

    groups_final = []
    for i in hosts:
        hostgroups=await logn_group_to_Id(host_id=i['hostid'], hg=hg)
        if len(hostgroups) != 0:
            i['hostgroups'] = hostgroups
            groups_final.append(i)
    return groups_final

async def update_chanel(api, SM_HOSTID):
    macros = await api.usermacro.get(hostids=[SM_HOSTID])
    macros.extend([{'macro': '{$SM_HOSTID}', 'value': SM_HOSTID},
                   {'macro': '{$SCREEN_LINK}',
                    'value': f'https://zabbix-cssm.sigma.sbrf.ru/zabbix_wan/'
                             f'zabbix.php?action=problem.view&page=1&filter_'
                             f'show=1&filter_hostids[]={SM_HOSTID}&filter_se'
                             f'verity=2&filter_set=1'}])

    await api.host.update({'hostid': SM_HOSTID, 'macros': macros})

async def rounded_to_decimal(number):
    number = re.search('(\d*).(\d*)', str(number))
    number1 = number.group(1)
    number2 = number.group(2)
    if len(number2) == 1 and int(number2) == 0:
        return int(number1)
    else:
        if len(number2) == 1:
            return float(f'{number1}.{number2}')
        else:
            response = float(f'{number1}.{number2[0]}')
            return response

async def __procent_and_bandswish_replace(procent, cnl_ifs):
    if procent.group(1) == None and procent.group(2) == None and procent.group(3):
        #cnl_ifs = procent.group(3)
        cnl_ifs = cnl_ifs
        bandswish = 1

    else:
        #cnl_ifs = procent.group(1)
        cnl_ifs = cnl_ifs
        bandswish = procent.group(2)
    return cnl_ifs, bandswish


async def splitter(item):
    CNL_IFS, BANDWIDTH = [], []
    items=item.split(',')

    for i in items:
        cnl_ifs = i
        i = re.search(r'\s*(\S*)%(\d*\.?\d*)|\s*(\S*)', i)
        cnl_ifs, bandswish = await __procent_and_bandswish_replace(i, cnl_ifs)
        CNL_IFS.append(cnl_ifs)
        BANDWIDTH.append(bandswish)

    if len(BANDWIDTH) > 1:
        #Если больше одного значения в массиве, считаем сренее арифметическое
        BANDWIDTH= await rounded_to_decimal(numpy.sum(list(map(float, BANDWIDTH))))
        res = re.search('(\d*).(\d*)|(\d*)', str(BANDWIDTH))
        if re.search('^0+$', res.group(2)):
            BANDWIDTH = res.group(1)
        else:
            BANDWIDTH = BANDWIDTH
    else:
        res = re.search('(\d*).(\d*)|(\d*)',str(BANDWIDTH[0]))
        if re.search('^0+$',res.group(2)):
            BANDWIDTH = res.group(1)
        else:
            BANDWIDTH = BANDWIDTH[0]

    CNL_IFS=','.join(CNL_IFS)
    return BANDWIDTH, CNL_IFS

async def empty_none(val):
    if val == None:
        return None
    elif str(val).replace(' ', '') == '':
        return None
    else:
        return val


async def get_macros(snmp_community, ospf_peers, Interfaces_ISIS, EIBGP_peers,BGP_peers,BANDWIDTH, CNL_IFS, PROXY_NAME, SLA_TESTS):
        nOSPF_PEERS = await empty_none(ospf_peers)
        nISIS_INTERFACES = await empty_none(Interfaces_ISIS)
        nEIGRP_PEERS = await empty_none(EIBGP_peers)
        nBGP_PEERS = await empty_none(BGP_peers)
        nBANDWIDTH = await empty_none(BANDWIDTH)
        nCNL_IFS = await empty_none(CNL_IFS)
        nPROXY_NAME = await empty_none(PROXY_NAME)
        nSLA_TESTS = await empty_none(SLA_TESTS)
        macros = [
            {"macro": "{$SNMP_COMMUNITY}", "value": f'{snmp_community}'},
            {'macro': '{$OSPF_PEERS}', 'value': f'{nOSPF_PEERS}'},
            {'macro': '{$ISIS_INTERFACES}', 'value': f'{nISIS_INTERFACES}'},
            {'macro': '{$EIGRP_PEERS}', 'value': f'{nEIGRP_PEERS}'},
            {'macro': '{$BGP_PEERS}', 'value': f'{nBGP_PEERS}'},
            {'macro': '{$BANDWIDTH}', 'value': f'{nBANDWIDTH}'},
            {'macro': '{$CNL_IFS}', 'value': f'{nCNL_IFS}'},
            {'macro': '{$PROXY_NAME}', 'value': f'{nPROXY_NAME}'},
            {'macro': '{$SLA_TESTS}', 'value':f'{nSLA_TESTS}'}
            # ДОПИСАТЬ МАКровс
        ]
        return macros

async def get_group_name(group_names):
        #Получение имени групп
        arr = []
        arrGroupsLeagacy = []
        count = 0
        for i in group_names:
            count +=1
            arr.append(i)
            arrGroupsLeagacy.append('/'.join(arr))

        return arrGroupsLeagacy

async def get_template_sub(SubGroup):
    if re.search(r'^(?i)Core Wan', SubGroup):
        templates_names = ['Extcon_channel_internal_v2', ]
    elif re.search(r'^(?i)External node', SubGroup):
        if SubGroup.split('/')[1] in ['B2B', 'Dealing', 'CIB']:
            templates_names = ['Extcon_channel_organization_v2', ]
        else:
            templates_names = ['Extcon_channel_external_v2', ]
    elif re.search(r'^(?i)Internet node', SubGroup):
        if re.search(r'^Internet node/Channels/External', SubGroup):
            templates_names = ['Extcon_channel_external_v2', 'Extcon_channel_QoS']
        else:
            templates_names = ['Extcon_channel_internal_v2']

    return templates_names

async def sub_master_group(groups):
    sub_master_groups = list(map(lambda x: x.split('/'), groups))
    group_name_arr = []
    for gr in sub_master_groups:
        groups_name = await get_group_name(gr)
        group_name_arr.extend(groups_name)

    groups_name = list(set(group_name_arr))
    return groups_name


async def get_or_create_host_id(zapi, group):
    hostgroup = await zapi.hostgroup.get(filter={"name": [group]})

    if len(hostgroup) == 0:
        hostgroup = await zapi.hostgroup.create({'name': group})
        group_id = hostgroup['groupids'][0]
    else:
        group_id = hostgroup[0]['groupid']
    return group_id


async def host_create(zapi, max_group, result_alarm_name, alarmer_name, group, zabbix, request):
    prox_min = await get_proyx_min(zapi)
    proxy_hostid = prox_min['proxyid']
    mygroup = await get_group_name(max_group.split('/'))
    groups_for_host = []
    for gr in mygroup:

        group_id = await get_or_create_host_id(zapi, gr)
        groups_for_host.append(dict(groupid=group_id))

    template =  await zapi.template.get(filter={'host':['Alarm-combiner']}, output=['host'])
    if len(template) == 0:
        raise TypeError('Not template Alarm-combiner')

    template_id = template[0]['templateid']
    try:
        alarm_combiner_struct = dict(name=result_alarm_name,#result Alarm
            proxy_hostid=proxy_hostid,
            host=alarmer_name,
            interfaces=[{
                "type": 2,
                "main": 1,
                "useip": 1,
                "ip": "127.0.0.1",
                "dns": "",
                "port": "162"
            }],
            groups=groups_for_host,
            macros = [
                {
                    "macro":"{$BGP_COUNT}",
                    "value":"0"
                },
                {
                    "macro": "{$HOSTGROUP_ID}",
                    "value": f"{group_id}"
                },
                {
                    "macro": "{$SCREEN_LINK}",
                    "value": f"https://zabbix-cssm.sigma.sbrf.ru/zabbix_wan/zabbix.php?action=problem.view&page=1&filter_show=1&filter_groupids[]={group_id}&filter_severity=2&filter_set=1"
                },

            ],
            inventory_mode = 1,
            inventory={
                "type":'Channel',
                "type_full":f"{max_group}"
            },
            templates = [
                {
                    'templateid':f'{template_id}'
                }
            ])
        await zapi.host.create(alarm_combiner_struct )
        request.app['zabbix_wan_logger'].info(f'USER ({request["user_id"]})|Info in app: Alarm-combiner created ({alarm_combiner_struct}) ')
        await update_cnl_num(db='configs', group=group, zabbix=zabbix)
    except Exception as err:
        request.app['zabbix_wan_logger'].error(f'USER ({request["user_id"]})|Error in app: Alarm-combiner {str(err)}')
        raise TypeError(err)


async def create_alarm_host(long_group, zapi, result_alarm_name, alarmer_name, group, zabbix, request):
    long_group.sort(key=lambda x: len(x))
    max_group = long_group[-1]
    hostgroup = await zapi.hostgroup.get(filter={'name':[max_group]}, selectHosts=['hostid'])
    if len(hostgroup) != 0:
        host_name=await zapi.host.get(filter={'hostid':list(map(lambda x:x['hostid'],hostgroup[0]['hosts']))}, search={'host':'ALARM_CNL'})
        if len(host_name) != 0:
            request.app['zabbix_wan_logger'].info(
                f'USER ({request["user_id"]})|Info in app: Alarm-combiner in group ({max_group}) already exists !')
        else:
            await host_create(zapi, max_group, result_alarm_name, alarmer_name, group=group, zabbix=zabbix,
                              request=request)
    else:
        await host_create(zapi, max_group, result_alarm_name, alarmer_name, group=group, zabbix=zabbix, request=request)

async def get_transport_group(group):
    Ngroup= group.split('/')[0]
    if Ngroup.upper() == 'Core Wan'.upper():
        response =  'WAN'
    elif Ngroup.upper() == 'External node'.upper():
        response = 'EXT'
    elif Ngroup.upper() == 'Internet node'.upper():
        response=  'INET'
    return response

async def get_proyx_min(zapi):
    proxy_ids = await zapi.proxy.get(selectHosts='extend')
    proxy = []

    for i in proxy_ids:
        host_id = list(map(lambda x: x['hostid'], i['hosts']))
        items = await zapi.item.get(filter={'hostid': host_id}, countOutput='extend')
        result = dict(host=i['host'], items=items, proxyid = i['proxyid'])
        proxy.append(result)
    if len(proxy) == 0:
        raise TypeError('No proxy! You must add a proxy')
    items_min = min(list(map(lambda x: int(x['items']),proxy)))
    min_proxy = list(filter(lambda x: int(x['items']) == int(items_min),proxy))
    return min_proxy[0]

async def check_link_template(templates_names, zapi):
    template_for_filter = await zapi.template.get(filter={'name': templates_names}, selectParentTemplates=['host'],
                                                  output=['parentTemplates'], searchByAny=True)
    parentTemplates = list(map(lambda x: x['parentTemplates'], template_for_filter))
    parentTemplatesHumanFormat = []
    for i in parentTemplates:
        parentTemplatesHumanFormat.extend(i)
    if len(list(filter(lambda x: x['host'] == 'Alarm-combiner', parentTemplatesHumanFormat))):
        templates_names.remove('Alarm-combiner')

    return templates_names

async def get_good_proxy(proxy_balanser, templates_names, zapi):
    prox_min = await get_proyx_min(zapi)
    PROXY_NAME = prox_min['host']
    proxy_hostid = prox_min['proxyid']
    if re.search(r'10058$', PROXY_NAME):
        templates_names.append('proxy_name_zbxw-prx-msk_10058')
    if 'Alarm-combiner' in templates_names:
        templates_names = await check_link_template(templates_names, zapi)
    templatesids = await zapi.template.get(output=['templateid'],
                                           filter={'name': templates_names})
    return templatesids, PROXY_NAME, proxy_hostid

async def get_long_group(groups):
    max_list = max(list(map(lambda x: len(x),groups)))
    long_group = list(filter(lambda x: len(x) == int(max_list), groups))
    return long_group[0]


async def group_creator(groups, zapi):
    groups_list = []
    for group in groups:
        hostgroup = await zapi.hostgroup.get(filter={"name": [group]})
        if len(hostgroup) == 0:
            hostgroup = await zapi.hostgroup.create({'name': group})
            groups_list.append(dict(groupid=hostgroup['groupids'][0]))
        else:
            groups_list.append(dict(groupid=hostgroup[0]['groupid']))
    return groups_list

async def flusn_none(dict_c):
    for k, v in dict_c.items():
        if dict_c[k] != None:
            pass
        else:
            dict_c[k] = ''
    return dict_c

async def get_scheme_to_send( i, proxy_balanser, zapi, zabbix, file_mode=False, request=None):
        i = await flusn_none(i)
        name = i.get('ChannelName', '')
        ip = i.get('Management ip address', '')
        BANDWIDTH, CNL_IFS = await splitter(i.get('Interfaces: ALL', ''))
        if file_mode:
            groups_name = await sub_master_group(['/'.join(i.get('SubGroup', ''))])
        else:
            groups_name = await sub_master_group(i.get('SubMasterGroup', ''))
        group= await get_transport_group(groups_name[0])
        SubGroup = await get_long_group(groups_name)
        cnl_num = await get_cnl_num(db='configs', group=group, zabbix=zabbix)
        templates_names = await get_template_sub(SubGroup)
        alarmer_name = f'ALARM_CNL-{group}-{cnl_num}'
        if i.get('ChannelName','') == i.get('Result Alarm Name','') :
            templates_names.append('Alarm-combiner')
        elif i.get('Result Alarm Name','').replace(' ', '') != '':
            await create_alarm_host(groups_name, zapi, i.get('Result Alarm Name',''), alarmer_name, group, zabbix, request=request)
        templatesids, PROXY_NAME, proxy_hostid = await get_good_proxy(proxy_balanser, templates_names, zapi)
        groups = await group_creator(groups=groups_name, zapi=zapi)
        interfaces = [{'type': 2, 'main': 1, 'useip': 1, 'ip': f'{ip}', 'dns': "", 'port': '161'}]
        host = f'CNL-{group}-{cnl_num}'
        snmp_community = i.get('SNMP community', None)
        if snmp_community == None or snmp_community.replace(' ','') == '' :
            snmp_community = 'sbrf'
        ospf_peers = i.get('OSPF peers', None)
        Interfaces_ISIS = i.get('Interfaces: ISIS', None)
        EIBGP_peers = i.get('EIBGP peers', None)
        BGP_peers = i.get('BGP peers', None)
        SLA_TESTS = i.get('SLA tests',None)
        macros= await get_macros(snmp_community=snmp_community, ospf_peers=ospf_peers, Interfaces_ISIS=Interfaces_ISIS,
                               EIBGP_peers=EIBGP_peers,BGP_peers=BGP_peers, BANDWIDTH=BANDWIDTH, CNL_IFS=CNL_IFS,
                               PROXY_NAME=PROXY_NAME, SLA_TESTS=SLA_TESTS)
        if re.search(r'^Internet node/Channels/External', SubGroup):
            nCNL_IFS_QOS = await empty_none(CNL_IFS.split(',')[0])
            macros.append({'macro': '{$CNL_IFS_QOS}', 'value':f'{nCNL_IFS_QOS}'})
        response = dict(host=host, name=name, interfaces=interfaces, groups=groups, templates=templatesids, proxy_hostid=proxy_hostid,
                     macros=macros, inventory_mode=1, inventory={'type':'Channel','type_full':f"{SubGroup}"})
        return response, group
