from api import *
_fs = APIContainer("cli_a65443261b39d00d", "beUisVYWNEU8s0WCgdgUCh2yRJi7ut0i")
token = "GOvAbKyv3aOot1sy9emcTmpdn6d"
table_id = "tblgP75665t0WrOQ"

def DEBUG_OUT(data=None, json=None, file='request.json'):
    """调试时输出数据到文件中."""
    with open(file, 'w') as f:
        json_str = ujson.dumps(data, indent=4, ensure_ascii=False) if data else json # 格式化写入 JSON 文件
        f.write(json_str)

with open("request.json", 'r') as f:
    result = ujson.loads(f.read())

a = _fs.cloud.app_table_search(token, table_id)
table_items = result['data']['items']
item = table_items[0]
fields = item['fields']
creator_name = fields['创建人'][0]['name']
bill_list = fields['发票']
for bill in bill_list:
    pdf_url = bill['tmp_url']
    url = bill['url']
    print(pdf_url)
    print(url)
    break