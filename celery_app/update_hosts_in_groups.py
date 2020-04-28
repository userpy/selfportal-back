import os
import sys
import sqlalchemy as sa
from pandas import read_sql
scripts_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')
sys.path.append(scripts_directory)
from celery_app.celery_help_functions import db_connect,get_zabbix_conf,zabbix_conn
from celery.utils.log import get_logger

def generate_table(name):
    metadata = sa.MetaData()
    return sa.Table(name, metadata,
                   sa.Column('groupid', sa.Integer, primary_key=True),
                   sa.Column('groupname', sa.String(100), unique=True),
                   sa.Column('CIs', sa.String(200), unique=True))

def get_host_group_mapping_list_sql(grp_table_name):
    grp_table_name = grp_table_name
    grp_table = generate_table(grp_table_name)
    engine = db_connect()
    with engine.connect() as conn:
        df = read_sql(grp_table.select(),conn)
        df = df.rename(index=str, columns={'groupid':'GROUP_ID','groupname':'GROUP_NAME'})
    return df

def update_hosts_in_groups(source):
    logger = get_logger('config')
    ZabbixConfig = get_zabbix_conf()
    zapi = zabbix_conn(source,ZabbixConfig)

    hostgroups = zapi.hostgroup.get(output=["groupid", "name"], selectHosts=["hostid", "name", "description"],
                                    sortfield="groupid")
    allZabbixHosts = zapi.host.get(output=["hostid", "host", "name", "flags", "description", "inventory_mode"], sortfield=["name"],
                                   selectInventory=True)

    zbx_groups_dataframe = get_host_group_mapping_list_sql(ZabbixConfig[source]['group_table'])
    zbx_groups_dataframe.isnull().values.any()

    jobProcessCounter = 0
    groupsUpdated = 0
    groupsNotUpdated = 0
    groupsNotInMapping = 0

    for hostGroup in hostgroups:
        hostgroupId = hostGroup["groupid"]
        host_group_hosts = hostGroup['hosts']
        hosts_in_group_static_ids = []
        for host in host_group_hosts:
            if host['description'].find("_static_") != -1:
                hosts_in_group_static_ids.append({'hostid': host['hostid']})
        hostGroupExistsInMapping = 0
        jobProcessCounter = jobProcessCounter + 1
        zabbixHostsInGroup = []
        zabbixHostsInGroup.extend(hosts_in_group_static_ids)

        df_result = zbx_groups_dataframe[zbx_groups_dataframe['GROUP_ID'] == int(hostgroupId)].values.tolist()
        if len(df_result)>0:
            group = df_result[0]
            if len(group) == 0:
                continue
            if len(group[2]) == 0:
                continue
            hostGroupExistsInMapping = 1
            for zabbixHost in allZabbixHosts:
                if zabbixHost['flags'] == "4":
                    continue
                if zabbixHost['description'].find("_static_") != -1:
                    continue
                zabbixHostInventory = zabbixHost['inventory']
                if type(zabbixHostInventory) == list:
                    continue
                if zabbixHost['inventory_mode'] == '-1':
                    continue
                if len(zabbixHostInventory) > 0 and zabbixHostInventory['hardware'] != "" and \
                                len(set(group[2].split(',')) & set(zabbixHostInventory['hardware'].split(';'))) > 0:
                    if not any(d['hostid'] == zabbixHost['hostid'] for d in zabbixHostsInGroup):
                        zabbixHostsInGroup.append({'hostid': zabbixHost['hostid']})

        if hostGroupExistsInMapping:
            zapi.hostgroup.massupdate(hosts=zabbixHostsInGroup, groups=[hostgroupId])
            if len(host_group_hosts) != len(zabbixHostsInGroup):
                groupsUpdated = groupsUpdated + 1
            else:
                groupsNotUpdated = groupsNotUpdated + 1
        else:
            groupsNotInMapping = groupsNotInMapping + 1

    logger.info(f'Updated hosts in groups for {source} groupsUpdated:{groupsUpdated}, groupsNotUpdated:{groupsNotUpdated}, groupsNotInMapping:{groupsNotInMapping}')

if __name__ == '__main__':
    update_hosts_in_groups('Zabbix Prom')

