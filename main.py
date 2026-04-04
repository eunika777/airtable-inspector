import asyncio
import httpx
from datetime import datetime

# 配置：严格按照你给的 URL 字符手动输入
PAT_TOKEN = "patcwx5vX4lDXmmcK.d71c96b0e23cd0763569b78e091b74d195d41832c29f79dc72a82e65e7b74a49"
# 注意：这里改成了你 URL 里的原样字符 applTVvwI1rimUNWX
MASTER_BASE_ID = "applTVvwI1rimUNWX" 
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
        print(f"🔍 正在连接 Base: {MASTER_BASE_ID} ...")
        master_url = f"https://api.airtable.com/v0/{MASTER_BASE_ID}/{TARGET_TABLE_ID}"
        
        test_res = await client.get(master_url, headers=HEADERS)
        if test_res.status_code != 200:
            print(f"❌ 访问失败！状态码: {test_res.status_code}")
            print(f"❌ 报错内容: {test_res.text}")
            return # 只要这里不通，脚本就会在几秒内停止

        print(f"✅ 连接成功！正在扫描全量数据...")
        m_records = test_res.json().get("records", [])

        base_res = await client.get("https://api.airtable.com/v0/meta/bases", headers=HEADERS)
        all_bases = base_res.json().get("bases", [])

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
                    await client.patch(f"{master_url}/{match['id']}", headers=HEADERS, json=payload)
                else:
                    await client.post(master_url, headers=HEADERS, json=payload)
                
                print(f"✅ {t['name']} = {cnt}")
                await asyncio.sleep(0.2)

if __name__ == "__main__":
    asyncio.run(main())
