import asyncio
import httpx
from datetime import datetime

# 配置
PAT_TOKEN = "patcwx5vX4lDXmmcK.d71c96b0e23cd0763569b78e091b74d195d41832c29f79dc72a82e65e7b74a49"
MASTER_BASE_ID = "appITVvwl1rimUNWX" 
TARGET_TABLE_NAME = "Base 资产清单"
HEADERS = {"Authorization": f"Bearer {PAT_TOKEN}", "Content-Type": "application/json"}

async def get_real_count(client, base_id, table_id):
    count, offset = 0, None
    while True:
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}?pageSize=100"
        params = {"offset": offset} if offset else {}
        resp = await client.get(url, headers=HEADERS, params=params)
        if resp.status_code != 200: break
        data = resp.json()
        count += len(data.get("records", []))
        offset = data.get("offset")
        if not offset: break
    return count

async def main():
    async with httpx.AsyncClient(timeout=300.0) as client:
        print("🚀 开始同步...")
        
        # 1. 获取最新 Table 列表
        base_res = await client.get("https://api.airtable.com/v0/meta/bases", headers=HEADERS)
        all_bases = base_res.json().get("bases", [])
        current_tables = []
        for b in all_bases:
            t_res = await client.get(f"https://api.airtable.com/v0/meta/bases/{b['id']}/tables", headers=HEADERS)
            if t_res.status_code == 200:
                for t in t_res.json().get("tables", []):
                    current_tables.append({"b_id": b["id"], "b_name": b["name"], "t_id": t["id"], "t_name": t["name"]})
        
        active_ids = [item["t_id"] for item in current_tables]

        # 2. 获取清单现有记录
        m_records = []
        m_offset = None
        m_url = f"https://api.airtable.com/v0/{MASTER_BASE_ID}/{TARGET_TABLE_NAME}"
        while True:
            r = await client.get(m_url, headers=HEADERS, params={"offset": m_offset} if m_offset else {})
            data = r.json()
            m_records.extend(data.get("records", []))
            m_offset = data.get("offset")
            if not m_offset: break

        # 3. 逐个更新/新增
        for item in current_tables:
            cnt = await get_real_count(client, item["b_id"], item["t_id"])
            match = next((r for r in m_records if r["fields"].get("Table ID") == item["t_id"]), None)
            
            # 严格对齐字段名
            fields = {
                "Base Name": item["b_name"],
                "Table Name": item["t_name"],
                "Table ID": item["t_id"],
                "Record Count": cnt,
                "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            
            if match:
                res = await client.patch(f"{m_url}/{match['id']}", headers=HEADERS, json={"fields": fields})
            else:
                res = await client.post(m_url, headers=HEADERS, json={"fields": fields})
            
            if res.status_code not in [200, 201]:
                print(f"❌ 写入失败 [{item['t_name']}]: {res.text}")
            else:
                print(f"✅ 同步成功: {item['t_name']} = {cnt}")
            await asyncio.sleep(0.25)

        # 4. 清理 (V3.0)
        for r in m_records:
            tid = r["fields"].get("Table ID")
            if tid and tid not in active_ids:
                del_res = await client.delete(f"{m_url}/{r['id']}", headers=HEADERS)
                print(f"🗑️ 清理记录: {r['fields'].get('Table Name')} - {del_res.status_code}")
                await asyncio.sleep(0.25)

        print("✨ 彻底完成！")

if __name__ == "__main__":
    asyncio.run(main())
