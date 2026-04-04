import asyncio
import httpx
from datetime import datetime

# 配置
PAT_TOKEN = "patcwx5vX4lDXmmcK.d71c96b0e23cd0763569b78e091b74d195d41832c29f79dc72a82e65e7b74a49"
MASTER_BASE_ID = "appITVvwl1rimUNWX" 
TARGET_TABLE_NAME = "Base 资产清单"
HEADERS = {"Authorization": f"Bearer {PAT_TOKEN}"}

# 严格复刻 ChatGPT 的分页计数逻辑
async def get_real_count(client, base_id, table_id):
    count = 0
    offset = None
    page = 0
    while True:
        # 仅请求 ID 字段以提升速度，pageSize=100
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}?pageSize=100"
        if offset: url += f"&offset={offset}"
        
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code != 200:
            print(f"   ❌ 获取失败: {table_id}")
            break
            
        data = resp.json()
        records = data.get("records", [])
        batch = len(records)
        count += batch
        
        offset = data.get("offset")
        page += 1
        # 如果需要调试，可以取消下面这行的注释查看日志
        # print(f"      第{page}页 +{batch}（累计{count}）")
        
        if not offset:
            break
    return count

async def main():
    # 增加超时限制，防止大表卡死
    async with httpx.AsyncClient(timeout=300.0) as client:
        print("🚀 开始全量真实计数 (复刻 ChatGPT 逻辑)...")
        
        # 1. 获取所有 Base
        base_res = await client.get("https://api.airtable.com/v0/meta/bases", headers=HEADERS)
        all_bases = base_res.json().get("bases", [])
        
        current_table_ids = []
        sync_list = []

        # 2. 扫描所有 Table 并记录 ID
        for b in all_bases:
            t_res = await client.get(f"https://api.airtable.com/v0/meta/bases/{b['id']}/tables", headers=HEADERS)
            if t_res.status_code != 200: continue
            for t in t_res.json().get("tables", []):
                current_table_ids.append(t['id'])
                sync_list.append({"b_id": b["id"], "b_name": b["name"], "t_id": t["id"], "t_name": t["name"]})

        # 3. 获取目标清单现有记录 (用于增量更新和删除)
        m_url = f"https://api.airtable.com/v0/{MASTER_BASE_ID}/{TARGET_TABLE_NAME}"
        m_records = []
        m_offset = None
        while True:
            r = await client.get(m_url, headers=HEADERS, params={"offset": m_offset} if m_offset else {})
            d = r.json()
            m_records.extend(d.get("records", []))
            m_offset = d.get("offset")
            if not m_offset: break

        # 4. 执行同步 (计数 + 写入)
        print(f"📊 准备同步 {len(sync_list)} 个表...")
        for item in sync_list:
            cnt = await get_real_count(client, item["b_id"], item["t_id"])
            
            # 查找是否存在
            match = next((r for r in m_records if r["fields"].get("Table ID") == item["t_id"]), None)
            
            payload = {
                "fields": {
                    "Base Name": item["b_name"],
                    "Table Name": item["t_name"],
                    "Table ID": item["t_id"],
                    "Table URL": f"https://airtable.com/{item['b_id']}/{item['t_id']}",
                    "Record Count": cnt,
                    "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
            }
            
            if match:
                await client.patch(f"{m_url}/{match['id']}", headers=HEADERS, json=payload)
            else:
                await client.post(m_url, headers=HEADERS, json=payload)
            print(f"   ✅ 完成: {item['t_name']} = {cnt}")

        # 5. 物理清理 (V3.0：自动删除已不存在的表记录)
        print("🧹 开始清理已删除的表记录...")
        for r in m_records:
            if r["fields"].get("Table ID") not in current_table_ids:
                await client.delete(f"{m_url}/{r['id']}", headers=HEADERS)
        
        print("✨ 全部完成（真实行数）")

if __name__ == "__main__":
    asyncio.run(main())
