from celery import Celery
from celery.schedules import crontab
from celery_once import QueueOnce
from celery_app.sm_report import generate_sm_report
from celery_app.update_mapping import update_mapping
from celery_app.update_hosts_in_groups import update_hosts_in_groups
from celery_app.update_host_inventory_sm import update_host_inventory_sm
from celery_app.celery_help_functions import db_connect
from celery_app.reallocate_hosts_in_groups_by_address_A import reallocate_hosts_in_base_groups
from celery_app.remove_deleted_hosts import remove_deleted_hosts
from celery_app.autofill_templates_by_group import link_correct_template_to_hosts_by_hostgroups
from scripts.help_functions import create_logger, create_config
import time

redis_url = 'redis://localhost:6379/0'
app=Celery('celery_app', broker=redis_url) # include=['tasks']

app.conf.ONCE = {
    'backend': 'celery_once.backends.Redis',
    'settings': {
        'url' : 'redis://localhost:6379/0',
        'default_timeout': 60*60
    }
}

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    #sender.add_periodic_task(crontab(minute='*/1'), test.s(), name='every 10')
    logger = create_logger(create_config('app.conf'), 'config')
    logger.propagate = False
    engine = db_connect()
    with engine.connect() as conn:
        res = conn.execute(f"select hour,minute,task_name,args from configs.celery_periodic_tasks")
        result = res.fetchall()
    for row in result:
        if row[3] != '':
            sender.add_periodic_task(crontab(hour=row[0], minute=row[1]), globals()[row[2]].s(*row[3].split(',')))
        else:
            sender.add_periodic_task(crontab(hour=row[0], minute=row[1]), globals()[row[2]].s())

@app.task(base=QueueOnce,once={'graceful': True, 'keys': ['source']})
def link_correct_template_to_hosts_by_hostgroups_task(source):
    link_correct_template_to_hosts_by_hostgroups(source)

@app.task(base=QueueOnce,once={'graceful': True, 'keys': ['source']})
def remove_deleted_hosts_task(source):
    remove_deleted_hosts(source)

@app.task(base=QueueOnce,once={'graceful': True, 'keys': ['source']})
def reallocate_hosts_in_base_groups_task(source):
    reallocate_hosts_in_base_groups(source)

@app.task(base=QueueOnce,once={'graceful': True, 'keys': ['source']})
def update_mapping_task(source):
    update_mapping(source)

@app.task(base=QueueOnce,once={'graceful': True, 'keys': ['source']})
def update_inventory_task(source):
    update_host_inventory_sm(source)

@app.task(base=QueueOnce,once={'graceful': True, 'keys': ['source']})
def update_hosts_in_groups_task(source):
    update_hosts_in_groups(source)

@app.task(base=QueueOnce,once={'graceful': True})
def sm_report():
    generate_sm_report()

def run_link_correct_template_to_hosts_by_hostgroups(source):
    link_correct_template_to_hosts_by_hostgroups_task.delay(source)

def run_remove_deleted_hosts(source):
    remove_deleted_hosts_task.delay(source)

def run_reallocate_hosts_in_base_groups(source):
    reallocate_hosts_in_base_groups_task.delay(source)

def run_update_hosts_in_groups(source):
    update_hosts_in_groups_task.delay(source)

def run_update_inventory(source):
    update_inventory_task.delay(source)

def run_update_mapping(source):
    update_mapping_task.delay(source)

def run_sm_report():
    sm_report.delay()

@app.task(base=QueueOnce,once={'graceful': True})
def test():
    print('yahoo!')
    time.sleep(5)
    print('yahoo2!')

def run_test():
    test.delay()

if __name__ == '__main__':
    run_test()


