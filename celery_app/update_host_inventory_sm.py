import cx_Oracle
import os
import sys
import re
import socket
scripts_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')
sys.path.append(scripts_directory)
import datetime
from celery_app.update_hosts_inventory_queries import ci_query_all_servers,ci_query_all_services,ci_relations_query_all, contact_query_all, ci_ir_group_email
from celery_app.celery_help_functions import db_connect,get_zabbix_conf,zabbix_conn
from celery.utils.log import get_logger

CITypes = ['DEV (разработка)',
           'ИФТ (тестирование ИФТ/ПИР)',
           'HF (тестирование срочных изменений)',
           'ПРОМ (промышленная среда)',
           'ПРОМ (Stand-In)',
           'ИНФ (инфраструктурных серверов)',
           'ST3 (системное тестирование разработчиками исправлений в промышленную версию)',
           'ST1 (системное тестирование разработчиками следующего релиза)',
           'ST2 (системное тестирование разработчиками версии ИФТ/ПСИ текущего релиза)',
           'LT (проведение нагрузочного тестирования)',
           'ПСИ (проведение ПСИ)',
           'EDU (обучение)',
           'MSV (межсистемное взаимодействие тестирования)',
           'АФТ (автоматизированного и функционального тестирования)',
           'MINOR-CHECK',
           'MAJOR-CHECK',
           'MINOR-GO',
           'MAJOR-GO']


def getTSCIList(HostCIID, CIRelationsList, CITypeList, CIList):
    """Возвращаем IDs тестовых стендов, к которым относится данная КЭ
    :param HostCIID:
    :param CIRelationsList:
    :param CITypeList:
    :param CIList:
    :param TSCIList:
    :param recursionIndex:
    :return:
    """
    TSCIList = []
    as_ci_list = []
    ir_list = []
    stack = list()
    stack.append((HostCIID, 1))

    while stack:
        (cur_CIID, level) = stack.pop()
        if level > 8:
            return
        if cur_CIID in CIRelationsList:
            for CIID in CIRelationsList[cur_CIID]:
                if CIID in CIList:
                    for CI in CIList[CIID]:
                        if CIID == CI[0] and CI[0] not in ['CI00353209']:
                            # Debug("Checkpoint_10:" + CIID)
                            if (CI[2] in CITypeList or
                                CI[3] == "sbvirtcluster" or (
                                        re.match("^ТС.*", CI[1]) and (CI[3] == "collection"))) and CI not in TSCIList:
                                if len(TSCIList) < 21:
                                    TSCIList.append(CI)
                            elif CI[3] in ['infresource', 'dbmsinstance'] and CI[2] not in [
                                'Файл', 'Сервис', 'Терминальный сервис']:
                                ir_list.append(CI)
                            elif CI[3] == "bizservice" and CI[2] in ('Инфраструктура', 'АС', 'Техническая поддержка', 'Сервис', 'Внешняя', 'SandBox'):
                                as_ci_list.append(CI)
                                break
                            # Debug("Checkpoint_1:" + CIID)

                            stack.append((CIID, level + 1))
    return TSCIList, as_ci_list, ir_list

def parse_ip(ip_addr):
    # actions-read-write
    if ip_addr is not None:
        out = re.findall(r'(?:\d{1,3}\.){3}\d{1,3}', ip_addr)
        if len(out) == 1:
            return out[0]

def get_ip_by_dns(dns_name):
    host_data = socket.gethostbyname(dns_name)
    return host_data


def process_zabbix_host(zabbix_host,zapi,ci_list_all_servers,ci_list_all_services,ci_relations_list_all,sm_contact_list_all,ir_group_email):
    zabbix_host_ci_count = 0
    zabbix_host_ci_id = "UNKNOWN"
    zabbix_host_admin_name = "UNKNOWN"
    zabbix_host_responsibility_group = "UNKNOWN"
    zabbix_host_os_responsibility_group = "UNKNOWN"
    zabbix_host_admin_email = "UNKNOWN"
    zabbix_host_admin_department = "UNKNOWN"
    zabbix_host_ts_admin_names = "UNKNOWN"
    zabbix_host_ts_admin_emails = "UNKNOWN"
    zabbix_host_ts_admin_emails_short = "UNKNOWN"
    zabbix_host_ts_admin_departments = "UNKNOWN"
    ts_ci_ids = "UNKNOWN"
    ts_ci_names = "UNKNOWN"
    ts_subtypes = "UNKNOWN"
    zabbix_host_environment = "UNKNOWN"

    zabbix_host_sm_status = "UNKNOWN"

    ts_ci_list = []

    as_ci_list = []
    ir_type_list = []
    as_ci_id = "UNKNOWN"
    as_ci_name = "UNKNOWN"
    ac_ci_assignment = "UNKNOWN"
    as_ci_criticality = "UNKNOWN"

    zabbix_host_interfaces = zabbix_host['interfaces']
    if len(zabbix_host_interfaces) == 0:
        return
    zabbix_host_name = zabbix_host["name"]
    zabbix_host_inventory = zabbix_host['inventory']
    if type(zabbix_host_inventory) == list:
        return
    if zabbix_host['inventory_mode'] == '-1':
        return
    zabbixHostIP = zabbix_host_interfaces[0]["ip"]

    if zabbixHostIP == '':
        zabbixHostIP = get_ip_by_dns(zabbix_host_interfaces[0]["dns"])

    actual_host_presented = 0
    virtual_host_presented = 0

    if zabbixHostIP in ci_list_all_servers:
        for [LOGICAL_NAME, TITLE, IP_ADDRESSES, SUBTYPE, TYPE, TPS_ASSIGNEE_NAME, TPS_DNS_NAME, TPS_PLATFORM,
             HPC_STATUS,
             SB_RESPONSIBILITY_WG_NAME, ASSIGNMENT, SB_SERVICE_LEVEL, ENVIRONMENT, SB_ADMIN_GROUP2_NAME,
             ADMINISTRATOR_LIST] in ci_list_all_servers[zabbixHostIP]:
            if SUBTYPE in ['Виртуальный', 'LDOM', 'LPAR', 'Логический', 'nPAR',
                           'Физический', None] and IP_ADDRESSES is not None and parse_ip(
                IP_ADDRESSES) is not None and zabbixHostIP == parse_ip(IP_ADDRESSES):

                if actual_host_presented and HPC_STATUS == 'Выведен':
                    continue

                zabbix_host_ci_count = zabbix_host_ci_count + 1
                zabbix_host_ci_id = LOGICAL_NAME
                if ENVIRONMENT is not None and ENVIRONMENT != '':
                    zabbix_host_environment = ENVIRONMENT
                if TPS_ASSIGNEE_NAME is not None:
                    zabbix_host_admin_name = TPS_ASSIGNEE_NAME
                if ASSIGNMENT is not None:
                    zabbix_host_responsibility_group = ASSIGNMENT
                if SB_ADMIN_GROUP2_NAME is not None:
                    zabbix_host_os_responsibility_group = SB_ADMIN_GROUP2_NAME
                if HPC_STATUS != 'Выведен':
                    actual_host_presented = 1
                if SUBTYPE == 'Физический':
                    physicalHostPresented = 1
                if SUBTYPE == 'Виртуальный':
                    virtual_host_presented = 1

                if virtual_host_presented and actual_host_presented:
                    break

    if zabbix_host_ci_id != "UNKNOWN":
        if actual_host_presented:
            zabbix_host_sm_status = "Active"
        else:
            zabbix_host_sm_status = "Deleted"

    if zabbix_host_admin_name in sm_contact_list_all:
        for FULL_NAME, EMAIL, TITLE, HPC_DEPT_NAME, FIRST_NAME, LAST_NAME in sm_contact_list_all[zabbix_host_admin_name]:
            if FULL_NAME == zabbix_host_admin_name:
                if EMAIL is not None:
                    zabbix_host_admin_email = EMAIL
                if HPC_DEPT_NAME is not None:
                    zabbix_host_admin_department = HPC_DEPT_NAME
                break

    ts_ci_list, as_ci_list, ir_list = getTSCIList(zabbix_host_ci_id, ci_relations_list_all, CITypes, ci_list_all_services)

    ir_type_list = []
    ir_admin_list = []
    ir_assignment_email = ''
    ir_administrator_group_email = ''

    """ Цикл по ир-ам кэ """
    for CI_LOGICAL_NAME, LS_TITLE, LS_SUBTYPE, LS_TYPE, LS_TPS_ASSIGNEE_NAME, LS_TPS_DNS_NAME, LS_TPS_PLATFORM, \
        LS_HPC_STATUS, SB_RESPONSIBILITY_WG_NAME, ASSIGNMENT, SB_ADMINISTRATOR_GROUP, SB_SERVICE_LEVEL, ENVIRONMENT, \
        SB_ADMIN_GROUP2_NAME, ADMINISTRATOR_LIST in ir_list:
        ir_type_list.append(LS_SUBTYPE)
        if ADMINISTRATOR_LIST:
            ir_admin_list.extend([admin.strip() for admin in ADMINISTRATOR_LIST.split(';')])
        if ASSIGNMENT and ASSIGNMENT in ir_group_email:
            if len(ir_assignment_email + ir_group_email[ASSIGNMENT]) < 127:
                if ir_assignment_email and ir_group_email[ASSIGNMENT] not in ir_assignment_email:
                    ir_assignment_email = ir_assignment_email + ';' + ir_group_email[ASSIGNMENT]
                else:
                    ir_assignment_email = ir_group_email[ASSIGNMENT]
        if SB_ADMINISTRATOR_GROUP and SB_ADMINISTRATOR_GROUP in ir_group_email:
            if len(ir_administrator_group_email + ir_group_email[SB_ADMINISTRATOR_GROUP]) < 127:
                if ir_administrator_group_email and ir_group_email[SB_ADMINISTRATOR_GROUP] not in ir_administrator_group_email:
                    ir_administrator_group_email = ir_administrator_group_email + ';' + ir_group_email[SB_ADMINISTRATOR_GROUP]
                else:
                    ir_administrator_group_email = ir_group_email[SB_ADMINISTRATOR_GROUP]

    ir_type_list = list(set(ir_type_list))
    ir_admin_list = list(set(ir_admin_list))
    ir_admin_list_email = []
    """ Собираем список емейлов администроторов ир-ов куда выходит кэ"""
    for admin in ir_admin_list:
        if admin in sm_contact_list_all:
            for FULL_NAME, EMAIL, TITLE, HPC_DEPT_NAME, FIRST_NAME, LAST_NAME in sm_contact_list_all[admin]:
                if EMAIL:
                    ir_admin_list_email.append(EMAIL)
    ir_admin_list_str = ';'.join(sorted(set(ir_admin_list_email)))

    if len(ts_ci_list) > 0:
        ts_ci_list.sort(key=lambda tup: tup[0])
        for [CI_LOGICAL_NAME, LS_TITLE, LS_SUBTYPE, LS_TYPE, LS_TPS_ASSIGNEE_NAME, LS_TPS_DNS_NAME,
             LS_TPS_PLATFORM, LS_HPC_STATUS, SB_RESPONSIBILITY_WG_NAME, ASSIGNMENT,SB_ADMINISTRATOR_GROUP, SB_SERVICE_LEVEL, ENVIRONMENT,
             SB_ADMIN_GROUP2_NAME, ADMINISTRATOR_LIST] in ts_ci_list:
            if ts_ci_ids == "UNKNOWN":
                ts_ci_ids = str(CI_LOGICAL_NAME)
            else:
                ts_ci_ids = ts_ci_ids + ";" + str(CI_LOGICAL_NAME)
            if ts_ci_names == "UNKNOWN":
                ts_ci_names = str(LS_TITLE)
            else:
                ts_ci_names = ts_ci_names + ";" + str(LS_TITLE)
            if ts_subtypes == "UNKNOWN":
                ts_subtypes = str(LS_SUBTYPE.split()[0])
            else:
                ts_subtypes = ts_subtypes + ";" + str(LS_SUBTYPE.split()[0])
            if ADMINISTRATOR_LIST is not None:
                for k in sorted([i.strip() for i in ADMINISTRATOR_LIST.split(';')]):
                        for FULL_NAME, EMAIL, TITLE, HPC_DEPT_NAME, FIRST_NAME, LAST_NAME in sm_contact_list_all[k]:
                            """Составляем строку Имен администраторов стендов сервера на основе поля администратор 
                            каждого КЭ стенда, в котором находится сервер """
                            if zabbix_host_ts_admin_names == "UNKNOWN" and FULL_NAME is not None:
                                zabbix_host_ts_admin_names = FULL_NAME.split("(")[0].strip()
                            elif FULL_NAME is not None and FULL_NAME.split("(")[
                                0].strip() not in zabbix_host_ts_admin_names:
                                zabbix_host_ts_admin_names = zabbix_host_ts_admin_names + ";" + FULL_NAME.split("(")[
                                    0].strip()
                            """Составляем строку E-MAIL администраторов стендов сервера на основе поля администратор 
                            каждого КЭ стенда, в котором находится сервер """
                            if zabbix_host_ts_admin_emails == "UNKNOWN" and EMAIL is not None:
                                zabbix_host_ts_admin_emails = EMAIL
                            elif EMAIL is not None and EMAIL not in zabbix_host_ts_admin_emails:
                                zabbix_host_ts_admin_emails = zabbix_host_ts_admin_emails + ";" + EMAIL
                            """Составляем строку ОТДЕЛОВ СБТ, в которых работают администраторы стендов сервера на основе 
                            поля администратор каждого КЭ стенда, в котором находится сервер """
                            if zabbix_host_ts_admin_departments == "UNKNOWN" and HPC_DEPT_NAME is not None:
                                zabbix_host_ts_admin_departments = HPC_DEPT_NAME
                            elif HPC_DEPT_NAME is not None and HPC_DEPT_NAME not in zabbix_host_ts_admin_departments:
                                zabbix_host_ts_admin_departments = zabbix_host_ts_admin_departments + ";" + HPC_DEPT_NAME

    if len(as_ci_list) > 0:
        as_ci_id = as_ci_list[0][0]
        as_ci_name = as_ci_list[0][1]
        ac_ci_assignment = as_ci_list[0][9]
        as_ci_criticality = as_ci_list[0][11]

    if len(zabbix_host_ts_admin_names) > 64:
        zabbix_host_ts_admin_names = zabbix_host_ts_admin_names[:64][:(zabbix_host_ts_admin_names[:64].rfind(';'))]
    if len(zabbix_host_ts_admin_emails) > 128:
        zabbix_host_ts_admin_emails_short = zabbix_host_ts_admin_emails[:128][:(zabbix_host_ts_admin_emails[:128].rfind(';'))]

    ir_type_list.sort(key=lambda tup: tup[0])
    ir_type_list_str = ";".join(ir_type_list)
    ts_subtypes_str = ";".join(list(set(ts_subtypes.split(';'))))
    if len(ts_subtypes_str) > 255:
        ts_subtypes_str = ts_subtypes_str[:255][:(ts_subtypes_str[:255].rfind(';'))]

    if zabbix_host_ci_id != zabbix_host_inventory['tag'] or \
            zabbix_host_environment != zabbix_host_inventory['serialno_a'] or \
            as_ci_id != zabbix_host_inventory['asset_tag'] or \
            as_ci_criticality != zabbix_host_inventory['url_b'] or \
            ac_ci_assignment != zabbix_host_inventory['hardware_full'] or \
            as_ci_name != zabbix_host_inventory['software'] or \
            zabbix_host_admin_name != zabbix_host_inventory['poc_1_name'] or \
            zabbix_host_responsibility_group != zabbix_host_inventory['contact'] or \
            zabbix_host_os_responsibility_group != zabbix_host_inventory['site_notes'] or \
            zabbix_host_admin_email != zabbix_host_inventory['poc_1_email'] or \
            zabbix_host_admin_department != zabbix_host_inventory['poc_1_notes'] or \
            ts_ci_names != zabbix_host_inventory['location'] or \
            ts_subtypes_str != zabbix_host_inventory['site_address_b'] or \
            zabbix_host_sm_status != zabbix_host_inventory['url_c'] or \
            ts_ci_ids != zabbix_host_inventory['hardware'] or \
            zabbix_host_ts_admin_names != zabbix_host_inventory["poc_2_name"] or \
            zabbix_host_ts_admin_emails_short != zabbix_host_inventory['poc_2_email'] or \
            ir_admin_list_str != zabbix_host_inventory['notes'] or \
            zabbix_host_ts_admin_departments != zabbix_host_inventory['poc_2_notes'] or \
            ir_type_list_str != zabbix_host_inventory['site_address_a'] :

        zapi.host.update(hostid=zabbix_host['hostid'],
                         inventory=dict(asset_tag=as_ci_id,
                                        serialno_a=zabbix_host_environment,
                                        tag=zabbix_host_ci_id,
                                        software=as_ci_name,
                                        #poc_1_name=zabbix_host_admin_name,
                                        poc_1_name = ir_administrator_group_email,
                                        contact=zabbix_host_responsibility_group,
                                        site_notes=zabbix_host_os_responsibility_group,
                                        #poc_1_email=zabbix_host_admin_email,
                                        poc_1_email=ir_assignment_email,
                                        poc_1_notes=zabbix_host_admin_department,
                                        url_c=zabbix_host_sm_status,
                                        url_b=as_ci_criticality,
                                        location=ts_ci_names,
                                        hardware=ts_ci_ids,
                                        hardware_full=ac_ci_assignment,
                                        poc_2_name=zabbix_host_ts_admin_names,
                                        poc_2_email=zabbix_host_ts_admin_emails_short,
                                        poc_2_notes=zabbix_host_ts_admin_departments,
                                        notes=ir_admin_list_str,
                                        #notes=zabbix_host_ts_admin_emails,
                                        site_address_a=ir_type_list_str,
                                        site_address_b=ts_subtypes_str))



def update_host_inventory_sm(source):
    logger = get_logger('config')
    engine = db_connect()
    with engine.connect() as conn:
        res = conn.execute(f"select * from configs.databases where name='ORACLESM'")
        result = res.fetchall()
    hpsm_config = result[0]
    os.environ['NLS_LANG'] = 'American_America.AL32UTF8'
    con = cx_Oracle.connect('{}/{}@{}:{}/{}'.format(hpsm_config[4],
                                                    hpsm_config[5],
                                                    hpsm_config[1],
                                                    hpsm_config[2],
                                                    hpsm_config[3]))
    cur = con.cursor()

    cur.execute(ci_query_all_servers)
    ci_list_all_servers_temp = cur.fetchall()
    ci_list_all_servers = {}
    for el in ci_list_all_servers_temp:
        if parse_ip(el[2]) is not None:
            if parse_ip(el[2]) in ci_list_all_servers:
                ci_list_all_servers[parse_ip(el[2])].append(el)
            else:
                ci_list_all_servers[parse_ip(el[2])] = [el]
    del ci_list_all_servers_temp

    cur.execute(ci_query_all_services)
    ci_list_all_services = cur.fetchall()
    ci_list_all_services_temp = dict()
    for el in ci_list_all_services:
        if el[0] is not None:
            if el[0] in ci_list_all_services_temp:
                ci_list_all_services_temp[el[0]].append(el)
            else:
                ci_list_all_services_temp[el[0]] = [el]
    ci_list_all_services = ci_list_all_services_temp
    del ci_list_all_services_temp

    cur.execute(ci_relations_query_all)
    ci_relations_list_all = cur.fetchall()
    CIRelationsList_new = dict()
    for CIID, RelatedCIIDs in ci_relations_list_all:
        if RelatedCIIDs is not None:
            if RelatedCIIDs in CIRelationsList_new:
                CIRelationsList_new[RelatedCIIDs].append(CIID)
            else:
                CIRelationsList_new[RelatedCIIDs] = [CIID]
    ci_relations_list_all = CIRelationsList_new
    del CIRelationsList_new

    cur.execute(contact_query_all)
    sm_contact_list_all_temp = cur.fetchall()
    sm_contact_list_all = {}
    for el in sm_contact_list_all_temp:
        if el[0] is not None:
            if el[0] in sm_contact_list_all:
                sm_contact_list_all[el[0]].append(el)
            else:
                sm_contact_list_all[el[0]] = [el]
    del sm_contact_list_all_temp

    cur.execute(ci_ir_group_email)
    ir_group_email_temp = cur.fetchall()
    ir_group_email = {}
    for el in ir_group_email_temp:
        if el[0] is not None:
            ir_group_email[el[0]] = el[1]
    del ir_group_email_temp

    cur.close()
    con.close()
    zapi = zabbix_conn(source)
    allZabbixHosts = zapi.host.get(output=["hostid", "host", "hostip", "name", "inventory_mode"],
                                   sortfield=["name"],
                                   selectInterfaces=["interfaceid", "hostid", "ip", "dns"],
                                   selectInventory=True)

    for current_zabbix_host in allZabbixHosts:
        #print(datetime.datetime.now(),current_zabbix_host['host'])
        try:
            process_zabbix_host(current_zabbix_host,zapi,ci_list_all_servers,ci_list_all_services,ci_relations_list_all,sm_contact_list_all,ir_group_email)
        except BaseException as e:
            pass
    logger.info(f"Completed update inventory on source: {source}")



if __name__ == '__main__':
    update_host_inventory_sm('Zabbix Test')
