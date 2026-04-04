import asyncio
import httpx
from datetime import datetime

# 配置
PAT_TOKEN = "patcwx5vX4lDXmmcK.d71c96b0e23cd0763569b78e091b74d195d41832c29f79dc72a82e65e7b74a49"
MASTER_BASE_ID = "appITVvwl1rimUNWX" 
TARGET_TABLE_NAME = "Base 资产清单"
HEADERS = {"Authorization": f"Bearer {PAT_TOKEN}"}

# 修正后的精准获取行数逻辑
async def get_count(client, base_id, table_id):
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    params = {"pageSize": 1, "fields[]": []} # 极简请求，只为获取 offset 链
    count = 0
    offset = None
    try:
        while True:
            if offset: params["offset"] = offset
            resp = await client.get(url, headers=HEADERS, params=params)
            if resp.status_code != 200: break
            data = resp.json()
            count += len(data.get("records", []))
            offset = data.get("offset")
            if not offset: break
    except:
        pass
    return count

async def main():
    async with httpx.AsyncClient(timeout=120.0) as client: # 增加超时容错
        # 1. 扫描所有 Base 和 Table
        base_res = await client.get("https://api.airtable.com/v0/meta/bases", headers=HEADERS)
        all_bases = base_res.json().get("bases", [])
        current_table_ids = []
        sync_list = []

        for b in all_bases:
            t_res = await client.get(f"https://api.airtable.com/v0/meta/bases/{b['id']}/tables", headers=HEADERS)
            for t in t_res.json().get("tables", []):
                current_table_ids.append(t['id'])
                sync_list.append({"b_id": b["id"], "b_name": b["name"], "t_id": t["id"], "t_name": t["name"]})

        # 2. 获取清单存量（用于清理）
        m_url = f"https://api.airtable.com/v0/{MASTER_BASE_ID}/{TARGET_TABLE_NAME}"
        m_records = []
        m_offset = None
        while True:
            m_res = await client.get(m_url, headers=HEADERS, params={"offset": m_offset} if m_offset else {})
            res_data = m_res.json()
            m_records.extend(res_data.get("records", []))
            m_offset = res_data.get("offset")
            if not m_offset: break

        # 3. 循环同步（更新/新增）
        for item in sync_list:
            cnt = await get_count(client, item["b_id"], item["t_id"])
            match = next((r for r in m_records if r["fields"].get("Table ID") == item["t_id"]), None)
            
            payload = {
                "fields": {
                    "Base Name": item["b_name"],
                    "Table Name": item["t_name"],
                    "Table ID": item["t_id"],
                    "Record Count": cnt,
                    "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
            }
            if match: await client.patch(f"{m_url}/{match['id']}", headers=HEADERS, json=payload)
            else: await client.post(m_url, headers=HEADERS, json=payload)

        # 4. 物理清理 (V3.0)
        for r in m_records:
            if r["fields"].get("Table ID") not in current_table_ids:
                await client.delete(f"{m_url}/{r['id']}", headers=HEADERS)

if __name__ == "__main__":
    asyncio.run(main())
