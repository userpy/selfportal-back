import os
import sys
import logging
import sqlalchemy as sa
from pandas import read_sql
scripts_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')
sys.path.append(scripts_directory)
from celery_app.celery_help_functions import db_connect,get_zabbix_conf,zabbix_conn
from celery.utils.log import get_logger
from logging.handlers import RotatingFileHandler

# описание:
# скрипт распределяет шаблоны на узлы в зависимости от групп на узле. Он только добавляет,
# если какого-то шаблона быть на хосте не должно - он его не удалит.
# Сприпт опирается на таблицу, колонки которой описаны выше в функции
# колонка  шаблонов должна принимать в себя значения групп через запятую, запятая НЕ_ДОЛЖНА содержать рядом с собой пробелов
# колонка OS_type должна принимать в себя одно из значений ОС (см словарь ос групп)
# или "APP" если от ОС шаблон не зависит. В этой колонке должно быть только одно значение.
# ни одна из колонок для поля не должна быть пустой

dict_of_os_groups = {"hp-ux" : "IS OS HP-UX", "solaris" : "IS OS Solaris",
                     "linux" : "IS OS Linux", "aix" : "IS OS AIX", "windows" : "IS OS Windows"}
excluded_group = "Sigma servers"

def generate_table(name):
    metadata = sa.MetaData()
    return sa.Table(name, metadata,
                   sa.Column('HostGroupName', sa.String(255), unique=True),
                   sa.Column('TemplateName', sa.String(1000), unique=False),
                   sa.Column('OS_type', sa.String(100), unique=False))

def get_host_group_mapping_list_sql(grp_table_name):
    grp_table = generate_table(grp_table_name)
    engine = db_connect()
    with engine.connect() as conn:
        df = read_sql(grp_table.select(),conn)
    return df

# input: ['1234','1235','1236'],['88005', '58547']
def softly_link_template(hostids, templateid, zapi, source, logger):
    for hostid in hostids:
        try:
            zapi.host.massadd(hosts = [hostid], templates = templateid)
            logger.debug(f'SUCCESS link templateid {templateid} on hostdis {hostid} for {source}\n')
        except:
            logger.debug(f'FAILED link templateid {templateid} on hostdis {hostid} for {source}, try it by hands!\n')

# input:  ['1488','1489'], ['57843']
## output: ['1489']
def filter_hostids_by_template(hostids, templateid, zapi):
    all_templateid_hosts = [x['hostid'] for x in zapi.host.get(hostids = hostids, templateids = templateid, output = ['hostid'])]
    return all_templateid_hosts


# input:  ['1488','1489'], 'my example group'
## output: ['1489']
def filter_hostids_by_group(hostids, groupname, zapi):
    groupid = [x['groupid'] for x in zapi.hostgroup.get(output = ['groupid', 'name'], filter = {'name':[groupname]})]
    all_group_hosts = [x['hostid'] for x in zapi.host.get(hostids = hostids, groupids = groupid, output = 'hostid')]
    return all_group_hosts

def link_correct_template_to_hosts_by_hostgroups(source):
    logger = get_logger('config')
    ZabbixConfig = get_zabbix_conf()
    zapi = zabbix_conn(source,ZabbixConfig)

    # define file handler for debug log
    mylogger = logging.getLogger('detailed')
    mylogger.setLevel(logging.DEBUG)
    frh = RotatingFileHandler('/var/log/selfportal/autofill_templates_by_group.log', maxBytes=10485760, backupCount=10)
    frh.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    frh.setFormatter(formatter)
    mylogger.addHandler(frh)

    # get group-template dictionary
    Group_table_mapping = get_host_group_mapping_list_sql('Hostgroup_Template_table')

    for element in range(len(Group_table_mapping)):
        groupname = Group_table_mapping.iloc[element]['HostGroupName']
        templatenames = Group_table_mapping.iloc[element]['TemplateName'].split(",")
        OS_type = Group_table_mapping.iloc[element]['OS_type'].lower()
        if (templatenames == '') or (OS_type == ''):
            continue
        else:
            for template in templatenames:
                # get groupids and templateids
                target_groupid = [x['groupid'] for x in zapi.hostgroup.get(output = ['groupid', 'name'], filter = {'name':[groupname]})]
                target_templateids = [x['templateid'] for x in zapi.template.get(output = ['templateid', 'host'], filter = {'host':template})]
                if target_templateids == []:
                    logger.info(f'Template {template} in {source} not found!')
                    continue
                # get current all hosts in target group and filter by OS
                current_all_in_group = [x['hostid'] for x in zapi.host.get(output = ['hostid', 'name'], groupids = target_groupid)]
                if OS_type != "app":
                    current_all_in_group_filtered_by_OS = filter_hostids_by_group(current_all_in_group, dict_of_os_groups[OS_type], zapi)
                else:
                    current_all_in_group_filtered_by_OS = current_all_in_group
                # filter excluded group
                current_all_in_group_filtered_by_OS_with_excluded = filter_hostids_by_group(current_all_in_group_filtered_by_OS, excluded_group, zapi)
                current_all_in_group_filtered_by_OS_without_excluded = list(set(current_all_in_group_filtered_by_OS) - set(current_all_in_group_filtered_by_OS_with_excluded))
                # get current templated hosts
                current_all_templated_and_filtered_in_group = filter_hostids_by_template(current_all_in_group_filtered_by_OS_without_excluded, target_templateids, zapi)
                # calculate positive gap (set current all in group - set current templated from group) and link it
                positive_gap = list(set(current_all_in_group_filtered_by_OS_without_excluded) - set(current_all_templated_and_filtered_in_group))
                if positive_gap != []:
                    softly_link_template(positive_gap, target_templateids, zapi, source, mylogger)
            logger.info(f'Link hosts for {source} in group {groupname} with templatenames: {templatenames}')

if __name__ == '__main__':
    link_correct_template_to_hosts_by_hostgroups('Zabbix Test')