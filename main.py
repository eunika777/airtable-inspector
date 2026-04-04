import asyncio
import httpx
from datetime import datetime

# 配置
PAT_TOKEN = "patcwx5vX4lDXmmcK.d71c96b0e23cd0763569b78e091b74d195d41832c29f79dc72a82e65e7b74a49"
MASTER_BASE_ID = "applTVvwI1rimUNWX" # 确认是小写 l
TARGET_TABLE_ID = "tblDpYQ2b9MvB4NXe"
HEADERS = {"Authorization": f"Bearer {PAT_TOKEN}", "Content-Type": "application/json"}
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
        print("🔍 正在读取资产清单存量记录...")
        m_records = []
        offset = None
        # 必须全量读取存量，否则会重复写入
        while True:
            params = {"offset": offset} if offset else {}
            r = await client.get(MASTER_URL, headers=HEADERS, params=params)
            if r.status_code != 200: break
            data = r.json()
            m_records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset: break
        
        print(f"📊 当前存量: {len(m_records)} 条")

        # 获取所有 Base 结构
        base_res = await client.get("https://api.airtable.com/v0/meta/bases", headers=HEADERS)
        all_bases = base_res.json().get("bases", [])

        for b in all_bases:
            t_res = await client.get(f"https://api.airtable.com/v0/meta/bases/{b['id']}/tables", headers=HEADERS)
            if t_res.status_code != 200: continue
            
            for t in t_res.json().get("tables", []):
                cnt = await get_real_count(client, b["id"], t["id"])
                
                # 【关键核心】：只认 Table ID，防止重复写入
                match = next((r for r in m_records if r["fields"].get("Table ID") == t["id"]), None)
                
                payload = {"fields": {
                    "Base Name": b["name"],
                    "Table Name": t["name"],
                    "Table ID": t["id"],
                    "Record Count": cnt,
                    "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M")
                }}

                if match:
                    # 匹配到了就更新旧行
                    await client.patch(f"{MASTER_URL}/{match['id']}", headers=HEADERS, json=payload)
                    print(f"🔄 更新: {t['name']} = {cnt}")
                else:
                    # 没匹配到才新增
                    await client.post(MASTER_URL, headers=HEADERS, json=payload)
                    print(f"🆕 新增: {t['name']} = {cnt}")
                
                await asyncio.sleep(0.2)

        print("✨ 同步完成！")

if __name__ == "__main__":
    asyncio.run(main())
