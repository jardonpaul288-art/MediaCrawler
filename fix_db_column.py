# -*- coding: utf-8 -*-
"""临时脚本：添加所有缺失的列"""
import asyncio
from sqlalchemy import text
from sync_sentiment_data import get_mysql_engine

# unified_sentiment 表需要添加的列
UNIFIED_COLUMNS = [
    ("platform_name", "VARCHAR(50) DEFAULT NULL AFTER platform"),
    ("ip_location", "VARCHAR(255) DEFAULT NULL AFTER user_id"),
    ("source_url", "TEXT DEFAULT NULL AFTER ip_location"),
    ("source_keyword", "VARCHAR(255) DEFAULT NULL AFTER source_url"),
]

# negative_sentiment 表需要添加的列
NEGATIVE_COLUMNS = [
    ("platform_name", "VARCHAR(50) DEFAULT NULL AFTER platform"),
    ("ip_location", "TEXT DEFAULT NULL AFTER user_nickname"),
    ("last_modify_ts", "BIGINT DEFAULT NULL AFTER publish_time"),
]

async def add_columns():
    engine = get_mysql_engine()
    async with engine.begin() as conn:
        print("=== 修复 unified_sentiment 表 ===")
        for col_name, col_def in UNIFIED_COLUMNS:
            try:
                await conn.execute(text(f'ALTER TABLE unified_sentiment ADD COLUMN {col_name} {col_def}'))
                print(f'✅ unified_sentiment.{col_name} 列已添加')
            except Exception as e:
                if 'Duplicate column' in str(e):
                    print(f'ℹ️ unified_sentiment.{col_name} 列已存在')
                else:
                    print(f'❌ unified_sentiment.{col_name} 错误: {e}')
        
        print("\n=== 修复 negative_sentiment 表 ===")
        for col_name, col_def in NEGATIVE_COLUMNS:
            try:
                await conn.execute(text(f'ALTER TABLE negative_sentiment ADD COLUMN {col_name} {col_def}'))
                print(f'✅ negative_sentiment.{col_name} 列已添加')
            except Exception as e:
                if 'Duplicate column' in str(e):
                    print(f'ℹ️ negative_sentiment.{col_name} 列已存在')
                else:
                    print(f'❌ negative_sentiment.{col_name} 错误: {e}')

if __name__ == "__main__":
    asyncio.run(add_columns())
