#!/usr/bin/python

import sys
import requests

if __name__ == '__main__':
    try:
        requests.post(url='http://selfportal.zabbix.ca.sbrf.ru/api/eventdashboard/new_problem',json={'id':sys.argv[1],'msg':sys.argv[2]})
    except:
        pass
