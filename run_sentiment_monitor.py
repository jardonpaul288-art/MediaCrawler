# -*- coding: utf-8 -*-
"""
天津联通舆情监控系统 - 主入口脚本
流程：多平台串行爬取 → 数据同步 → 情感分析 → 负面筛选
"""

import sys
import io
import asyncio
import argparse
from datetime import datetime

# Force UTF-8 encoding
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def print_banner():
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║         🔍 天津联通舆情监控系统 📊                               ║
║    流程：多平台串行爬取 → 数据同步 → 情感分析 → 负面筛选         ║
║    • 串行执行（一个平台完成后再执行下一个）                      ║
║    • 二维码显示已禁用                                            ║
╚══════════════════════════════════════════════════════════════════╝
""")


async def run_full_pipeline(
    skip_crawl: bool = False,
    skip_sync: bool = False,
    skip_analyze: bool = False,
    time_per_platform_minutes: float = 3
) -> dict:
    """运行完整流程：爬取 -> 同步 -> 分析"""
    results = {"crawl": [], "sync": [], "analyze": None}
    
    # 步骤1 & 2：循环执行每个平台的爬取和同步
    if not skip_crawl:
        print(f"\n{'#'*70}")
        print(f"# 步骤 1: 多平台串行爬取与同步")
        print(f"{'#'*70}")
        try:
            from sentiment_crawler import get_keywords, run_platform_crawler, ALL_PLATFORMS, PLATFORM_NAMES
            from sync_sentiment_data import sync_platform_data, get_db_session, clear_unified_table
            
            keywords = get_keywords()
            print(f"[{get_timestamp()}] 📋 关键词: {len(keywords)} 个")
            print(f"[{get_timestamp()}] ⏰ 每平台超时: {time_per_platform_minutes} 分钟")
            
            # 如果需要同步，先清空统一表（只清空一次）
            if not skip_sync:
                async with get_db_session() as session:
                    deleted_count = await clear_unified_table(session)
                    print(f"[{get_timestamp()}] 🗑️  已清空统一舆情表，删除 {deleted_count} 条旧数据")
            
            timeout_seconds = time_per_platform_minutes * 60
            
            for i, platform in enumerate(ALL_PLATFORMS, 1):
                platform_name = PLATFORM_NAMES.get(platform, platform)
                print(f"\n{'='*70}")
                print(f"[{get_timestamp()}] 🔄 进度: {i}/{len(ALL_PLATFORMS)} 平台 - {platform_name}")
                print(f"{'='*70}")
                
                # 1. 爬取
                crawl_result = await run_platform_crawler(platform, keywords, timeout_seconds)
                results["crawl"].append(crawl_result)
                
                # 特殊处理：如果快手报错431，尝试清理缓存
                if platform == "ks" and crawl_result.get("status") == "error" and "431" in str(crawl_result.get("message", "")):
                    print(f"[{get_timestamp()}] 🧹 检测到快手431错误，尝试清理缓存...")
                    try:
                        import shutil
                        user_data_dir = os.path.join(os.getcwd(), "browser_data", "cdp_ks_user_data_dir")
                        if os.path.exists(user_data_dir):
                            shutil.rmtree(user_data_dir, ignore_errors=True)
                            print(f"[{get_timestamp()}] ✅ 快手缓存已清理，下次运行将重新登录")
                    except Exception as e:
                        print(f"[{get_timestamp()}] ❌ 清理缓存失败: {e}")

                # 2. 同步（即使爬取失败也尝试同步，因为可能有部分数据）
                if not skip_sync:
                    print(f"[{get_timestamp()}] 📥 同步 {platform_name} 数据...")
                    try:
                        async with get_db_session() as session:
                            sync_res = await sync_platform_data(session, platform)
                            results["sync"].append({"platform": platform, "data": sync_res})
                    except Exception as e:
                        print(f"[{get_timestamp()}] ❌ {platform_name} 同步失败: {e}")
                
                # 3. 等待
                if i < len(ALL_PLATFORMS):
                    print(f"[{get_timestamp()}] ⏳ 等待3秒后执行下一个平台...")
                    await asyncio.sleep(3)
                    
        except Exception as e:
            print(f"[{get_timestamp()}] ❌ 流程异常: {e}")
            import traceback
            traceback.print_exc()
    
    # 步骤3：分析（所有平台完成后统一分析）
    if not skip_analyze:
        print(f"\n{'#'*70}")
        print(f"# 步骤 2: 情感分析")
        print(f"{'#'*70}")
        try:
            from sentiment_analyzer import process_unanalyzed_content
            analyze_results = await process_unanalyzed_content(limit=99999)
            results["analyze"] = {
                "status": "success", 
                "total_processed": analyze_results.get("total_processed", 0), 
                "negative_count": analyze_results.get("negative_count", 0)
            }
        except Exception as e:
            print(f"[{get_timestamp()}] ❌ 分析失败: {e}")
            import traceback
            traceback.print_exc()
            results["analyze"] = {"status": "error", "message": str(e)}
    
    return results


async def run_scheduled_monitor(
    interval_minutes=20, 
    run_once=False, 
    skip_crawl=False, 
    skip_sync=False, 
    skip_analyze=False, 
    time_per_platform_minutes=3
):
    cycle = 0
    while True:
        cycle += 1
        start_time = datetime.now()
        print(f"\n{'='*70}")
        print(f"[{get_timestamp()}] 🔄 第 {cycle} 轮监控开始")
        print(f"{'='*70}")
        
        try:
            results = await run_full_pipeline(
                skip_crawl, skip_sync, skip_analyze, time_per_platform_minutes
            )
            elapsed = (datetime.now() - start_time).total_seconds()
            
            print(f"\n{'='*70}")
            print(f"[{get_timestamp()}] 📊 结果汇总 (耗时 {elapsed/60:.1f} 分钟)")
            
            # 统计爬取结果
            crawl_success = 0
            crawl_total = 0
            if isinstance(results["crawl"], list):
                crawl_total = len(results["crawl"])
                crawl_success = sum(1 for r in results["crawl"] if r.get("status") == "success")
            elif isinstance(results["crawl"], dict) and results["crawl"].get("status") == "success":
                # 兼容旧格式（虽然现在是并行模式）
                crawl_success = results["crawl"].get("success_count", 0)
                crawl_total = results["crawl"].get("platforms", 0)
            
            if crawl_total > 0:
                print(f"    ✅ 爬取: {crawl_success}/{crawl_total} 平台")
                
            # 统计同步结果
            sync_posts = 0
            sync_comments = 0
            if isinstance(results["sync"], list):
                for item in results["sync"]:
                    data = item.get("data", {})
                    sync_posts += data.get("posts", 0)
                    sync_comments += data.get("comments", 0)
            elif isinstance(results["sync"], dict) and results["sync"].get("status") == "success":
                sync_posts = results["sync"].get("total_posts", 0)
                sync_comments = results["sync"].get("total_comments", 0)
                
            if sync_posts > 0 or sync_comments > 0:
                print(f"    ✅ 同步: {sync_posts} 帖子, {sync_comments} 评论")
                
            if results["analyze"] and results["analyze"]["status"] == "success":
                print(f"    ✅ 分析: {results['analyze'].get('total_processed')} 条, 负面 {results['analyze'].get('negative_count')} 条")
            print(f"{'='*70}")
        except Exception as e:
            print(f"[{get_timestamp()}] ❌ 异常: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 并行模式下不需要恢复配置，因为是子进程运行
            pass
        
        if run_once:
            print(f"\n[{get_timestamp()}] 🏁 完成")
            break
        
        print(f"\n[{get_timestamp()}] ⏰ 等待 {interval_minutes} 分钟...")
        await asyncio.sleep(interval_minutes * 60)


def parse_args():
    parser = argparse.ArgumentParser(description="天津联通舆情监控系统")
    parser.add_argument("--interval", type=int, default=20, help="执行间隔（分钟）")
    parser.add_argument("--time-per-platform", type=float, default=0.5, help="每平台超时（分钟）")
    parser.add_argument("--once", action="store_true", help="只执行一次")
    parser.add_argument("--skip-crawl", action="store_true", help="跳过爬取")
    parser.add_argument("--skip-sync", action="store_true", help="跳过同步")
    parser.add_argument("--skip-analyze", action="store_true", help="跳过分析")
    parser.add_argument("--test-api", action="store_true", help="测试API")
    return parser.parse_args()


def main():
    args = parse_args()
    print_banner()
    
    from sentiment_crawler import get_keywords, ALL_PLATFORMS
    keywords = get_keywords()
    
    print(f"📋 参数: 关键词{len(keywords)}个, 每平台{args.time_per_platform}分钟, 共{len(ALL_PLATFORMS)}个平台")
    print(f"📋 预计爬取时间: {args.time_per_platform * len(ALL_PLATFORMS)} 分钟")
    print()
    
    if args.test_api:
        from sentiment_analyzer import test_api_connection
        asyncio.run(test_api_connection())
        return
    
    try:
        asyncio.run(run_scheduled_monitor(
            args.interval, args.once, args.skip_crawl, args.skip_sync, args.skip_analyze, 
            args.time_per_platform
        ))
    except KeyboardInterrupt:
        print(f"\n[{get_timestamp()}] 🛑 用户中断")
        from sentiment_crawler import restore_config_file
        restore_config_file()


if __name__ == "__main__":
    main()
