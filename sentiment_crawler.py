# -*- coding: utf-8 -*-
"""
天津联通舆情监控 - 多平台串行爬取脚本
直接调用原项目API，不使用子进程
"""

import sys
import io
import os
import asyncio
import argparse
from typing import List
from datetime import datetime

# Force UTF-8 encoding
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 项目根目录
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

import config
from main import CrawlerFactory
from var import crawler_type_var

# ========== 舆情监控关键词（以此为准）==========
SENTIMENT_KEYWORDS = [
    "天津联通负面",
    "天津联通",
    "联通投诉",
    "联通维权",
    "联通吐槽",
    "联通差评",
    "联通服务差",
    "联通乱扣费",
    "联通网络差",
]

# 支持的平台列表
# ALL_PLATFORMS = ["ks","dy", "xhs", "bili", "wb", "tieba", "zhihu"]
ALL_PLATFORMS = ["ks","dy"]

# 平台中文名称映射
PLATFORM_NAMES = {
    "dy": "抖音",
    "ks": "快手",
    "xhs": "小红书",
    "bili": "B站",
    "wb": "微博",
    "tieba": "贴吧",
    "zhihu": "知乎",
}


def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_keywords() -> List[str]:
    """获取关键词列表（优先使用脚本中的）"""
    if SENTIMENT_KEYWORDS:
        return SENTIMENT_KEYWORDS
    return []


async def run_platform_crawler(platform: str, keywords: List[str], timeout_seconds: float) -> dict:
    """运行单个平台的爬取（直接调用API）"""
    platform_name = PLATFORM_NAMES.get(platform, platform)
    
    print(f"\n[{get_timestamp()}] 🚀 {platform_name} 开始爬取...")
    print(f"    关键词: {', '.join(keywords[:3])}{'...' if len(keywords) > 3 else ''}")
    print(f"    超时: {timeout_seconds:.0f} 秒 ({timeout_seconds/60:.1f} 分钟)")
    
    # 保存原始配置
    original_platform = config.PLATFORM
    original_keywords = config.KEYWORDS
    original_save_option = config.SAVE_DATA_OPTION
    original_crawler_type = config.CRAWLER_TYPE
    original_enable_comments = config.ENABLE_GET_COMMENTS
    
    try:
        # 设置新配置
        config.PLATFORM = platform
        config.KEYWORDS = ",".join(keywords)
        config.SAVE_DATA_OPTION = "db"
        config.CRAWLER_TYPE = "search"
        config.ENABLE_GET_COMMENTS = True
        crawler_type_var.set("search")
        
        # 创建爬虫并运行
        crawler = CrawlerFactory.create_crawler(platform=platform)
        
        try:
            await asyncio.wait_for(crawler.start(), timeout=timeout_seconds)
            print(f"[{get_timestamp()}] ✅ {platform_name} 爬取完成")
            return {"platform": platform, "status": "success"}
            
        except asyncio.TimeoutError:
            print(f"[{get_timestamp()}] ⏰ {platform_name} 超时（{timeout_seconds/60:.1f}分钟），已保存部分数据")
            return {"platform": platform, "status": "timeout"}
            
        finally:
            # 清理浏览器资源
            if hasattr(crawler, 'cdp_manager') and crawler.cdp_manager:
                try:
                    await crawler.cdp_manager.cleanup(force=True)
                except:
                    pass
            elif hasattr(crawler, 'browser_context') and crawler.browser_context:
                try:
                    await crawler.browser_context.close()
                except:
                    pass
                    
    except Exception as e:
        print(f"[{get_timestamp()}] ❌ {platform_name} 错误: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return {"platform": platform, "status": "error", "message": str(e)[:100]}
        
    finally:
        # 恢复原始配置
        config.PLATFORM = original_platform
        config.KEYWORDS = original_keywords
        config.SAVE_DATA_OPTION = original_save_option
        config.CRAWLER_TYPE = original_crawler_type
        config.ENABLE_GET_COMMENTS = original_enable_comments


async def run_all_platforms_serial(
    keywords: List[str], 
    platforms: List[str] = None,
    time_per_platform_minutes: float = 3
) -> List[dict]:
    """串行运行所有平台的爬取任务"""
    if platforms is None:
        platforms = ALL_PLATFORMS.copy()
    
    timeout_seconds = time_per_platform_minutes * 60
    
    print(f"\n{'='*70}")
    print(f"[{get_timestamp()}] 📢 开始多平台串行爬取")
    print(f"{'='*70}")
    print(f"[{get_timestamp()}] 📋 平台数量: {len(platforms)} 个")
    print(f"[{get_timestamp()}]    {', '.join([PLATFORM_NAMES.get(p, p) for p in platforms])}")
    print(f"[{get_timestamp()}] 🔍 关键词数量: {len(keywords)} 个")
    print(f"[{get_timestamp()}] ⏰ 每平台超时: {time_per_platform_minutes} 分钟")
    print(f"[{get_timestamp()}] ⏰ 预计总时间: {time_per_platform_minutes * len(platforms)} 分钟")
    print(f"{'='*70}")
    print(f"[{get_timestamp()}] 🔍 关键词列表:")
    for i, kw in enumerate(keywords, 1):
        print(f"    {i}. {kw}")
    print(f"{'='*70}")
    
    results = []
    
    # 串行执行每个平台
    for i, platform in enumerate(platforms, 1):
        print(f"\n{'='*70}")
        print(f"[{get_timestamp()}] 🔄 进度: {i}/{len(platforms)} 平台")
        print(f"{'='*70}")
        
        result = await run_platform_crawler(platform, keywords, timeout_seconds)
        results.append(result)
        
        # 每个平台完成后等待几秒，让资源释放
        if i < len(platforms):
            print(f"[{get_timestamp()}] ⏳ 等待3秒后执行下一个平台...")
            await asyncio.sleep(3)
    
    # 打印汇总
    print(f"\n{'='*70}")
    print(f"[{get_timestamp()}] 📊 爬取结果汇总:")
    
    success_count = 0
    for result in results:
        platform_name = PLATFORM_NAMES.get(result["platform"], result["platform"])
        if result.get("status") == "success":
            print(f"  ✅ {platform_name}: 完成")
            success_count += 1
        elif result.get("status") == "timeout":
            print(f"  ⏰ {platform_name}: 超时（已保存部分数据）")
            success_count += 1
        else:
            print(f"  ❌ {platform_name}: 失败")
    
    print(f"\n[{get_timestamp()}] 📊 成功: {success_count}/{len(platforms)} 个平台")
    print(f"{'='*70}\n")
    
    return results


async def run_scheduled_crawler(
    keywords: List[str],
    platforms: List[str] = None,
    interval_minutes: int = 20,
    run_once: bool = False,
    time_per_platform_minutes: float = 3
) -> None:
    """定时运行爬虫"""
    cycle = 0
    
    while True:
        cycle += 1
        print(f"\n{'#'*70}")
        print(f"[{get_timestamp()}] 🔄 第 {cycle} 轮爬取开始")
        print(f"{'#'*70}")
        
        try:
            await run_all_platforms_serial(keywords, platforms, time_per_platform_minutes)
        except Exception as e:
            print(f"[{get_timestamp()}] ❌ 本轮爬取异常: {e}")
            import traceback
            traceback.print_exc()
        
        if run_once:
            print(f"[{get_timestamp()}] 🏁 单次执行完成")
            break
        
        print(f"[{get_timestamp()}] ⏰ 等待 {interval_minutes} 分钟后执行下一轮...")
        await asyncio.sleep(interval_minutes * 60)


def parse_args():
    parser = argparse.ArgumentParser(description="天津联通舆情监控 - 多平台串行爬取脚本")
    parser.add_argument("--platforms", type=str, default=None,
        help=f"要爬取的平台，逗号分隔。可选: {','.join(ALL_PLATFORMS)}")
    parser.add_argument("--interval", type=int, default=20, help="执行间隔（分钟）")
    parser.add_argument("--time-per-platform", type=float, default=3, help="每平台超时（分钟）")
    parser.add_argument("--once", action="store_true", help="只执行一次")
    return parser.parse_args()


def main():
    args = parse_args()
    
    platforms = None
    if args.platforms:
        platforms = [p.strip() for p in args.platforms.split(",")]
        invalid = [p for p in platforms if p not in ALL_PLATFORMS]
        if invalid:
            print(f"❌ 不支持的平台: {invalid}")
            sys.exit(1)
    
    keywords = get_keywords()
    if not keywords:
        print(f"❌ 没有找到关键词")
        sys.exit(1)
    
    platform_count = len(platforms or ALL_PLATFORMS)
    total_time = args.time_per_platform * platform_count
    
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║      天津联通舆情监控系统 - 多平台串行爬取（单进程）             ║
╚══════════════════════════════════════════════════════════════════╝

📋 运行参数:
  • 平台数量: {platform_count} 个
  • 关键词数量: {len(keywords)} 个
  • 每平台超时: {args.time_per_platform} 分钟
  • 预计总时间: {total_time} 分钟
  • 执行间隔: {args.interval} 分钟
  • 执行模式: {'单次执行' if args.once else '循环执行'}

💡 单进程串行执行，直接调用原项目API
💡 二维码显示已禁用

按 Ctrl+C 可停止运行
""")
    
    try:
        asyncio.run(run_scheduled_crawler(
            keywords=keywords,
            platforms=platforms,
            interval_minutes=args.interval,
            run_once=args.once,
            time_per_platform_minutes=args.time_per_platform
        ))
    except KeyboardInterrupt:
        print(f"\n[{get_timestamp()}] 🛑 用户中断")


if __name__ == "__main__":
    main()
