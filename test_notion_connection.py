"""
快速测试 Notion 连接

使用方法：
1. 设置环境变量: export NOTION_API_TOKEN="你的token"
2. 运行: python test_notion_connection.py
"""
import os
import sys

def test_connection():
    """测试 Notion API 连接"""
    
    print("=" * 50)
    print("🔗 Notion 连接测试")
    print("=" * 50)
    
    # 检查 Token
    token = os.getenv("NOTION_API_TOKEN")
    if not token:
        print("\n❌ 错误：未找到 NOTION_API_TOKEN 环境变量")
        print("\n请先设置环境变量：")
        print("  Windows (PowerShell): $env:NOTION_API_TOKEN = '你的token'")
        print("  Mac/Linux: export NOTION_API_TOKEN='你的token'")
        return False
    
    print(f"\n✅ Token 已设置 (前10位: {token[:10]}...)")
    
    # 导入连接器
    try:
        from src.notion_connector import NotionConnector
        print("✅ 模块导入成功")
    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        print("请确保在项目根目录运行此脚本")
        return False
    
    # 测试连接
    print("\n📡 正在连接 Notion API...")
    try:
        connector = NotionConnector(token)
        
        # 尝试获取少量数据
        df = connector.fetch_timesheet(
            start_date="2025-01-01",
            end_date="2025-01-31"
        )
        
        print(f"✅ 连接成功！")
        print(f"\n📊 数据概览（2025年1月）：")
        print(f"   记录数: {len(df)} 条")
        
        if len(df) > 0:
            print(f"   成员: {df['成员'].nunique()} 人")
            print(f"   总工时: {df['工时 h'].sum():.1f} 小时")
            print(f"\n📋 前 5 条记录：")
            print(df[['日期', '成员', '工作内容', '工时 h']].head().to_string(index=False))
        
        return True
        
    except Exception as e:
        print(f"\n❌ 连接失败: {e}")
        
        if "401" in str(e):
            print("\n💡 可能原因：Token 无效或已过期")
            print("   解决方案：重新生成 Token")
        elif "403" in str(e):
            print("\n💡 可能原因：Integration 没有访问数据库的权限")
            print("   解决方案：在 Notion 数据库页面添加 Integration 连接")
        elif "404" in str(e):
            print("\n💡 可能原因：数据库 ID 错误")
            print("   解决方案：检查数据库 ID 是否正确")
        
        return False


def export_sample():
    """导出示例数据"""
    from src.notion_connector import fetch_timesheet, save_to_csv
    
    print("\n" + "=" * 50)
    print("📥 导出示例数据")
    print("=" * 50)
    
    # 获取最近一周的数据
    from datetime import datetime, timedelta
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    print(f"\n日期范围: {start_date} 至 {end_date}")
    
    try:
        df = fetch_timesheet(start_date, end_date)
        
        if len(df) == 0:
            print("⚠️ 该时间段没有数据")
            return
        
        # 保存
        output_path = "data/notion_export_sample.csv"
        os.makedirs("data", exist_ok=True)
        save_to_csv(df, output_path)
        
        print(f"✅ 已导出 {len(df)} 条记录到: {output_path}")
        
    except Exception as e:
        print(f"❌ 导出失败: {e}")


if __name__ == "__main__":
    success = test_connection()
    
    if success and len(sys.argv) > 1 and sys.argv[1] == "--export":
        export_sample()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 测试完成！你可以开始使用了")
        print("\n下一步：")
        print("  1. 导出数据: python src/notion_connector.py -s 2025-09-22 -e 2025-09-30 -o data/week39.csv")
        print("  2. 运行分析: python main.py -i data/week39.csv -d 2025-09-28")
    else:
        print("😢 测试失败，请检查上述错误信息")
    print("=" * 50)
