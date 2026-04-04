import asyncio
import httpx
from datetime import datetime
from urllib.parse import quote

# 配置
PAT_TOKEN = "patcwx5vX4lDXmmcK.d71c96b0e23cd0763569b78e091b74d195d41832c29f79dc72a82e65e7b74a49"
MASTER_BASE_ID = "appITVvwl1rimUNWX"
TARGET_TABLE_NAME = "Base 资产清单"

# ✅ 关键：表名编码
TABLE_NAME_ENCODED = quote(TARGET_TABLE_NAME)

HEADERS = {
    "Authorization": f"Bearer {PAT_TOKEN}",
    "Content-Type": "application/json"
}

async def main():
    async with httpx.AsyncClient(timeout=300.0) as client:

        # 获取所有 Base
        base_res = await client.get(
            "https://api.airtable.com/v0/meta/bases",
            headers=HEADERS
        )
        base_data = base_res.json().get("bases", [])

        # ✅ 正确 URL
        master_url = f"https://api.airtable.com/v0/{MASTER_BASE_ID}/{TABLE_NAME_ENCODED}"

        # 获取已有记录
        m_res = await client.get(master_url, headers=HEADERS)
        m_records = m_res.json().get("records", [])

        active_table_ids = []

        for b_info in base_data:

            t_res = await client.get(
                f"https://api.airtable.com/v0/meta/bases/{b_info['id']}/tables",
                headers=HEADERS
            )
            if not t_res.is_success:
                continue

            tables = t_res.json().get("tables", [])

            for t_info in tables:
                active_table_ids.append(t_info["id"])

                # 统计行数（分页）
                count = 0
                offset = None

                while True:
                    url = f"https://api.airtable.com/v0/{b_info['id']}/{t_info['id']}?pageSize=100"
                    params = {"offset": offset} if offset else {}

                    r = await client.get(url, headers=HEADERS, params=params)
                    if not r.is_success:
                        break

                    data = r.json()
                    count += len(data.get("records", []))
                    offset = data.get("offset")

                    if not offset:
                        break

                # 查找是否存在
                match = next(
                    (r for r in m_records if r["fields"].get("Table ID") == t_info["id"]),
                    None
                )

                payload = {
                    "fields": {
                        "Base Name": b_info["name"],
                        "Table Name": t_info["name"],
                        "Table ID": t_info["id"],
                        "Table URL": f"https://airtable.com/{b_info['id']}/{t_info['id']}",
                        "Record Count": count,
                        "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                }

                if match:
                    await client.patch(
                        f"{master_url}/{match['id']}",
                        headers=HEADERS,
                        json=payload
                    )
                else:
                    await client.post(
                        master_url,
                        headers=HEADERS,
                        json=payload
                    )

                print(f"✅ 完成: {t_info['name']} = {count}")
                await asyncio.sleep(0.2)

        # 删除已不存在的表
        for r in m_records:
            if r["fields"].get("Table ID") not in active_table_ids:
                await client.delete(
                    f"{master_url}/{r['id']}",
                    headers=HEADERS
                )

if __name__ == "__main__":
    asyncio.run(main())
