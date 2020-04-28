import argparse
import requests
from lxml import etree as ET

class Preprocess():
    def __init__(self):
        self.severities = {}

    def Parser(self):
        parser_arg = argparse.ArgumentParser()
        parser_arg.add_argument('-A', '--action', help='Action for SM Create/Update default Create', default='Create')
        parser_arg.add_argument('-u', '--url', help='Address API SM', default='10.121.204.68')
        parser_arg.add_argument('-p', '--port', help='Port API SM', default='13085')
        parser_arg.add_argument('-s', '--secure', help='https or http default http', default='http')
        parser_arg.add_argument('-U', '--user', help='USER for API SM', default='int_zabbix')
        parser_arg.add_argument('-P', '--passw', help='PASSWORD for API SM', default='123456')
        parser_arg.add_argument('-num', '--number', default='')
        parser_arg.add_argument('-des', '--description', default='Default TAG for Description')
        parser_arg.add_argument('-ser', '--service', default='CI01810729')
        parser_arg.add_argument('-tem', '--TemplateID', default='10000795')
        parser_arg.add_argument('-pri', '--priority', default='5. Низкий')
        parser_arg.add_argument('-ass', '--assignmentGroup', default='СБТ ДК ОСА Группа мониторинга (Прутских С.С.) (00010285)')
        parser_arg.add_argument('-ini', '--initiator', default='zabbix (00642903)')
        parser_arg.add_argument('-cal', '--callbackContact', default='zabbix (00642903)')
        parser_arg.add_argument('-asi', '--assignee', default='zabbix (00642903)')
        parser_arg.add_argument('-dev', '--device', default='CI00894355')
        parser_arg.add_argument('-res', '--resolution', default='')
        parser_arg.add_argument('-res_cod', '--resolutionCode', default='Решено полностью')
        parser_arg.add_argument('-dea', '--deadlineBreachCause', default='')
        parser_arg.add_argument('-typ', '--type', default='Тестовый')
        parser_arg.add_argument('-dom', '--domen', default='ALPHA')
        parser_arg.add_argument('-act', '--activ', default='Создание учетной записи и  оповещений (Zabbix)')
        parser_arg.add_argument('-sev', '--severity', default='Не знаю')
        parser_arg.add_argument('-tag', '--tag', default='')
        return parser_arg

    def XMLrequest(self, action, number, description, service, TemplateID, priority, assignmentGroup, initiator, callbackContact, assignee, device, resolution, resolutionCode, deadlineBreachCause, type, domen, activ, severity, tag):
        soapenv = 'http://schemas.xmlsoap.org/soap/envelope/'
        pws = 'http://servicecenter.peregrine.com/PWS'
        com = 'http://servicecenter.peregrine.com/PWS/Common'
        Env = ET.Element('{%s}Envelope' % (soapenv), nsmap={"soapenv":"http://schemas.xmlsoap.org/soap/envelope/", "pws":"http://servicecenter.peregrine.com/PWS", "com":"http://servicecenter.peregrine.com/PWS/Common"})
        Hea = ET.SubElement(Env, '{%s}Header' % (soapenv))
        Bod = ET.SubElement(Env, '{%s}Body' % (soapenv))
        actio = "{%s}" + action + "SBAPI_SBRequestRequest"
        Act = ET.SubElement(Bod, actio % (pws))
        mod = ET.SubElement(Act, '{%s}model' % (pws))
        key = ET.SubElement(mod, '{%s}keys' % (pws))
        num = ET.SubElement(key, '{%s}number' % (pws))
        num.text = u''+ number +''
        ins = ET.SubElement(mod, '{%s}instance' % (pws))
        des = ET.SubElement(ins, '{%s}description' % (pws))
        des.text = u''+ description +''
        ser = ET.SubElement(ins, '{%s}service' % (pws))
        ser.text = u''+ service +''
        tpl = ET.SubElement(ins, '{%s}tplID' % (pws))
        tpl.text = u''+ TemplateID +''
        pri = ET.SubElement(ins, '{%s}priority' % (pws))
        pri.text = u''+ priority +''
        asi = ET.SubElement(ins, '{%s}assignmentGroup' % (pws))
        asi.text = u''+ assignmentGroup +''
        opt = ET.SubElement(ins, '{%s}options' % (pws))
        opt.text = ET.CDATA(u'<form><select id="q1" label="Класс среды объектов мониторинга" mandatory="true" sbmodify="true" style="combo" visible="true">' + type + '</select><select id="q2" label="Домен" mandatory="true" sbmodify="true" style="combo" visible="true">' + domen + '</select><select id="q3" label="Тип запроса" mandatory="true" sbmodify="true" style="combo" visible="true">' + activ + '</select><select id="q4" label="Уровень критичности ИТ-услуги" mandatory="true" sbmodify="true" style="combo" visible="true">' + severity + '</select><text id="q5" label="Тэг" mandatory="false" sbmodify="true" sbtype="string" visible="true">' + tag + '</text></form>')
        res_cod = ET.SubElement(ins, '{%s}resolutionCode' % (pws))
        res_cod.text = u''+ resolutionCode +''
        res = ET.SubElement(ins, '{%s}resolution' % (pws))
        res.text = u''+ resolution +''
        ini = ET.SubElement(ins, '{%s}initiator' % (pws))
        ini.text = u''+ initiator +''
        cal = ET.SubElement(ins, '{%s}callbackContact' % (pws))
        cal.text = u''+ callbackContact +''
        asi = ET.SubElement(ins, '{%s}assignee' % (pws))
        asi.text = u''+ assignee +''
        dev = ET.SubElement(ins, '{%s}device' % (pws))
        dev.text = u''+ device +''
        dea = ET.SubElement(ins, '{%s}deadlineBreachCause' % (pws))
        dea.text = u''+ deadlineBreachCause +''
        return Env

    def Send(self, session, secure, url, port, user, passw, action, XML, cooki):

        link = secure + '://' + url + ':' + port + '/sc62server/ws'
        if cooki == '':
            head = {'Connection': 'Keep-Alive', 'SOAPAction': action, 'Accept-Encoding': 'text/xml;charset=UTF-8', 'Content-Type': 'text/xml;charset=UTF-8'}
        else:
            head = {'Connection': 'Keep-Alive', 'SOAPAction': action, 'Accept-Encoding': 'text/xml;charset=UTF-8', 'Content-Type': 'text/xml;charset=UTF-8', 'Cookie': 'JSESSIONID='+ cooki}
        API_SM = session.post(url=link, auth=(user, passw), headers=head, data=XML.encode('utf-8'))
        return API_SM

def create_zno(msg,env_type):
    with requests.Session() as session:
        try:

            parser = ET.XMLParser(remove_blank_text=True)
            EndZNO = ['StartWork', 'Complete']
            cooki = '56ECA4D7C381FF33730B3EE7B781B9AE'
            answer = ''
            prepro = Preprocess()
            parser_arg = prepro.Parser()
            args = parser_arg.parse_args([])
            args.type = env_type
            #Create
            XML = prepro.XMLrequest(args.action, args.number, msg, args.service, args.TemplateID, args.priority, args.assignmentGroup, args.initiator, args.callbackContact, args.assignee, args.device, args.resolution, args.resolutionCode, args.deadlineBreachCause, args.type, args.domen, args.activ, args.severity, args.tag)
            XML = ET.tostring(XML, encoding='utf-8').decode('utf-8')
            answer = prepro.Send(session, args.secure, args.url, args.port, args.user, args.passw, args.action, XML, cooki)
            code = answer.status_code
            #cooki = answer.cookies['JSESSIONID']
            answer = ET.XML(answer.text, parser)

            for event in answer:
                args.number = event[0][0][0][0].text
            for modify in EndZNO:
                args.action = modify
                if modify == 'Complete':
                    args.resolution = 'Выполнено'
                XML = prepro.XMLrequest(args.action, args.number, msg, args.service, args.TemplateID, args.priority, args.assignmentGroup, args.initiator, args.callbackContact, args.assignee, args.device, args.resolution, args.resolutionCode, args.deadlineBreachCause, args.type, args.domen, args.activ, args.severity, args.tag)
                XML = ET.tostring(XML, encoding='utf-8').decode('utf-8')
                answer = prepro.Send(session, args.secure, args.url, args.port,  args.user, args.passw, args.action, XML, cooki)
                answer = ET.XML(answer.text, parser)
        except BaseException as e:
            return False, code
        else:
            return True, args.number

if __name__ == '__main__':
    create_zno('test_zno')