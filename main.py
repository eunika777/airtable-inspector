"""
============================================================
项目名称：Airtable 全 Base 资产清单自动同步系统
当前版本：V4.0
更新日期：2026-10-04
主要功能：
1. 扫描账户内所有 Base，精准获取每个表的最新 Record Count。
2. 基于 Table ID 匹配逻辑，确保记录唯一，不产生重复。
3. 自动生成并写入 Table URL，支持一键直达。
4. 删除 503 中已不存在的表的残留行（此前版本只增不删）。
5. 仅更新行数、URL 和时间戳，不触碰手动填写的"分类"和"常用"列。
6. PAT 从环境变量 AIRTABLE_PAT 读取，不再硬编码在代码里。
请在仓库 Settings → Secrets and variables → Actions 中配置 AIRTABLE_PAT。
============================================================
"""

import asyncio
import os
import sys
import httpx
from datetime import datetime

# ================== 配置区域 ==================
# 个人访问令牌 (PAT) 从环境变量读取，请勿硬编码提交到仓库
PAT_TOKEN = os.environ.get("AIRTABLE_PAT", "").strip()
if not PAT_TOKEN:
    print("❌ 未找到环境变量 AIRTABLE_PAT，请在 GitHub Secrets 中配置后重试。")
    sys.exit(1)
# 资产清单所在的 Base ID
MASTER_BASE_ID = "applTVvwI1rimUNWX"
# 资产清单所在的 Table ID
TARGET_TABLE_ID = "tblDpYQ2b9MvB4NXe"

HEADERS = {
    "Authorization": f"Bearer {PAT_TOKEN}",
    "Content-Type": "application/json"
}
MASTER_URL = f"https://api.airtable.com/v0/{MASTER_BASE_ID}/{TARGET_TABLE_ID}"


def log_run(msg: str):
    """把运行摘要追加到 sync.log（供 keepalive 提交保活用）。"""
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
    with open("sync.log", "a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="")


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
            if not offset:
                break
        except Exception:
            return 0
    return count


async def main():
    async with httpx.AsyncClient(timeout=300.0) as client:
        log_run("🚀 启动 V4.0 同步任务...")

        # 1. 获取清单表中现有的所有记录 (建立索引)
        m_records = []
        offset = None
        while True:
            params = {"offset": offset} if offset else {}
            r = await client.get(MASTER_URL, headers=HEADERS, params=params)
            if r.status_code != 200:
                log_run(f"❌ 无法访问清单表。状态码: {r.status_code}")
                return
            data = r.json()
            m_records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset:
                break

        log_run(f"📊 当前清单存量: {len(m_records)} 条记录")

        # 2. 获取账户内所有的 Base 列表
        base_res = await client.get("https://api.airtable.com/v0/meta/bases", headers=HEADERS)
        if base_res.status_code != 200:
            log_run("❌ 无法获取 Base 列表")
            return
        all_bases = base_res.json().get("bases", [])

        # 3. 遍历每个 Base 及其下属的所有 Table
        live_table_ids = set()
        n_new, n_upd = 0, 0
        for b in all_bases:
            t_res = await client.get(f"https://api.airtable.com/v0/meta/bases/{b['id']}/tables", headers=HEADERS)
            if t_res.status_code != 200:
                continue

            for t in t_res.json().get("tables", []):
                live_table_ids.add(t["id"])
                # 获取真实行数
                cnt = await get_real_count(client, b["id"], t["id"])

                # 生成跳转 URL
                table_url = f"https://airtable.com/{b['id']}/{t['id']}"

                # 根据 Table ID 匹配现有行
                match = next((r for r in m_records if r["fields"].get("Table ID") == t["id"]), None)

                payload = {"fields": {
                    "Base Name": b["name"],
                    "Table Name": t["name"],
                    "Table ID": t["id"],
                    "Table URL": table_url,
                    "Record Count": cnt,
                    "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M")
                }}

                if match:
                    # 匹配成功：执行 PATCH 更新 (会补全缺失的 URL)
                    await client.patch(f"{MASTER_URL}/{match['id']}", headers=HEADERS, json=payload)
                    n_upd += 1
                    print(f" ✅ 更新: {t['name']} -> {cnt}")
                else:
                    # 匹配失败：执行 POST 新增
                    await client.post(MASTER_URL, headers=HEADERS, json=payload)
                    n_new += 1
                    print(f" 🆕 新增: {t['name']} -> {cnt}")

        # 4. 删除 503 中已不存在的表的残留行
        n_del = 0
        for r in m_records:
            tid = r["fields"].get("Table ID")
            if tid and tid not in live_table_ids:
                d_res = await client.delete(f"{MASTER_URL}/{r['id']}", headers=HEADERS)
                if d_res.status_code == 200:
                    n_del += 1
                    print(f" 🗑️ 删除僵尸行: {r['fields'].get('Table Name')} ({tid})")
                else:
                    print(f" ⚠️ 删除失败: {r['fields'].get('Table Name')} 状态码 {d_res.status_code}")

        log_run(f"🏁 同步完成：新增 {n_new}，更新 {n_upd}，删除僵尸 {n_del}，当前实际 {len(live_table_ids)} 张表")


if __name__ == "__main__":
    asyncio.run(main())
