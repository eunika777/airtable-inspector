import asyncio
import httpx
from datetime import datetime

# 配置
PAT_TOKEN = "patcwx5vX4lDXmmcK.d71c96b0e23cd0763569b78e091b74d195d41832c29f79dc72a82e65e7b74a49"
MASTER_BASE_ID = "appITVvwl1rimUNWX" 
TARGET_TABLE_ID = "tblDpYQ2b9MvB4NXe" 
HEADERS = {"Authorization": f"Bearer {PAT_TOKEN}", "Content-Type": "application/json"}

async def get_real_count(client, base_id, table_id):
    count, offset = 0, None
    while True:
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}?pageSize=100&fields[]="
        r = await client.get(url, headers=HEADERS, params={"offset": offset} if offset else {})
        if r.status_code != 200: return 0
        data = r.json()
        count += len(data.get("records", []))
        offset = data.get("offset")
        if not offset: break
    return count

async def main():
    async with httpx.AsyncClient(timeout=300.0) as client:
        print("🔍 正在检查清单表访问权限...")
        master_url = f"https://api.airtable.com/v0/{MASTER_BASE_ID}/{TARGET_TABLE_ID}"
        
        # 测试读取
        test_res = await client.get(master_url, headers=HEADERS)
        print(f"📡 清单表读取状态: {test_res.status_code}")
        if test_res.status_code != 200:
            print(f"❌ 错误详情: {test_res.text}")
            return

        m_records = test_res.json().get("records", [])
        print(f"📊 当前清单已有记录数: {len(m_records)}")

        # 获取所有 Base
        base_res = await client.get("https://api.airtable.com/v0/meta/bases", headers=HEADERS)
        all_bases = base_res.json().get("bases", [])
        print(f"📦 扫描到 Base 总数: {len(all_bases)}")

        for b in all_bases:
            t_res = await client.get(f"https://api.airtable.com/v0/meta/bases/{b['id']}/tables", headers=HEADERS)
            if t_res.status_code != 200: continue
            
            for t in t_res.json().get("tables", []):
                cnt = await get_real_count(client, b["id"], t["id"])
                match = next((r for r in m_records if r["fields"].get("Table ID") == t["id"]), None)
                
                payload = {"fields": {
                    "Base Name": b["name"],
                    "Table Name": t["name"],
                    "Table ID": t["id"],
                    "Record Count": cnt,
                    "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M")
                }}

                if match:
                    res = await client.patch(f"{master_url}/{match['id']}", headers=HEADERS, json=payload)
                else:
                    res = await client.post(master_url, headers=HEADERS, json=payload)
                
                if res.status_code not in [200, 201]:
                    print(f"⚠️ 写入失败 [{t['name']}]: {res.status_code} - {res.text}")
                else:
                    print(f"✅ 写入成功: {t['name']} = {cnt}")
                await asyncio.sleep(0.2)

if __name__ == "__main__":
    asyncio.run(main())
