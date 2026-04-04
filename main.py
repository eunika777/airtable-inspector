import asyncio
import httpx
from datetime import datetime

# 配置 (请保持不变)
PAT_TOKEN = "patcwx5vX4lDXmmcK.d71c96b0e23cd0763569b78e091b74d195d41832c29f79dc72a82e65e7b74a49"
MASTER_BASE_ID = "appITVvwl1rimUNWX" 
# 【核心修改】这里直接用 Table ID，不要用中文名，最稳！
TARGET_TABLE_ID = "tblM9WqW1vTzT0O6m" 
HEADERS = {"Authorization": f"Bearer {PAT_TOKEN}", "Content-Type": "application/json"}

# 资产清单表的 API 地址
MASTER_URL = f"https://api.airtable.com/v0/{MASTER_BASE_ID}/{TARGET_TABLE_ID}"

async def get_real_count(client, base_id, table_id):
    count, offset = 0, None
    while True:
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}?pageSize=100&fields[]="
        r = await client.get(url, headers=HEADERS, params={"offset": offset} if offset else {})
        if r.status_code != 200: break
        data = r.json()
        count += len(data.get("records", []))
        offset = data.get("offset")
        if not offset: break
    return count

async def main():
    async with httpx.AsyncClient(timeout=300.0) as client:
        print("🚀 启动全量资产同步 (ID 定位版)...")
        
        # 1. 扫描所有最新 Table
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
        while True:
            r = await client.get(MASTER_URL, headers=HEADERS, params={"offset": m_offset} if m_offset else {})
            if r.status_code != 200: 
                print(f"❌ 访问清单表失败，请检查 Table ID: {TARGET_TABLE_ID}")
                return
            data = r.json()
            m_records.extend(data.get("records", []))
            m_offset = data.get("offset")
            if not m_offset: break

        # 3. 逐个更新/新增
        for item in current_tables:
            cnt = await get_real_count(client, item["b_id"], item["t_id"])
            match = next((r for r in m_records if r["fields"].get("Table ID") == item["t_id"]), None)
            
            payload = {"fields": {
                "Base Name": item["b_name"],
                "Table Name": item["t_name"],
                "Table ID": item["t_id"],
                "Record Count": cnt,
                "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M")
            }}
            
            if match:
                res = await client.patch(f"{MASTER_URL}/{match['id']}", headers=HEADERS, json=payload)
            else:
                res = await client.post(MASTER_URL, headers=HEADERS, json=payload)
            
            if res.status_code in [200, 201]:
                print(f"✅ 同步成功: {item['t_name']} = {cnt}")
            else:
                print(f"❌ 写入失败 [{item['t_name']}]: {res.text}")
            await asyncio.sleep(0.3)

        # 4. 清理 (V3.0)
        for r in m_records:
            if r["fields"].get("Table ID") not in active_ids:
                await client.delete(f"{MASTER_URL}/{r['id']}", headers=HEADERS)
                await asyncio.sleep(0.3)

        print("✨ 任务彻底完成！")

if __name__ == "__main__":
    asyncio.run(main())
