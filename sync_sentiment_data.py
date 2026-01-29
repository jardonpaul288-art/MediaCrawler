# -*- coding: utf-8 -*-
"""
天津联通舆情监控 - 数据同步脚本
将各平台的帖子和评论数据同步到统一舆情表 unified_sentiment
特性：
- 每次同步前清空表，确保数据最新
- 包含 IP 归属地信息
- 包含平台中文名称
"""

import sys
import io
import asyncio
import argparse
import time
from typing import Dict, List, Optional
from datetime import datetime

# Force UTF-8 encoding
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select, text, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

from config.db_config import mysql_db_config
from database.models import (
    UnifiedSentiment,
    BilibiliVideo, DouyinAweme, KuaishouVideo, WeiboNote, XhsNote, TiebaNote, ZhihuContent,
    BilibiliVideoComment, DouyinAwemeComment, KuaishouVideoComment, 
    WeiboNoteComment, XhsNoteComment, TiebaComment, ZhihuComment,
    ToutiaoPost, HeimaoComplaint
)


def get_timestamp():
    """获取当前时间戳字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# 平台中文名称
PLATFORM_NAMES = {
    "xhs": "小红书",
    "dy": "抖音",
    "ks": "快手",
    "bili": "B站",
    "wb": "微博",
    "tieba": "贴吧",
    "zhihu": "知乎",
    "toutiao": "今日头条",
    "heimao": "黑猫投诉",
}

# 创建数据库引擎
_engine = None

def get_mysql_engine():
    global _engine
    if _engine is None:
        db_url = f"mysql+asyncmy://{mysql_db_config['user']}:{mysql_db_config['password']}@{mysql_db_config['host']}:{mysql_db_config['port']}/{mysql_db_config['db_name']}"
        _engine = create_async_engine(db_url, echo=False)
    return _engine


@asynccontextmanager
async def get_db_session():
    engine = get_mysql_engine()
    AsyncSessionFactory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = AsyncSessionFactory()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise e
    finally:
        await session.close()


# 平台数据映射配置
PLATFORM_MAPPING = {
    "bili": {
        "post_model": BilibiliVideo,
        "comment_model": BilibiliVideoComment,
        "post_id_field": "video_id",
        "post_title_field": "title",
        "post_content_field": "desc",
        "post_user_field": "nickname",
        "post_user_id_field": "user_id",
        "post_url_field": "video_url",
        "post_time_field": "create_time",
        "post_keyword_field": "source_keyword",
        "post_ip_field": None,
        "comment_id_field": "comment_id",
        "comment_content_field": "content",
        "comment_user_field": "nickname",
        "comment_user_id_field": "user_id",
        "comment_time_field": "create_time",
        "comment_ip_field": None,
    },
    "dy": {
        "post_model": DouyinAweme,
        "comment_model": DouyinAwemeComment,
        "post_id_field": "aweme_id",
        "post_title_field": "title",
        "post_content_field": "desc",
        "post_user_field": "nickname",
        "post_user_id_field": "user_id",
        "post_url_field": "aweme_url",
        "post_time_field": "create_time",
        "post_keyword_field": "source_keyword",
        "post_ip_field": "ip_location",
        "comment_id_field": "comment_id",
        "comment_content_field": "content",
        "comment_user_field": "nickname",
        "comment_user_id_field": "user_id",
        "comment_time_field": "create_time",
        "comment_ip_field": "ip_location",
    },
    "ks": {
        "post_model": KuaishouVideo,
        "comment_model": KuaishouVideoComment,
        "post_id_field": "video_id",
        "post_title_field": "title",
        "post_content_field": "desc",
        "post_user_field": "nickname",
        "post_user_id_field": "user_id",
        "post_url_field": "video_url",
        "post_time_field": "create_time",
        "post_keyword_field": "source_keyword",
        "post_ip_field": None,
        "comment_id_field": "comment_id",
        "comment_content_field": "content",
        "comment_user_field": "nickname",
        "comment_user_id_field": "user_id",
        "comment_time_field": "create_time",
        "comment_ip_field": None,
    },
    "wb": {
        "post_model": WeiboNote,
        "comment_model": WeiboNoteComment,
        "post_id_field": "note_id",
        "post_title_field": None,
        "post_content_field": "content",
        "post_user_field": "nickname",
        "post_user_id_field": "user_id",
        "post_url_field": "note_url",
        "post_time_field": "create_time",
        "post_keyword_field": "source_keyword",
        "post_ip_field": "ip_location",
        "comment_id_field": "comment_id",
        "comment_content_field": "content",
        "comment_user_field": "nickname",
        "comment_user_id_field": "user_id",
        "comment_time_field": "create_time",
        "comment_ip_field": "ip_location",
    },
    "xhs": {
        "post_model": XhsNote,
        "comment_model": XhsNoteComment,
        "post_id_field": "note_id",
        "post_title_field": "title",
        "post_content_field": "desc",
        "post_user_field": "nickname",
        "post_user_id_field": "user_id",
        "post_url_field": "note_url",
        "post_time_field": "time",
        "post_keyword_field": "source_keyword",
        "post_ip_field": "ip_location",
        "comment_id_field": "comment_id",
        "comment_content_field": "content",
        "comment_user_field": "nickname",
        "comment_user_id_field": "user_id",
        "comment_time_field": "create_time",
        "comment_ip_field": "ip_location",
    },
    "tieba": {
        "post_model": TiebaNote,
        "comment_model": TiebaComment,
        "post_id_field": "note_id",
        "post_title_field": "title",
        "post_content_field": "desc",
        "post_user_field": "user_nickname",
        "post_user_id_field": None,
        "post_url_field": "note_url",
        "post_time_field": "add_ts",
        "post_keyword_field": "source_keyword",
        "post_ip_field": "ip_location",
        "comment_id_field": "comment_id",
        "comment_content_field": "content",
        "comment_user_field": "user_nickname",
        "comment_user_id_field": None,
        "comment_time_field": "add_ts",
        "comment_ip_field": "ip_location",
    },
    "zhihu": {
        "post_model": ZhihuContent,
        "comment_model": ZhihuComment,
        "post_id_field": "content_id",
        "post_title_field": "title",
        "post_content_field": "content_text",
        "post_user_field": "user_nickname",
        "post_user_id_field": "user_id",
        "post_url_field": "content_url",
        "post_time_field": "add_ts",
        "post_keyword_field": "source_keyword",
        "post_ip_field": None,
        "comment_id_field": "comment_id",
        "comment_content_field": "content",
        "comment_user_field": "user_nickname",
        "comment_user_id_field": "user_id",
        "comment_time_field": "add_ts",
        "comment_ip_field": "ip_location",
    },
    "toutiao": {
        "post_model": ToutiaoPost,
        "comment_model": None,  # 今日头条不爬取评论
        "post_id_field": "post_id",
        "post_title_field": "title",
        "post_content_field": "content",
        "post_user_field": "source",
        "post_user_id_field": None,
        "post_url_field": "source_url",
        "post_time_field": "create_time",
        "post_keyword_field": "source_keyword",
        "post_ip_field": None,
        "comment_id_field": None,
        "comment_content_field": None,
        "comment_user_field": None,
        "comment_user_id_field": None,
        "comment_time_field": None,
        "comment_ip_field": None,
    },
    "heimao": {
        "post_model": HeimaoComplaint,
        "comment_model": None,  # 黑猫投诉不爬取评论
        "post_id_field": "complaint_id",
        "post_title_field": "title",
        "post_content_field": "content",
        "post_user_field": "user_nickname",
        "post_user_id_field": None,
        "post_url_field": "source_url",
        "post_time_field": "create_time",
        "post_keyword_field": "source_keyword",
        "post_ip_field": None,
        "comment_id_field": None,
        "comment_content_field": None,
        "comment_user_field": None,
        "comment_user_id_field": None,
        "comment_time_field": None,
        "comment_ip_field": None,
    },
}


async def clear_unified_table(session: AsyncSession) -> int:
    """清空统一舆情表"""
    result = await session.execute(delete(UnifiedSentiment))
    return result.rowcount


async def sync_posts(session: AsyncSession, platform: str, mapping: Dict) -> int:
    """同步帖子数据"""
    model = mapping["post_model"]
    platform_name = PLATFORM_NAMES.get(platform, platform)
    synced_count = 0
    
    result = await session.execute(select(model))
    posts = result.scalars().all()
    
    current_ts = int(time.time() * 1000)
    
    for post in posts:
        content_id = str(getattr(post, mapping["post_id_field"], ""))
        if not content_id:
            continue
        
        title = getattr(post, mapping["post_title_field"], "") if mapping["post_title_field"] else ""
        content = getattr(post, mapping["post_content_field"], "") or ""
        user_nickname = getattr(post, mapping["post_user_field"], "") or ""
        user_id = str(getattr(post, mapping["post_user_id_field"], "")) if mapping["post_user_id_field"] else ""
        source_url = getattr(post, mapping["post_url_field"], "") or ""
        source_keyword = getattr(post, mapping["post_keyword_field"], "") or ""
        publish_time = getattr(post, mapping["post_time_field"], 0) or 0
        
        ip_location = ""
        if mapping.get("post_ip_field"):
            ip_location = getattr(post, mapping["post_ip_field"], "") or ""
        
        unified = UnifiedSentiment(
            platform=platform,
            platform_name=platform_name,
            content_type="post",
            content_id=content_id,
            title=title,
            content=content,
            user_nickname=user_nickname,
            user_id=user_id,
            ip_location=ip_location,
            source_url=source_url,
            source_keyword=source_keyword,
            publish_time=publish_time if isinstance(publish_time, int) else current_ts,
            add_ts=current_ts,
            last_modify_ts=current_ts,
            is_analyzed=0
        )
        session.add(unified)
        synced_count += 1
    
    return synced_count


async def sync_comments(session: AsyncSession, platform: str, mapping: Dict) -> int:
    """同步评论数据"""
    model = mapping["comment_model"]
    platform_name = PLATFORM_NAMES.get(platform, platform)
    synced_count = 0
    
    result = await session.execute(select(model))
    comments = result.scalars().all()
    
    current_ts = int(time.time() * 1000)
    
    for comment in comments:
        content_id = str(getattr(comment, mapping["comment_id_field"], ""))
        if not content_id:
            continue
        
        content = getattr(comment, mapping["comment_content_field"], "") or ""
        user_nickname = getattr(comment, mapping["comment_user_field"], "") or ""
        user_id = str(getattr(comment, mapping["comment_user_id_field"], "")) if mapping["comment_user_id_field"] else ""
        publish_time = getattr(comment, mapping["comment_time_field"], 0) or 0
        
        ip_location = ""
        if mapping.get("comment_ip_field"):
            ip_location = getattr(comment, mapping["comment_ip_field"], "") or ""
        
        unified = UnifiedSentiment(
            platform=platform,
            platform_name=platform_name,
            content_type="comment",
            content_id=content_id,
            title="",
            content=content,
            user_nickname=user_nickname,
            user_id=user_id,
            ip_location=ip_location,
            source_url="",
            source_keyword="",
            publish_time=publish_time if isinstance(publish_time, int) else current_ts,
            add_ts=current_ts,
            last_modify_ts=current_ts,
            is_analyzed=0
        )
        session.add(unified)
        synced_count += 1
    
    return synced_count


async def sync_platform_data(session: AsyncSession, platform: str) -> Dict[str, int]:
    """同步单个平台的数据"""
    platform_name = PLATFORM_NAMES.get(platform, platform)
    
    mapping = PLATFORM_MAPPING.get(platform)
    if not mapping:
        return {"posts": 0, "comments": 0}
    
    try:
        posts_count = 0
        if mapping.get("post_model"):
            posts_count = await sync_posts(session, platform, mapping)
            
        comments_count = 0
        if mapping.get("comment_model"):
            comments_count = await sync_comments(session, platform, mapping)
        
        print(f"    ✅ {platform_name}: 帖子 {posts_count} 条, 评论 {comments_count} 条")
        return {"posts": posts_count, "comments": comments_count}
        
    except Exception as e:
        print(f"    ❌ {platform_name} 同步失败: {e}")
        return {"posts": 0, "comments": 0, "error": str(e)}


async def sync_all_data(platforms: List[str] = None, clear_first: bool = True) -> Dict:
    """
    同步所有平台数据
    
    Args:
        platforms: 要同步的平台列表
        clear_first: 是否先清空表
    """
    if platforms is None:
        platforms = list(PLATFORM_MAPPING.keys())
    
    print(f"\n{'='*60}")
    print(f"[{get_timestamp()}] 📢 开始数据同步到统一舆情表")
    print(f"[{get_timestamp()}] 📋 平台: {', '.join([PLATFORM_NAMES.get(p, p) for p in platforms])}")
    print(f"[{get_timestamp()}] 🗑️  清空旧数据: {'是' if clear_first else '否'}")
    print(f"{'='*60}\n")
    
    total_posts = 0
    total_comments = 0
    
    async with get_db_session() as session:
        # 先清空表
        if clear_first:
            deleted_count = await clear_unified_table(session)
            print(f"[{get_timestamp()}] 🗑️  已清空统一舆情表，删除 {deleted_count} 条旧数据")
        
        # 同步各平台数据
        print(f"[{get_timestamp()}] 📥 开始同步各平台数据...")
        for platform in platforms:
            result = await sync_platform_data(session, platform)
            total_posts += result.get("posts", 0)
            total_comments += result.get("comments", 0)
        
        await session.commit()
    
    print(f"\n{'='*60}")
    print(f"[{get_timestamp()}] 📊 同步完成:")
    print(f"[{get_timestamp()}] 📝 总计: 帖子 {total_posts} 条, 评论 {total_comments} 条")
    print(f"{'='*60}\n")
    
    return {
        "total_posts": total_posts,
        "total_comments": total_comments
    }


def parse_args():
    parser = argparse.ArgumentParser(description="天津联通舆情监控 - 数据同步脚本")
    parser.add_argument("--platforms", type=str, default=None, help="要同步的平台，逗号分隔")
    parser.add_argument("--no-clear", action="store_true", help="不清空表，追加数据")
    return parser.parse_args()


async def main():
    args = parse_args()
    
    platforms = None
    if args.platforms:
        platforms = [p.strip() for p in args.platforms.split(",")]
    
    await sync_all_data(platforms, clear_first=not args.no_clear)


if __name__ == "__main__":
    asyncio.run(main())
