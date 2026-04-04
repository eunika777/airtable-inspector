import asyncio
import httpx
from datetime import datetime

# 配置：根据你提供的 URL 精准对齐
PAT_TOKEN = "patcwx5vX4lDXmmcK.d71c96b0e23cd0763569b78e091b74d195d41832c29f79dc72a82e65e7b74a49"
MASTER_BASE_ID = "appITVvwl1rimUNWX" 
# 关键修改：使用你链接中真实的 Table ID
TARGET_TABLE_ID = "tblDpYQ2b9MvB4NXe" 
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
        print("🚀 启动全量资产同步 (准确 ID 版)...")
        
        # 1. 扫描所有 Base 及其 Table 结构
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
                print(f"❌ 访问清单表失败: {r.text}")
                return
            data = r.json()
            m_records.extend(data.get("records", []))
            m_offset = data.get("offset")
            if not m_offset: break

        # 3. 逐个更新/新增 (复刻 JS 逻辑，即数即写)
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
                await client.patch(f"{MASTER_URL}/{match['id']}", headers=HEADERS, json=payload)
            else:
                await client.post(MASTER_URL, headers=HEADERS, json=payload)
            
            print(f"✅ 同步成功: {item['t_name']} = {cnt}")
            await asyncio.sleep(0.3)

        # 4. 清理 (V3.0：删除已不存在的表)
        for r in m_records:
            if r["fields"].get("Table ID") not in active_ids:
                await client.delete(f"{MASTER_URL}/{r['id']}", headers=HEADERS)
                await asyncio.sleep(0.3)

        print("✨ 任务彻底完成！")

if __name__ == "__main__":
    asyncio.run(main())
