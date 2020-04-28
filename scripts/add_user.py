from scripts.help_functions_zbx import get_allowed_grps,get_zabbix_conf
from scripts.help_functions import db_connect
from scripts.create_zno import create_zno
import asyncio
from functools import partial

async def add_user(zapi, user, source, mode, logger):
    if '(' not in user['surname']:
        user['surname'] = f'{user["surname"]}({user["sigma_login"]})'
    ZabbixConfig = await get_zabbix_conf()
    allowed_groups = await get_allowed_grps(source, with_id=True)
    selected_groups_id = {}
    usergrpids = [str(ZabbixConfig[source]['default_user_group'])]
    for group in user['selected_groups']:
        if group in allowed_groups:
            selected_groups_id[group] = allowed_groups[group]


    ### Check usergroup exist and create if not:
    for group,groupid in selected_groups_id.items():
        if len(group) > 64:
            group_name = group[:55] + '_' + str(groupid)
        else:
            group_name = group
        usergrp = await zapi.usergroup.get(output=['usrgrpid'],filter={'name': group_name})
        if usergrp:
            usergrpids.append(usergrp[0]['usrgrpid'])
        else:
            try:
                usergrpid_res = await zapi.usergroup.create(name=group_name, rights=[{'permission': 3, 'id': groupid}])
                usergrpid = usergrpid_res['usrgrpids'][0]
                usergrpids.append(usergrpid)

                #create actions
                await create_action(zapi,group_name,usergrpid, groupid,0 ,str(ZabbixConfig[source]['email_media_type']), source, ZabbixConfig)
                await create_action(zapi,group_name+'_SMS', usergrpid, groupid,1 ,str(ZabbixConfig[source]['phone_media_type']), source, ZabbixConfig)

            except BaseException as e:
                print('at create actions',str(e))
                return False
    #create/update user

    result = await createUser(zapi, user, usergrpids, ZabbixConfig, mode, source)
    if result == True:
        loop = asyncio.get_event_loop()
        loop.create_task(log_data(logger, mode, user, source, usergrpids))
    return result

async def run_task_with_executor(loop,func,*args):
    func_for_execute = partial(func,*args)
    return loop.run_in_executor(None,func_for_execute)

async def log_data(logger,mode,user,source,usergrpids):
    log_text = f'{mode} user {user} on source: {source} grpids: {usergrpids}'
    zno_text = f"Прошу привести настройки для уз {user['login']} на {source} в соответствие с следующей конфигурацией: {user}"
    zno_type = 'Промышленный' if 'Prom' in source else 'Тестовый'
    engine = await db_connect('selfportal')
    async with engine.acquire() as conn:
        res = await conn.execute("select value from selfportal.app_config where keyword='zno_create_uz'")
        result = await res.fetchall()
    engine.close()
    if result[0][0] == 'True':
        create_result = await run_task_with_executor(asyncio.get_event_loop(), create_zno, zno_text, zno_type)
        zno_result, zno_text = await create_result
        if zno_result:
            log_text += ';Номер ЗНО:' + zno_text
        else:
            log_text += ';Зно не создано, код ошибки:' + str(zno_text)
    logger.info(log_text)

async def create_action(zapi,group,usergrpid,groupid, PhoneFlag ,sendtypeid, source, ZabbixConfig):
    PromConditions = [
        {'conditiontype': '4',
         'operator': '5',
         'value': '3',
         'formulaid': "C"
         }]
    PromConditions_SMS = [
        {'conditiontype': '4',
         'operator': '5',
         'value': '4',
         'formulaid': "C"
         }]

    TestConditions = [{'conditiontype': '15',
                       'operator': '3',
                       'value': 'ADMIN',
                       'formulaid': "C"
                       }, {'conditiontype': '15',
                           'operator': '3',
                           'value': 'MONITORING',
                           'formulaid': "D"
                           }, ]
    TestConditions_SMS = [{'conditiontype': '4',
                           'operator': '5',
                           'value': '5',
                           'formulaid': "E"
                           }]
    conditions = [{'conditiontype': '0',
                   'operator': '0',
                   'value': groupid,
                   'formulaid': "A"
                   }]
    if ZabbixConfig[source]['user_name'] == 'Zabbix Тест Sigma':
        service_cond_operator = '7'
    else:
        service_cond_operator = '11'
    if 'Prom' in source:
        if not PhoneFlag:
            conditions.extend(PromConditions)
        else:
            conditions.extend(PromConditions_SMS)
    else:
        conditions.extend(TestConditions)
        if PhoneFlag:
            conditions.extend(TestConditions_SMS)

    service_condition = {'conditiontype': '16',
                    'operator': service_cond_operator,  # 7 for 3.x, 11 for 4.x
                    'value': '',
                    'formulaid': "B"}
    conditions.append(service_condition)

    formula = ' and '.join([x['formulaid'] for x in conditions])
    await zapi.action.create(
        name=group,
        eventsource='0',
        status='0',
        esc_period='1m',
        def_shortdata='{HOST.HOST} - {TRIGGER.STATUS}: {TRIGGER.NAME}',
        def_longdata='[TRIGGER.STATUS]:{TRIGGER.STATUS}\r\n[INVENTORY.LOCATION]:{INVENTORY.LOCATION}\r\n[TRIGGER.NAME]:{TRIGGER.NAME}\r\n[TRIGGER.SEVERITY]:{TRIGGER.SEVERITY}\r\n[HOST.NAME1]:{HOST.NAME1}\r\n[IPADDRESS1]:{IPADDRESS1}\r\n[INVENTORY.TAG1]:{INVENTORY.TAG1}\r\n[ITEM.NAME1]:{ITEM.NAME1}\r\n[ITEM.VALUE1]:{ITEM.VALUE1}\r\n[TRIGGER.ID]:{TRIGGER.ID}\r\n[EVENT.ID]:{EVENT.ID}\r\n[TRIGGER.URL]:{TRIGGER.URL}\r\n[ITEM.ID]:{ITEM.ID}\r\n[DATE]:{DATE}\r\n[TIME]:{TIME}\r\n[TRIGGER.DESCRIPTION]:{TRIGGER.DESCRIPTION}\r\n[EVENT.TAGS]:{EVENT.TAGS}',
        r_shortdata='{HOST.HOST} - {TRIGGER.STATUS}: {TRIGGER.NAME}',
        r_longdata='[TRIGGER.STATUS]:{TRIGGER.STATUS}\r\n[INVENTORY.LOCATION]:{INVENTORY.LOCATION}\r\n[TRIGGER.NAME]:{TRIGGER.NAME}\r\n[TRIGGER.SEVERITY]:{TRIGGER.SEVERITY}\r\n[HOST.NAME1]:{HOST.NAME1}\r\n[IPADDRESS1]:{IPADDRESS1}\r\n[INVENTORY.TAG1]:{INVENTORY.TAG1}\r\n[ITEM.NAME1]:{ITEM.NAME1}\r\n[ITEM.VALUE1]:{ITEM.VALUE1}\r\n[TRIGGER.ID]:{TRIGGER.ID}\r\n[EVENT.ID]:{EVENT.ID}\r\n[TRIGGER.URL]:{TRIGGER.URL}\r\n[ITEM.ID]:{ITEM.ID}\r\n[DATE]:{DATE}\r\n[TIME]:{TIME}\r\n[TRIGGER.DESCRIPTION]:{TRIGGER.DESCRIPTION}\r\n[EVENT.TAGS]:{EVENT.TAGS}',
        maintenance_mode='1',
        recovery_msg='1',
        filter={
            'evaltype': '3',
            'formula': formula,
            'conditions': conditions},
        operations=[{'operationtype': '0',
                     'esc_step_from': '1',
                     'esc_step_to': '1',
                     'evaltype': '0',
                     'recovery': '1',
                     'recovery_msg': '1',
                     'esc_period': '0',
                     'opconditions': [],
                     'opmessage': {'default_msg': '1', 'mediatypeid': sendtypeid},
                     'opmessage_grp': [{'usrgrpid': usergrpid}]}],
        recovery_operations=[{'operationtype': '11', 'opmessage': {'default_msg': '1'}}])

async def createUser(zapi, user, groupIDs, ZabbixConf, mode, source):
    if type(user['phone']) == list:
        user['phone'] = user['phone'][0]
    try:
        users_medias = [{'mediatypeid': str(ZabbixConf[source]['email_media_type']), 'sendto': user['mail_sigma'].strip(),
                         'active': int(user['mail_sigma_enable']), 'severity': "63",
                         'period': "1-7,00:00-24:00"},
                        {'mediatypeid':  str(ZabbixConf[source]['email_media_type']), 'sendto': user['mail'].strip(),
                         'active': int(user['mail_enable']), 'severity': "63",
                         'period': "1-7,00:00-24:00"}]
        if len(user['phone'].strip()) > 5:
            users_medias.append({'mediatypeid':  str(ZabbixConf[source]['phone_media_type']), 'sendto': user['phone'].strip(),
                                 'active': int(user['phone_enable']), 'severity': "63",
                                 'period': "1-7,00:00-24:00"})

        if mode=='create':
            await zapi.user.create(
                alias=user['login'],
                name=user['name'],
                surname=user['surname'],
                passwd="1",
                lang="ru_RU",
                autologin="1",
                usrgrps=[{'usrgrpid': x} for x in groupIDs],
                user_medias=users_medias
            )
        else:
            zabbix_user = await zapi.user.get(output='userid', filter={'alias': user['login']}, selectUsrgrps=['name','usrgrpid'])
            zabbix_user = zabbix_user[0]
            allowed_groups = await get_allowed_grps(source, with_id=True)
            zabbix_user['selected_grps'] = []
            for grp in zabbix_user['usrgrps']:
                if grp['name'] not in allowed_groups and grp['usrgrpid'] != str(ZabbixConf[source]['default_user_group']):
                    if grp['name'].split('_')[-1] in allowed_groups.values():
                        continue
                    zabbix_user['selected_grps'].append({'usrgrpid':grp['usrgrpid']})
            for grpid in groupIDs:
                zabbix_user['selected_grps'].append({'usrgrpid': grpid})
            await zapi.user.update(
                surname=user['surname'],
                userid=zabbix_user['userid'],
                usrgrps=zabbix_user['selected_grps'],
                user_medias=users_medias
            )
        return True
    except Exception as e:
        return False