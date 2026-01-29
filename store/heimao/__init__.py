# -*- coding: utf-8 -*-
"""
黑猫投诉数据存储模块 - 参考小红书store实现
"""
import json
from typing import Dict, List

from sqlalchemy import select, update

import config
from base.base_crawler import AbstractStore
from database.db_session import get_session
from database.models import HeimaoComplaint
from tools import utils
from tools.time_util import get_current_timestamp
from tools.async_file_writer import AsyncFileWriter
from var import crawler_type_var, source_keyword_var


class HeimaoStoreFactory:
    """黑猫投诉存储工厂"""
    STORES = {
        "csv": "HeimaoCsvStoreImplement",
        "db": "HeimaoDbStoreImplement",
        "postgres": "HeimaoDbStoreImplement",
        "json": "HeimaoJsonStoreImplement",
    }
    
    @staticmethod
    def create_store() -> AbstractStore:
        store_type = config.SAVE_DATA_OPTION
        if store_type == "csv":
            return HeimaoCsvStoreImplement()
        elif store_type in ("db", "postgres"):
            return HeimaoDbStoreImplement()
        elif store_type == "json":
            return HeimaoJsonStoreImplement()
        else:
            # 默认使用db存储
            return HeimaoDbStoreImplement()


class HeimaoCsvStoreImplement(AbstractStore):
    """CSV存储实现"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.writer = AsyncFileWriter(platform="heimao", crawler_type=crawler_type_var.get())
    
    async def store_content(self, content_item: Dict):
        await self.writer.write_to_csv(item_type="contents", item=content_item)
    
    async def store_comment(self, comment_item: Dict):
        pass  # 黑猫投诉不爬评论
    
    async def store_creator(self, creator_item: Dict):
        pass  # 黑猫投诉不爬创作者


class HeimaoJsonStoreImplement(AbstractStore):
    """JSON存储实现"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.writer = AsyncFileWriter(platform="heimao", crawler_type=crawler_type_var.get())
    
    async def store_content(self, content_item: Dict):
        await self.writer.write_single_item_to_json(item_type="contents", item=content_item)
    
    async def store_comment(self, comment_item: Dict):
        pass  # 黑猫投诉不爬评论
    
    async def store_creator(self, creator_item: Dict):
        pass  # 黑猫投诉不爬创作者


class HeimaoDbStoreImplement(AbstractStore):
    """数据库存储实现"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    async def store_content(self, content_item: Dict):
        """存储投诉到数据库"""
        complaint_id = content_item.get("complaint_id")
        if not complaint_id:
            return
        async with get_session() as session:
            if await self._content_exists(session, complaint_id):
                await self._update_content(session, content_item)
            else:
                await self._add_content(session, content_item)
    
    async def _content_exists(self, session, complaint_id: str) -> bool:
        """检查投诉是否存在"""
        stmt = select(HeimaoComplaint).where(HeimaoComplaint.complaint_id == complaint_id)
        result = await session.execute(stmt)
        return result.first() is not None
    
    async def _add_content(self, session, content_item: Dict):
        """添加新投诉"""
        current_ts = int(get_current_timestamp())
        # 使用从页面获取的真实发布时间（13位时间戳）
        # 如果没有获取到，则使用当前时间
        publish_time = content_item.get("publish_time", 0)
        if not publish_time or publish_time == 0:
            publish_time = current_ts
            
        complaint = HeimaoComplaint(
            complaint_id=content_item.get("complaint_id"),
            title=content_item.get("title", ""),
            content=content_item.get("content", ""),
            user_nickname=content_item.get("user_nickname", ""),
            target_company=content_item.get("company", ""),
            complaint_status=content_item.get("status", ""),
            source_url=content_item.get("url", ""),
            create_time=publish_time,    # 使用真实的发布时间
            add_ts=current_ts,           # 添加到数据库的时间
            last_modify_ts=current_ts,   # 最后修改时间
            source_keyword=content_item.get("source_keyword", "")
        )
        session.add(complaint)
        utils.logger.info(f"[HeimaoDbStore] 新增投诉: {content_item.get('title', '')[:30]}...")
    
    async def _update_content(self, session, content_item: Dict):
        """更新已有投诉"""
        complaint_id = content_item.get("complaint_id")
        current_ts = int(get_current_timestamp())
        update_data = {
            "title": content_item.get("title", ""),
            "content": content_item.get("content", ""),
            "user_nickname": content_item.get("user_nickname", ""),
            "target_company": content_item.get("company", ""),
            "complaint_status": content_item.get("status", ""),
            "source_url": content_item.get("url", ""),
            "last_modify_ts": current_ts,
        }
        stmt = update(HeimaoComplaint).where(HeimaoComplaint.complaint_id == complaint_id).values(**update_data)
        await session.execute(stmt)
        utils.logger.info(f"[HeimaoDbStore] 更新投诉: {content_item.get('title', '')[:30]}...")
    
    async def store_comment(self, comment_item: Dict):
        pass  # 黑猫投诉不爬评论
    
    async def store_creator(self, creator_item: Dict):
        pass  # 黑猫投诉不爬创作者


async def update_heimao_complaint(complaint_data: Dict, keyword: str = "") -> None:
    """
    更新或插入黑猫投诉数据
    
    Args:
        complaint_data: 投诉数据
        keyword: 搜索关键词
    """
    # 生成投诉ID（使用URL的hash作为唯一标识）
    complaint_url = complaint_data.get("url", "")
    # 优先使用API返回的complaint_id，如果没有则使用URL hash
    complaint_id = complaint_data.get("complaint_id")
    if not complaint_id:
        complaint_id = str(hash(complaint_url)) if complaint_url else str(int(get_current_timestamp() * 1000))
    
    local_db_item = {
        "complaint_id": complaint_id,
        "title": complaint_data.get("title", ""),
        "content": complaint_data.get("content", ""),
        "user_nickname": complaint_data.get("user_nickname", ""),
        "company": complaint_data.get("company", ""),
        "status": complaint_data.get("status", ""),
        "url": complaint_url,
        "source_keyword": keyword or source_keyword_var.get(),
        "publish_time": complaint_data.get("publish_time", 0),  # 传递真实发布时间
    }
    
    utils.logger.info(f"[store.heimao.update_heimao_complaint] 保存投诉: {local_db_item.get('title', '')[:30]}...")
    await HeimaoStoreFactory.create_store().store_content(local_db_item)
