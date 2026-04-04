import asyncio
import httpx
from datetime import datetime

# 配置信息
PAT_TOKEN = "patcwx5vX4lDXmmcK.d71c96b0e23cd0763569b78e091b74d195d41832c29f79dc72a82e65e7b74a49"
# 根据 image_911173.png 确认你的 Base ID 是 appITVvwl1rimUNWX
MASTER_BASE_ID = "appITVvwl1rimUNWX" 
TARGET_TABLE_NAME = "Base 资产清单"

HEADERS = {"Authorization": f"Bearer {PAT_TOKEN}"}

async def get_total_records(client, base_id, table_id):
    """精准统计行数：利用分页 offset 持续计数"""
    count = 0
    offset = None
    while True:
        # 只请求 ID 字段，最大化减少流量消耗
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}?pageSize=100&fields[]="
        if offset: url += f"&offset={offset}"
        
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code != 200: break
        
        data = resp.json()
        records = data.get("records", [])
        count += len(records)
        offset = data.get("offset")
        if not offset: break
    return count

async def main():
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("🚀 开始扫描 Airtable 资产...")
        
        # 1. 获取所有 Base 列表
        base_res = await client.get("https://api.airtable.com/v0/meta/bases", headers=HEADERS)
        bases = base_res.json().get("bases", [])
        
        # 2. 获取当前总表记录，用于匹配
        master_url = f"https://api.airtable.com/v0/{MASTER_BASE_ID}/{TARGET_TABLE_NAME}"
        master_res = await client.get(master_url, headers=HEADERS)
        existing_records = master_res.json().get("records", [])

        for base_info in bases:
            b_id = base_info["id"]
            print(f"扫描 Base: {base_info['name']}")
            
            table_res = await client.get(f"https://api.airtable.com/v0/meta/bases/{b_id}/tables", headers=HEADERS)
            tables = table_res.json().get("tables", [])
            
            for table in tables:
                t_id = table["id"]
                # 暴力统计所有行数，不受 50 次请求限制
                real_count = await get_total_records(client, b_id, t_id)
                
                # 寻找总表中是否已存在该表记录
                match = next((r for r in existing_records if r["fields"].get("Table ID") == t_id), None)
                
                payload = {
                    "fields": {
                        "Base Name": base_info["name"],
                        "Table Name": table["name"],
                        "Table ID": t_id,
                        "Record Count": real_count,
                        "Table URL": f"https://airtable.com/{b_id}/{t_id}",
                        "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                }

                if match:
                    # 更新旧记录
                    await client.patch(f"{master_url}/{match['id']}", headers=HEADERS, json=payload)
                else:
                    # 创建新记录
                    await client.post(master_url, headers=HEADERS, json=payload)
                
                print(f"   ✅ {table['name']} 统计完成: {real_count} 行")

if __name__ == "__main__":
    asyncio.run(main())
