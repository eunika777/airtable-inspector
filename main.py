import asyncio
import httpx
from datetime import datetime

# 配置（保持你运行了几个月都没问题的原始数据）
PAT_TOKEN = "patcwx5vX4lDXmmcK.d71c96b0e23cd0763569b78e091b74d195d41832c29f79dc72a82e65e7b74a49"
MASTER_BASE_ID = "appITVvwl1rimUNWX" 
TARGET_TABLE_NAME = "Base 资产清单"
HEADERS = {"Authorization": f"Bearer {PAT_TOKEN}", "Content-Type": "application/json"}

async def main():
    async with httpx.AsyncClient(timeout=300.0) as client:
        print("🚀 开始全量同步 (原生逻辑复刻)...")
        
        # 1. 获取所有 Base
        base_url = "https://api.airtable.com/v0/meta/bases"
        base_res = await client.get(base_url, headers=HEADERS)
        all_bases = base_res.json().get("bases", [])

        # 2. 先获取“资产清单”表的现有记录（用于比对 ID）
        master_url = f"https://api.airtable.com/v0/{MASTER_BASE_ID}/{TARGET_TABLE_NAME}"
        m_res = await client.get(master_url, headers=HEADERS)
        m_records = m_res.json().get("records", [])

        # 3. 遍历所有 Base 下的所有 Table
        for b in all_bases:
            tables_url = f"https://api.airtable.com/v0/meta/bases/{b['id']}/tables"
            t_res = await client.get(tables_url, headers=HEADERS)
            if t_res.status_code != 200: continue
            
            for t in t_res.json().get("tables", []):
                # 精准计数逻辑
                count = 0
                offset = None
                table_data_url = f"https://api.airtable.com/v0/{b['id']}/{t['id']}"
                
                while True:
                    params = {"pageSize": 100, "fields[]": []}
                    if offset: params["offset"] = offset
                    r = await client.get(table_data_url, headers=HEADERS, params=params)
                    if r.status_code != 200: break
                    data = r.json()
                    count += len(data.get("records", []))
                    offset = data.get("offset")
                    if not offset: break
                
                # 匹配并写入
                match = next((r for r in m_records if r["fields"].get("Table ID") == t["id"]), None)
                payload = {
                    "fields": {
                        "Base Name": b["name"],
                        "Table Name": t["name"],
                        "Table ID": t["id"],
                        "Record Count": count,
                        "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                }

                if match:
                    await client.patch(f"{master_url}/{match['id']}", headers=HEADERS, json=payload)
                else:
                    await client.post(master_url, headers=HEADERS, json=payload)
                
                print(f"✅ {t['name']} = {count}")
                await asyncio.sleep(0.2) # 严格遵守频率限制

if __name__ == "__main__":
    asyncio.run(main())
