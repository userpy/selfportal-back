import pandas
import json

async def xls_to_json_dict_parser(file_xlsx, sheet_name):
    xlsx_json = json.loads(pandas.read_excel(file_xlsx, sheet_name=sheet_name).to_json())
    keys_json = list(map(lambda x: x, xlsx_json.keys()))
    max_json_lenth = max(list(map(lambda x: len(x), xlsx_json.values())))
    response =[]
    for i in range(max_json_lenth):
        val = {key: xlsx_json[key][str(i)] for key in keys_json}
        val['SubMasterGroup'] = [val['SubGroup']]
        response.append(val)
    return response