from pandas import read_sql
import os
import sys
import sqlalchemy as sa
import time
from celery_app.celery_help_functions import db_connect,get_zabbix_conf,zabbix_conn

scripts_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')
sys.path.append(scripts_directory)

from celery.utils.log import get_logger

def generate_table(name):
    metadata = sa.MetaData()
    return sa.Table(name, metadata,
                    sa.Column('groupid', sa.Integer, primary_key=True),
                    sa.Column('groupname', sa.String(100), unique=True),
                    sa.Column('CIs', sa.String(200), unique=True))

def checkInList(TSList, txtString):
    found = False
    for TS in TSList:
        if txtString == TS:
            found = True
            break
    return found

def get_host_group_mapping_list_sql(grp_table_name):
    grp_table = generate_table(grp_table_name)
    engine = db_connect()
    with engine.connect() as conn:
        df = read_sql(grp_table.select(), conn)
        df = df.rename(index=str, columns={'groupid': 'GROUP_ID', 'groupname': 'GROUP_NAME'})
    return df

def get_ts_ci_not_in_zabbix(source,logger):
    try:
        ZabbixConfig = get_zabbix_conf()
        zapi = zabbix_conn(source,ZabbixConfig)
        hosts = zapi.host.get(output=["hostid", "host", "hostip", "name"], sortfield=["name"],
                              selectInterfaces=["interfaceid", "hostid", "ip", "port"],
                              selectInventory=['hardware', 'location'])

        ci_list_all = {}
        for host in hosts:
            if type(host['inventory']) != list and len({'hardware', 'location'} & set(host['inventory'].keys())) == 2:
                if host['inventory']['hardware'] not in ('UNKNOWN', ''):
                    host_hardware = host['inventory']['hardware'].split(';')
                    host_location = host['inventory']['location'].split(';')
                    for i in range(len(host_hardware)):
                        if host_hardware[i].strip() not in ci_list_all and len(host_location[i]) <= 128 \
                                and (
                                host_location[i].strip().startswith('ТС') or host_location[i].strip().startswith('АС')):
                            ci_list_all[host_hardware[i].strip()] = host_location[i].strip()

        zbx_groups_dataframe = get_host_group_mapping_list_sql(ZabbixConfig[source]['group_table'])
        zbx_groups_dataframe.isnull().values.any()
        df_groups = zbx_groups_dataframe['CIs'].values.tolist()

        TS_CI_List = []

        for host in hosts:
            hostInventory = host['inventory']
            arrayLen = len(hostInventory)
            if arrayLen > 0:
                if 'hardware' in hostInventory.keys():
                    hostTSIDS = hostInventory["hardware"].split(";")
                    for hostTSID in hostTSIDS:
                        host_group_mapping_row = [1 for item in df_groups if hostTSID in item.split(',')]

                        if len(host_group_mapping_row) == 0 and not checkInList(TS_CI_List, hostTSID):
                            TS_CI_List.append(hostTSID)

        result = {}
        for TS_CI in TS_CI_List:
            if TS_CI.strip() in ci_list_all:
                result[TS_CI.strip()] = ci_list_all[TS_CI]
        return result
    except BaseException as e:
        logger.error(f'Error: {str(e)}')
        return {}


def create_host_groups_by_ts(ts_list,source,logger):
    ZabbixConfig = get_zabbix_conf()
    zapi = zabbix_conn(source, ZabbixConfig)

    hostGroups = zapi.hostgroup.get(output=["groupid", "name"],
                                    sortfield=["name"])
    hostGroups = {el['name']:el for el in hostGroups}
    grp_table_name = ZabbixConfig[source]['group_table']
    zbx_groups_dataframe = get_host_group_mapping_list_sql(grp_table_name)
    zbx_groups_dataframe.isnull().values.any()

    tsList = ts_list

    for ts in tsList:
        newGroupName = tsList[ts]
        newGroupCI = ts
        #host_group_mapping_row = [1 for item in zbx_groups_dataframe if newGroupCI in item.split(',')]
        host_group_mapping_row = zbx_groups_dataframe[zbx_groups_dataframe['CIs'].str.contains(newGroupCI)]

        if len(host_group_mapping_row) != 0:
            continue

        groupExists = -1

        if newGroupName in hostGroups:
            groupExists = int(hostGroups[newGroupName]['groupid'])
        else:
            newGroupId = zapi.hostgroup.create(name=newGroupName)
            time.sleep(1)

        if groupExists != -1:
            if len(zbx_groups_dataframe[zbx_groups_dataframe['GROUP_ID'] == groupExists]) > 0:
                grp_table = generate_table(grp_table_name)
                engine = db_connect()
                with engine.connect() as conn:
                    conn.execute(grp_table.update().values(CIs=grp_table.c.CIs + ',' + newGroupCI).where(grp_table.c.groupid == groupExists))
                    conn.execute("commit")
                logger.info(f"Updated row on source: {source}, row:{groupExists},{newGroupName} added CI: {newGroupCI}")
            else:
                newGroupId = {'groupids': [groupExists]}
                groupExists = -1

        if groupExists == -1:
            try:
                grp_table = generate_table(grp_table_name)
                engine = db_connect()
                with engine.connect() as conn:
                    conn.execute(grp_table.insert().values(groupid=newGroupId['groupids'][0], groupname=newGroupName, CIs=newGroupCI))
                    conn.execute("commit")
                logger.info(f"Added row on source: {source}, row:{newGroupId['groupids'][0]},{newGroupName},{newGroupCI}")
            except BaseException as e:
                logger.error(f'Error: {str(e)}')
    logger.info(f"Completed update mapping on source: {source}")


def update_mapping(source):
    #logger = create_logger('app.conf', 'config')
    logger = get_logger('config')
    create_host_groups_by_ts(get_ts_ci_not_in_zabbix(source,logger),source,logger)

if __name__ == '__main__':
    update_mapping('Zabbix Prom Win')
