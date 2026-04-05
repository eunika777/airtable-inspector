"""
============================================================
项目名称：Airtable 全 Base 资产清单自动同步系统
当前版本：V3.2 (修复版)
更新日期：2026-04-05
主要功能：
1. 【全量同步】扫描账户内所有 Base，精准获取每个表的最新 Record Count。
2. 【唯一匹配】基于 Table ID 匹配逻辑，确保记录唯一，不产生重复。
3. 【URL 补全】自动生成并写入 Table URL，支持一键直达。
4. 【数据保护】仅更新行数、URL 和时间戳，不触碰手动填写的“分类”和“常用”列。
============================================================
"""

import asyncio
import httpx
from datetime import datetime

# ================== 配置区域 ==================
# 你的个人访问令牌 (PAT)
PAT_TOKEN = "patcwx5vX4lDXmmcK.d71c96b0e23cd0763569b78e091b74d195d41832c29f79dc72a82e65e7b74a49"
# 资产清单所在的 Base ID
MASTER_BASE_ID = "applTVvwI1rimUNWX" 
# 资产清单所在的 Table ID
TARGET_TABLE_ID = "tblDpYQ2b9MvB4NXe"

HEADERS = {
    "Authorization": f"Bearer {PAT_TOKEN}",
    "Content-Type": "application/json"
}
MASTER_URL = f"https://api.airtable.com/v0/{MASTER_BASE_ID}/{TARGET_TABLE_ID}"

async def get_real_count(client, base_id, table_id):
    """递归获取某个表的真实总行数"""
    count, offset = 0, None
    while True:
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}?pageSize=100&fields[]="
        try:
            r = await client.get(url, headers=HEADERS, params={"offset": offset} if offset else {})
            if r.status_code != 200: 
                return 0
            data = r.json()
            count += len(data.get("records", []))
            offset = data.get("offset")
            if not offset: break
        except Exception:
            return 0
    return count

async def main():
    async with httpx.AsyncClient(timeout=300.0) as client:
        print(f"🚀 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 启动 V3.2 同步任务...")

        # 1. 获取清单表中现有的所有记录 (建立索引)
        m_records = []
        offset = None
        while True:
            params = {"offset": offset} if offset else {}
            r = await client.get(MASTER_URL, headers=HEADERS, params=params)
            if r.status_code != 200:
                print(f"❌ 无法访问清单表。状态码: {r.status_code}")
                return
            data = r.json()
            m_records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset: break
        
        print(f"📊 当前清单存量: {len(m_records)} 条记录")

        # 2. 获取账户内所有的 Base 列表
        base_res = await client.get("https://api.airtable.com/v0/meta/bases", headers=HEADERS)
        if base_res.status_code != 200:
            print(f"❌ 无法获取 Base 列表")
            return
        all_bases = base_res.json().get("bases", [])

        # 3. 遍历每个 Base 及其下属的所有 Table
        for b in all_bases:
            t_res = await client.get(f"https://api.airtable.com/v0/meta/bases/{b['id']}/tables", headers=HEADERS)
            if t_res.status_code != 200: continue
            
            for t in t_res.json().get("tables", []):
                # 获取真实行数
                cnt = await get_real_count(client, b["id"], t["id"])
                
                # 生成跳转 URL
                table_url = f"https://airtable.com/{b['id']}/{t['id']}"
                
                # 【核心逻辑】根据 Table ID 匹配现有行
                match = next((r for r in m_records if r["fields"].get("Table ID") == t["id"]), None)
                
                payload = {"fields": {
                    "Base Name": b["name"],
                    "Table Name": t["name"],
                    "Table ID": t["id"],
                    "Table URL": table_url, # 👈 修复：写入跳转链接
                    "Record Count": cnt,
                    "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M")
                }}

                if match:
                    # 匹配成功：执行 PATCH 更新 (会补全缺失的 URL)
                    await client.patch(f"{MASTER_URL}/{match['id']}", headers=HEADERS, json=payload)
                    print(f"   ✅ 更新: {t['name']} -> {cnt}")
                else:
                    # 匹配失败：执行 POST 新增
                    await client.post(MASTER_URL, headers=HEADERS, json=payload)
                    print(f"   🆕 新增: {t['name']} -> {cnt}")
                
                await asyncio.sleep(0.2)

        print(f"\n✨ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 同步圆满完成！")

if __name__ == "__main__":
    asyncio.run(main())
