import asyncio
import httpx
from datetime import datetime

# 配置
PAT_TOKEN = "patcwx5vX4lDXmmcK.d71c96b0e23cd0763569b78e091b74d195d41832c29f79dc72a82e65e7b74a49"
MASTER_BASE_ID = "appITVvwl1rimUNWX" 
TARGET_TABLE_NAME = "Base 资产清单"
HEADERS = {"Authorization": f"Bearer {PAT_TOKEN}"}

async def main():
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. 扫描所有 Base
        base_res = await client.get("https://api.airtable.com/v0/meta/bases", headers=HEADERS)
        all_bases = base_res.json().get("bases", [])
        current_table_ids = []
        sync_list = []

        # 2. 直接从元数据获取所有表的行数 (这是最快的方法)
        for b in all_bases:
            t_res = await client.get(f"https://api.airtable.com/v0/meta/bases/{b['id']}/tables", headers=HEADERS)
            tables = t_res.json().get("tables", [])
            for t in tables:
                current_table_ids.append(t['id'])
                # 直接使用元数据里的 rowCount，无需分页请求
                row_count = t.get("rowCount", 0) 
                sync_list.append({"b_name": b["name"], "t_id": t["id"], "t_name": t["name"], "count": row_count})

        # 3. 获取清单存量记录
        m_url = f"https://api.airtable.com/v0/{MASTER_BASE_ID}/{TARGET_TABLE_NAME}"
        m_records = []
        offset = None
        while True:
            r = await client.get(m_url, headers=HEADERS, params={"offset": offset} if offset else {})
            data = r.json()
            m_records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset: break

        # 4. 执行更新/新增
        for item in sync_list:
            match = next((r for r in m_records if r["fields"].get("Table ID") == item["t_id"]), None)
            payload = {"fields": {"Base Name": item["b_name"], "Table Name": item["t_name"], "Table ID": item["t_id"], "Record Count": item["count"], "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M")}}
            if match: await client.patch(f"{m_url}/{match['id']}", headers=HEADERS, json=payload)
            else: await client.post(m_url, headers=HEADERS, json=payload)

        # 5. 物理清理 (V3.0)
        for r in m_records:
            if r["fields"].get("Table ID") not in current_table_ids:
                await client.delete(f"{m_url}/{r['id']}", headers=HEADERS)

if __name__ == "__main__":
    asyncio.run(main())
