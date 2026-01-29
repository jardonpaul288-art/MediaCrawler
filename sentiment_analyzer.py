# -*- coding: utf-8 -*-
"""
天津联通舆情监控 - 情感分析脚本
功能：
- 调用公司内部大模型 API 进行情感分析
- 检查IP归属地（天津）扩大覆盖范围
- 筛选负面舆情，宁多勿少
"""

import sys
import io
import asyncio
import argparse
import json
import time
import re
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime

# Force UTF-8 encoding
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

from config.db_config import mysql_db_config
from database.models import UnifiedSentiment, NegativeSentiment


def get_timestamp():
    """获取当前时间戳字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_timestamp(ts) -> int:
    """
    统一时间戳格式为毫秒级
    - 10位数字：秒级时间戳，转换为毫秒
    - 13位数字：毫秒级时间戳，直接返回
    - 其他：返回当前时间戳
    """
    if ts is None:
        return int(time.time() * 1000)
    
    try:
        ts = int(ts)
        if ts < 0:
            return int(time.time() * 1000)
        
        # 10位数字是秒级时间戳
        if ts < 10000000000:
            return ts * 1000
        # 13位数字是毫秒级时间戳
        elif ts < 10000000000000:
            return ts
        else:
            # 异常大的数字，返回当前时间
            return int(time.time() * 1000)
    except (ValueError, TypeError):
        return int(time.time() * 1000)


# API 配置
API_URL = "https://maas-api.ai-yuanjing.com/openapi/compatible-mode/v1/chat/completions"
API_KEY = "sk-b1632e634f2b4a36a41e52927e12d5d4"
MODEL_NAME = "qwen3-235b-a22b"

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

# 天津联通相关关键词 - 用于初步筛选
TIANJIN_KEYWORDS = ["天津", "津", "塘沽", "滨海", "河西", "河东", "南开", "和平", "红桥", "河北", "东丽", "西青", "津南", "北辰", "武清", "宝坻", "静海", "宁河", "蓟州"]
UNICOM_KEYWORDS = ["联通", "沃派", "中国联通", "宽带", "冰淇淋套餐"]

# 创建直接连接MySQL的数据库引擎
_engine = None

def get_mysql_engine():
    """获取MySQL数据库引擎"""
    global _engine
    if _engine is None:
        db_url = f"mysql+asyncmy://{mysql_db_config['user']}:{mysql_db_config['password']}@{mysql_db_config['host']}:{mysql_db_config['port']}/{mysql_db_config['db_name']}"
        _engine = create_async_engine(db_url, echo=False)
    return _engine


@asynccontextmanager
async def get_db_session():
    """获取数据库会话 - 直接连接MySQL"""
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


def is_tianjin_related(content: str, title: str = "", ip_location: str = "", user_nickname: str = "") -> tuple:
    """
    检查内容是否与天津相关
    
    Args:
        content: 内容正文
        title: 标题
        ip_location: IP归属地
        user_nickname: 用户昵称
        
    Returns:
        tuple: (是否相关, 原因)
    """
    full_text = f"{title} {content} {user_nickname}".lower()
    
    # 检查IP归属地是否为天津
    if ip_location and "天津" in ip_location:
        return True, "IP归属地为天津"
    
    # 检查内容中是否包含天津相关关键词
    for kw in TIANJIN_KEYWORDS:
        if kw in full_text:
            return True, f"内容包含天津相关词'{kw}'"
    
    return False, ""


def is_unicom_related(content: str, title: str = "") -> tuple:
    """
    检查内容是否与联通相关
    
    Args:
        content: 内容正文
        title: 标题
        
    Returns:
        tuple: (是否相关, 原因)
    """
    full_text = f"{title} {content}".lower()
    
    for kw in UNICOM_KEYWORDS:
        if kw.lower() in full_text:
            return True, f"内容包含联通相关词'{kw}'"
    
    return False, ""


def pre_filter_content(content: str, title: str = "", ip_location: str = "") -> tuple:
    """
    预筛选：判断内容是否可能是天津联通相关舆情
    
    策略：宁多勿少
    - 如果明确提到"天津联通"，肯定相关
    - 如果提到联通 + (天津IP 或 天津关键词)，也算相关
    - 如果只提到联通，但IP是天津，也算相关
    
    Returns:
        tuple: (是否需要分析, 预判原因)
    """
    full_text = f"{title} {content}"
    
    # 明确提到天津联通
    if "天津联通" in full_text or "联通天津" in full_text:
        return True, "明确提到天津联通"
    
    # 检查联通相关
    unicom_related, unicom_reason = is_unicom_related(content, title)
    if not unicom_related:
        return False, "与联通无关"
    
    # 检查天津相关
    tianjin_related, tianjin_reason = is_tianjin_related(content, title, ip_location)
    if tianjin_related:
        return True, f"联通相关 + {tianjin_reason}"
    
    # 即使没有明确天津关键词，但提到联通的也保留（宁多勿少）
    # 后续由大模型进一步判断
    return True, "提到联通，保留待分析"


async def call_llm_api(content: str, title: str = "", ip_location: str = "") -> Dict:
    """
    调用大模型 API 进行情感分析
    
    Args:
        content: 待分析的内容
        title: 标题（可选）
        ip_location: IP归属地
        
    Returns:
        Dict: 包含情感分析结果
    """
    # 构建提示词
    text_to_analyze = f"标题：{title}\n内容：{content}" if title else content
    if ip_location:
        text_to_analyze += f"\n发帖人IP归属地：{ip_location}"
    
    # 限制内容长度
    if len(text_to_analyze) > 2000:
        text_to_analyze = text_to_analyze[:2000] + "..."
    
    prompt = f"""请分析以下内容是否属于"天津联通"的负面舆情。

分析内容：
{text_to_analyze}

请严格按照以下JSON格式返回结果，不要有任何其他内容：
{{"is_tianjin_unicom": true或false, "is_negative": true或false, "score": "正面"或"中性"或"负面", "reason": "判定原因（简要说明）"}}

【重要】判定标准：

第一步：判断是否与"天津联通"相关（必须满足以下条件之一）：
1. 内容明确提到"天津联通"或"联通天津"
2. 内容涉及联通相关业务（宽带、套餐、服务等）+ 发帖人IP归属地为"天津"
3. 内容涉及联通相关业务 + 内容中明确提到天津地名（如塘沽、滨海、河西等）

【特别注意】以下情况不属于"天津联通"相关：
- 发帖人IP不是天津，且内容未提及天津地名
- 只提到"中国联通"但发帖人在其他省市（如广东、四川、河南等）
- 提到的是其他省市的联通问题
- 官方客服的通用回复模板

第二步：如果确定与天津联通相关，再判断情感：
- 负面：投诉、抱怨、批评、不满、差评、骗人、乱扣费、欺诈等
- 正面：表扬、感谢、好评、推荐、服务好等  
- 中性：客观描述、咨询、讨论、无明显情感倾向

请直接返回JSON，不要有任何解释或前缀："""

    headers = {
        "Content-Type": "application/json",
        "X-LLM-Application-Tag": "proxyai",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500,
        "temperature": 0.1,
        "stream": False
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, headers=headers, json=payload, timeout=60) as response:
                if response.status != 200:
                    error_text = await response.text()
                    return {
                        "is_tianjin_unicom": False,
                        "is_negative": False,
                        "score": "未知",
                        "reason": f"API调用失败: {response.status} - {error_text[:200]}",
                        "error": True
                    }
                
                result = await response.json()
                
                # 解析返回结果
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0].get("message", {}).get("content", "")
                    
                    # 尝试解析JSON
                    try:
                        # 清理可能的markdown标记
                        content = content.strip()
                        if content.startswith("```json"):
                            content = content[7:]
                        if content.startswith("```"):
                            content = content[3:]
                        if content.endswith("```"):
                            content = content[:-3]
                        content = content.strip()
                        
                        parsed = json.loads(content)
                        return {
                            "is_tianjin_unicom": parsed.get("is_tianjin_unicom", True),  # 默认为True，宁多勿少
                            "is_negative": parsed.get("is_negative", False),
                            "score": parsed.get("score", "未知"),
                            "reason": parsed.get("reason", ""),
                            "error": False
                        }
                    except json.JSONDecodeError:
                        # 如果无法解析JSON，尝试从文本中提取信息
                        is_negative = "负面" in content or "is_negative\": true" in content.lower()
                        return {
                            "is_tianjin_unicom": True,  # 默认为True
                            "is_negative": is_negative,
                            "score": "负面" if is_negative else "中性",
                            "reason": content[:200],
                            "error": False
                        }
                
                return {
                    "is_tianjin_unicom": False,
                    "is_negative": False,
                    "score": "未知",
                    "reason": "API返回格式异常",
                    "error": True
                }
                
    except asyncio.TimeoutError:
        return {
            "is_tianjin_unicom": False,
            "is_negative": False,
            "score": "未知",
            "reason": "API调用超时",
            "error": True
        }
    except Exception as e:
        return {
            "is_tianjin_unicom": False,
            "is_negative": False,
            "score": "未知",
            "reason": f"API调用异常: {str(e)}",
            "error": True
        }


async def test_api_connection() -> bool:
    """测试 API 连接"""
    print(f"[{get_timestamp()}] 🔗 测试大模型 API 连接...")
    
    result = await call_llm_api("这是一个测试内容，天津联通的服务很差，网络经常断。", ip_location="天津")
    
    if result.get("error"):
        print(f"[{get_timestamp()}] ❌ API 连接测试失败: {result.get('reason')}")
        return False
    
    print(f"[{get_timestamp()}] ✅ API 连接测试成功")
    print(f"    天津联通相关: {result.get('is_tianjin_unicom')}")
    print(f"    情感: {result.get('score')}")
    print(f"    原因: {result.get('reason')[:50]}...")
    return True


async def analyze_single_content(unified_id: int, content: str, title: str = "", ip_location: str = "", max_retries: int = 3) -> Dict:
    """分析单条内容（带重试机制）"""
    last_error = None
    for attempt in range(max_retries):
        result = await call_llm_api(content, title, ip_location)
        if not result.get("error"):
            result["unified_id"] = unified_id
            return result
        last_error = result
        if attempt < max_retries - 1:
            await asyncio.sleep(1)  # 等待1秒后重试
    
    # 所有重试都失败
    last_error["unified_id"] = unified_id
    return last_error


async def process_unanalyzed_content(limit: int = 100, batch_size: int = 5) -> Dict:
    """
    处理未分析的内容
    
    Args:
        limit: 最多处理的条数
        batch_size: 每批处理条数（控制API调用频率）
        
    Returns:
        Dict: 处理结果统计
    """
    print(f"\n{'='*60}")
    print(f"[{get_timestamp()}] 📢 开始情感分析")
    print(f"[{get_timestamp()}] 📋 最大处理数量: {limit} 条")
    print(f"[{get_timestamp()}] 📋 策略: 严格筛选天津联通相关内容")
    print(f"{'='*60}\n")
    
    stats = {
        "total_processed": 0,
        "tianjin_unicom_count": 0,
        "negative_count": 0,
        "positive_count": 0,
        "neutral_count": 0,
        "not_related_count": 0,
        "error_count": 0,
        "retry_count": 0
    }
    
    # 失败记录队列，用于最后重试
    failed_records = []
    # 负面舆情收集列表，用于按publish_time排序后批量插入
    negative_items = []
    
    async with get_db_session() as session:
        # 1. 首先删除一个月前的负面舆情数据
        one_month_ago_ms = int((time.time() - 30 * 24 * 3600) * 1000)
        delete_result = await session.execute(
            text("DELETE FROM negative_sentiment WHERE publish_time < :cutoff"),
            {"cutoff": one_month_ago_ms}
        )
        deleted_count = delete_result.rowcount
        if deleted_count > 0:
            print(f"[{get_timestamp()}] 🗑️  已删除 {deleted_count} 条一个月前的负面舆情数据")
            await session.commit()
        
        # 2. 获取未分析的内容
        result = await session.execute(
            select(UnifiedSentiment).where(
                UnifiedSentiment.is_analyzed == 0
            ).limit(limit)
        )
        records = result.scalars().all()
        
        if not records:
            print(f"[{get_timestamp()}] ℹ️  没有待分析的内容")
            return stats
        
        print(f"[{get_timestamp()}] 📝 待分析内容: {len(records)} 条")
        
        current_ts = int(time.time() * 1000)
        
        # 3. 分批处理
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            print(f"[{get_timestamp()}] 🔄 处理第 {i+1}-{min(i+batch_size, len(records))} 条...")
            
            # 预筛选
            filtered_batch = []
            for record in batch:
                ip_location = record.ip_location or ""
                
                should_analyze, pre_reason = pre_filter_content(
                    record.content or "", 
                    record.title or "",
                    ip_location
                )
                
                if should_analyze:
                    filtered_batch.append((record, ip_location))
                else:
                    # 标记为已分析但不相关
                    await session.execute(
                        update(UnifiedSentiment)
                        .where(UnifiedSentiment.id == record.id)
                        .values(is_analyzed=1, last_modify_ts=current_ts)
                    )
                    stats["total_processed"] += 1
                    stats["not_related_count"] += 1

            
            if not filtered_batch:
                continue
            
            # 并行发送API请求（不重试，失败的放入队列）
            tasks = [
                call_llm_api(
                    record.content or "",
                    record.title or "",
                    ip_location
                )
                for record, ip_location in filtered_batch
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            for j, result in enumerate(results):
                record, ip_location = filtered_batch[j]
                stats["total_processed"] += 1
                
                # 检查是否需要重试
                if isinstance(result, Exception) or result.get("error"):
                    # 加入失败队列，稍后重试
                    failed_records.append((record, ip_location))
                    continue
                
                # 更新分析状态
                await session.execute(
                    update(UnifiedSentiment)
                    .where(UnifiedSentiment.id == record.id)
                    .values(is_analyzed=1, last_modify_ts=current_ts)
                )
                
                # 检查是否与天津联通相关
                if not result.get("is_tianjin_unicom", True):
                    stats["not_related_count"] += 1
                    continue
                
                stats["tianjin_unicom_count"] += 1
                
                # 统计情感类型
                score = result.get("score", "中性")
                if score == "负面":
                    stats["negative_count"] += 1
                elif score == "正面":
                    stats["positive_count"] += 1
                else:
                    stats["neutral_count"] += 1
                
                # 如果是负面舆情，收集到列表中
                if result.get("is_negative"):
                    platform_name = PLATFORM_NAMES.get(record.platform, record.platform)
                    content_type_cn = "帖子" if record.content_type == "post" else "评论"
                    print(f"    🔴 ID {record.id} ({platform_name}): 负面 - {result.get('reason', '')[:40]}...")
                    
                    # 归一化时间戳
                    normalized_publish_time = normalize_timestamp(record.publish_time)
                    normalized_last_modify_ts = normalize_timestamp(record.last_modify_ts)
                    
                    negative_items.append({
                        "unified_id": record.id,
                        "platform": record.platform,
                        "platform_name": platform_name,
                        "content_type": content_type_cn,
                        "title": record.title,
                        "content": record.content,
                        "user_nickname": record.user_nickname,
                        "ip_location": record.ip_location or "",
                        "source_url": record.source_url,
                        "publish_time": normalized_publish_time,
                        "last_modify_ts": normalized_last_modify_ts,
                        "sentiment_score": score,
                        "sentiment_reason": result.get("reason", ""),
                        "add_ts": current_ts
                    })
            
            # 提交当前批次
            await session.commit()
            
            # 控制API调用频率
            if i + batch_size < len(records):
                await asyncio.sleep(0.5)
        
        # 4. 重试失败的记录（只重试一次）
        if failed_records:
            print(f"\n[{get_timestamp()}] 🔄 重试 {len(failed_records)} 条失败记录...")
            
            for record, ip_location in failed_records:
                stats["retry_count"] += 1
                result = await call_llm_api(record.content or "", record.title or "", ip_location)
                
                if isinstance(result, Exception) or result.get("error"):
                    stats["error_count"] += 1
                    print(f"    ❌ ID {record.id}: 重试失败 - {str(result)[:50] if isinstance(result, Exception) else result.get('reason', '')[:50]}")
                    continue
                
                # 更新分析状态
                await session.execute(
                    update(UnifiedSentiment)
                    .where(UnifiedSentiment.id == record.id)
                    .values(is_analyzed=1, last_modify_ts=current_ts)
                )
                
                if not result.get("is_tianjin_unicom", True):
                    stats["not_related_count"] += 1
                    continue
                
                stats["tianjin_unicom_count"] += 1
                score = result.get("score", "中性")
                if score == "负面":
                    stats["negative_count"] += 1
                elif score == "正面":
                    stats["positive_count"] += 1
                else:
                    stats["neutral_count"] += 1
                
                if result.get("is_negative"):
                    platform_name = PLATFORM_NAMES.get(record.platform, record.platform)
                    content_type_cn = "帖子" if record.content_type == "post" else "评论"
                    print(f"    🔴 ID {record.id} ({platform_name}): 负面 - {result.get('reason', '')[:40]}...")
                    
                    normalized_publish_time = normalize_timestamp(record.publish_time)
                    normalized_last_modify_ts = normalize_timestamp(record.last_modify_ts)
                    
                    negative_items.append({
                        "unified_id": record.id,
                        "platform": record.platform,
                        "platform_name": platform_name,
                        "content_type": content_type_cn,
                        "title": record.title,
                        "content": record.content,
                        "user_nickname": record.user_nickname,
                        "ip_location": record.ip_location or "",
                        "source_url": record.source_url,
                        "publish_time": normalized_publish_time,
                        "last_modify_ts": normalized_last_modify_ts,
                        "sentiment_score": score,
                        "sentiment_reason": result.get("reason", ""),
                        "add_ts": current_ts
                    })
            
            await session.commit()
        
        # 5. 按publish_time降序排序后批量插入负面舆情
        if negative_items:
            # 按publish_time降序排序
            negative_items.sort(key=lambda x: x["publish_time"], reverse=True)
            
            print(f"\n[{get_timestamp()}] 📥 批量插入 {len(negative_items)} 条负面舆情（按时间降序）...")
            
            for item in negative_items:
                negative = NegativeSentiment(
                    unified_id=item["unified_id"],
                    platform=item["platform"],
                    platform_name=item["platform_name"],
                    content_type=item["content_type"],
                    title=item["title"],
                    content=item["content"],
                    user_nickname=item["user_nickname"],
                    ip_location=item["ip_location"],
                    source_url=item["source_url"],
                    publish_time=item["publish_time"],
                    last_modify_ts=item["last_modify_ts"],
                    sentiment_score=item["sentiment_score"],
                    sentiment_reason=item["sentiment_reason"],
                    add_ts=item["add_ts"]
                )
                session.add(negative)
            
            await session.commit()
    
    # 打印结果汇总
    print(f"\n{'='*60}")
    print(f"[{get_timestamp()}] 📊 情感分析结果汇总:")
    print(f"    ✅ 处理总数: {stats['total_processed']}")
    print(f"    📍 天津联通相关: {stats['tianjin_unicom_count']}")
    print(f"    🔴 负面: {stats['negative_count']}")
    print(f"    🟢 正面: {stats['positive_count']}")
    print(f"    ⚪ 中性: {stats['neutral_count']}")
    print(f"    ⚫ 不相关: {stats['not_related_count']}")
    print(f"    🔄 重试: {stats['retry_count']}")
    print(f"    ❌ 错误: {stats['error_count']}")
    print(f"{'='*60}\n")
    
    return stats


async def get_negative_sentiment_list(limit: int = 50) -> List[Dict]:
    """获取负面舆情列表，按发布时间降序排序"""
    async with get_db_session() as session:
        result = await session.execute(
            select(NegativeSentiment)
            .order_by(NegativeSentiment.publish_time.desc())  # 按发布时间降序
            .limit(limit)
        )
        records = result.scalars().all()
        
        return [
            {
                "id": r.id,
                "platform": PLATFORM_NAMES.get(r.platform, r.platform),
                "type": "帖子" if r.content_type == "post" else "评论",
                "title": r.title[:50] if r.title else "",
                "content": r.content[:100] if r.content else "",
                "user": r.user_nickname,
                "reason": r.sentiment_reason[:100] if r.sentiment_reason else "",
                "time": datetime.fromtimestamp(r.publish_time / 1000).strftime("%Y-%m-%d %H:%M") if r.publish_time else ""
            }
            for r in records
        ]


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="天津联通舆情监控 - 情感分析脚本"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="最多处理的条数，默认100"
    )
    
    parser.add_argument(
        "--batch",
        type=int,
        default=5,
        help="每批处理条数，默认5"
    )
    
    parser.add_argument(
        "--test-api",
        action="store_true",
        help="测试API连接"
    )
    
    parser.add_argument(
        "--list-negative",
        action="store_true",
        help="列出最近的负面舆情"
    )
    
    return parser.parse_args()


async def main():
    """主入口函数"""
    args = parse_args()
    
    if args.test_api:
        await test_api_connection()
        return
    
    if args.list_negative:
        print(f"[{get_timestamp()}] 📋 最近负面舆情列表:")
        print(f"{'='*80}")
        
        try:
            negatives = await get_negative_sentiment_list()
            if not negatives:
                print("  暂无负面舆情记录")
            else:
                for i, item in enumerate(negatives, 1):
                    print(f"\n{i}. [{item['platform']}] {item['type']}")
                    if item['title']:
                        print(f"   标题: {item['title']}")
                    print(f"   内容: {item['content']}...")
                    print(f"   用户: {item['user']}")
                    print(f"   原因: {item['reason']}")
                    print(f"   时间: {item['time']}")
        except Exception as e:
            print(f"  获取数据失败: {e}")
        
        print(f"\n{'='*80}")
        return
    
    await process_unanalyzed_content(limit=args.limit, batch_size=args.batch)


if __name__ == "__main__":
    asyncio.run(main())
