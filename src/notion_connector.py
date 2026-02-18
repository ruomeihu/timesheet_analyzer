"""
Notion 数据连接器模块

直接从 Notion 数据库获取工时数据，支持日期范围过滤

使用方法：
1. 获取 Notion API Token: https://www.notion.so/my-integrations
2. 将 Token 保存到环境变量或配置文件
3. 确保你的 Integration 有权限访问工时数据库
"""
import os
import json
import requests
import pandas as pd
from datetime import date, datetime
from typing import Optional, List, Dict
from pathlib import Path


class NotionConnector:
    """
    Notion 数据库连接器
    
    从 Notion 工时数据库直接获取数据
    """
    
    # 你的工时数据库 ID（已从数据库 URL 中提取）
    DEFAULT_DATABASE_ID = "27860a7d47d280ab9529e599217f6730"
    # 默认数据源名称（多数据源数据库中选取对应的那个）
    DEFAULT_DATA_SOURCE_NAME = "MIH Timesheet 工时库"
    
    def __init__(self, api_token: Optional[str] = None):
        """
        初始化连接器
        
        Parameters
        ----------
        api_token : str, optional
            Notion API Token，如果不提供会尝试从环境变量读取
        """
        self.api_token = api_token or os.getenv("NOTION_API_TOKEN")
        
        if not self.api_token:
            raise ValueError(
                "需要 Notion API Token！\n"
                "获取方式：https://www.notion.so/my-integrations\n"
                "设置方式：\n"
                "  1. 环境变量: export NOTION_API_TOKEN='your_token'\n"
                "  2. 或直接传入: NotionConnector(api_token='your_token')"
            )
        
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2025-09-03"
        }
        
        self.base_url = "https://api.notion.com/v1"
        self._page_title_cache = {}  # page_id -> title
    
    def fetch_timesheet(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        database_id: Optional[str] = None,
        member_filter: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        获取工时数据
        
        Parameters
        ----------
        start_date : str, optional
            起始日期，格式 'YYYY-MM-DD'
        end_date : str, optional
            结束日期，格式 'YYYY-MM-DD'
        database_id : str, optional
            数据库 ID，默认使用 MIH Timesheet
        member_filter : List[str], optional
            筛选特定成员
        
        Returns
        -------
        pd.DataFrame
            工时数据，格式与 CSV 导出一致
        """
        db_id = database_id or self.DEFAULT_DATABASE_ID
        
        # 构建过滤条件
        filters = []
        
        if start_date:
            filters.append({
                "property": "日期",
                "date": {
                    "on_or_after": start_date
                }
            })
        
        if end_date:
            filters.append({
                "property": "日期",
                "date": {
                    "on_or_before": end_date
                }
            })
        
        # 构建请求体
        body = {
            "page_size": 100,  # 每次获取 100 条
            "sorts": [
                {
                    "property": "日期",
                    "direction": "ascending"
                }
            ]
        }
        
        if filters:
            if len(filters) == 1:
                body["filter"] = filters[0]
            else:
                body["filter"] = {
                    "and": filters
                }
        
        # 获取数据源 ID（API 2025-09-03 要求）
        ds_id = self._resolve_data_source_id(db_id)

        # 分页获取所有数据
        all_results = []
        has_more = True
        start_cursor = None

        while has_more:
            if start_cursor:
                body["start_cursor"] = start_cursor

            response = requests.post(
                f"{self.base_url}/data_sources/{ds_id}/query",
                headers=self.headers,
                json=body
            )

            if response.status_code != 200:
                raise Exception(f"Notion API 错误: {response.status_code}\n{response.text}")

            data = response.json()
            all_results.extend(data.get("results", []))

            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")
        
        # 转换为 DataFrame
        return self._parse_results(all_results)
    
    def _resolve_data_source_id(self, database_id: str) -> str:
        """
        从数据库获取数据源 ID（API 2025-09-03 新模型）

        多数据源数据库需要先查出 data_source_id 再查询。
        按 DEFAULT_DATA_SOURCE_NAME 匹配，找不到则取第一个。
        """
        response = requests.get(
            f"{self.base_url}/databases/{database_id}",
            headers=self.headers
        )

        if response.status_code != 200:
            raise Exception(f"获取数据库信息失败: {response.status_code}\n{response.text}")

        db_info = response.json()
        data_sources = db_info.get("data_sources", [])

        if not data_sources:
            raise Exception(
                f"数据库 {database_id} 没有可用的数据源。"
                "请确认 Integration 已连接到该数据库。"
            )

        # 优先按名称匹配
        for ds in data_sources:
            if ds.get("name") == self.DEFAULT_DATA_SOURCE_NAME:
                return ds["id"]

        # 找不到则用第一个
        return data_sources[0]["id"]

    def _parse_results(self, results: List[Dict]) -> pd.DataFrame:
        """解析 Notion API 返回的结果"""
        records = []
        
        for page in results:
            props = page.get("properties", {})
            
            record = {
                "工作内容": self._get_title(props.get("工作内容", {})),
                "MIH Projects 项目库": self._get_relation_title(props.get("MIH Projects 项目库", {})),
                "成员": self._get_person_name(props.get("成员", {})),
                "日期": self._get_date(props.get("日期", {})),
                "工时 h": self._get_number(props.get("工时 h", {})),
                "工作阶段": self._get_select(props.get("工作阶段", {})),
                "概要": self._get_formula(props.get("概要", {})),
                "周数": self._get_formula(props.get("周数", {})),
                "月份": self._get_formula(props.get("月份", {})),
                "优先级": self._get_rollup(props.get("优先级", {})),
                "项目属性": self._get_rollup(props.get("项目属性", {})),
            }
            
            records.append(record)
        
        return pd.DataFrame(records)
    
    def _get_title(self, prop: Dict) -> str:
        """提取 title 类型属性"""
        title_array = prop.get("title", [])
        if title_array:
            return title_array[0].get("plain_text", "")
        return ""
    
    def _get_relation_title(self, prop: Dict) -> str:
        """提取 relation 类型属性的标题"""
        relations = prop.get("relation", [])
        if relations:
            # 获取关联页面的标题
            page_id = relations[0].get("id", "")
            if page_id:
                return self._fetch_page_title(page_id)
        return ""
    
    def _fetch_page_title(self, page_id: str) -> str:
        """获取页面标题（带缓存）"""
        if page_id in self._page_title_cache:
            return self._page_title_cache[page_id]

        title = page_id  # 默认返回 ID 作为后备
        try:
            response = requests.get(
                f"{self.base_url}/pages/{page_id}",
                headers=self.headers
            )
            if response.status_code == 200:
                page = response.json()
                props = page.get("properties", {})
                # 尝试常见的标题属性名
                for title_key in ["Name", "名称", "项目名称", "title", "Title"]:
                    if title_key in props:
                        title_prop = props[title_key]
                        if title_prop.get("type") == "title":
                            title_array = title_prop.get("title", [])
                            if title_array:
                                title = title_array[0].get("plain_text", "")
                                break
                else:
                    # 如果找不到，遍历所有属性找 title 类型
                    for key, value in props.items():
                        if value.get("type") == "title":
                            title_array = value.get("title", [])
                            if title_array:
                                title = title_array[0].get("plain_text", "")
                                break
        except Exception as e:
            print(f"获取页面标题失败: {e}")

        self._page_title_cache[page_id] = title
        return title
    
    def _get_person_name(self, prop: Dict) -> str:
        """提取 person 类型属性"""
        people = prop.get("people", [])
        if people:
            return people[0].get("name", "")
        return ""
    
    def _get_date(self, prop: Dict) -> str:
        """提取 date 类型属性"""
        date_obj = prop.get("date", {})
        if date_obj:
            return date_obj.get("start", "")
        return ""
    
    def _get_number(self, prop: Dict) -> float:
        """提取 number 类型属性"""
        return prop.get("number", 0) or 0
    
    def _get_select(self, prop: Dict) -> str:
        """提取 select 类型属性"""
        select_obj = prop.get("select", {})
        if select_obj:
            return select_obj.get("name", "")
        return ""
    
    def _get_formula(self, prop: Dict) -> str:
        """提取 formula 类型属性"""
        formula = prop.get("formula", {})
        if formula:
            formula_type = formula.get("type", "")
            return str(formula.get(formula_type, ""))
        return ""
    
    def _get_rollup(self, prop: Dict) -> str:
        """提取 rollup 类型属性"""
        rollup = prop.get("rollup", {})
        if rollup:
            rollup_type = rollup.get("type", "")
            if rollup_type == "array":
                array_items = rollup.get("array", [])
                if array_items:
                    # 获取第一个值
                    first_item = array_items[0]
                    item_type = first_item.get("type", "")
                    if item_type == "select":
                        return first_item.get("select", {}).get("name", "")
            return str(rollup.get(rollup_type, ""))
        return ""


def fetch_timesheet(
    start_date: str,
    end_date: str,
    api_token: Optional[str] = None
) -> pd.DataFrame:
    """
    便捷函数：获取指定日期范围的工时数据
    
    Parameters
    ----------
    start_date : str
        起始日期，格式 'YYYY-MM-DD'
    end_date : str
        结束日期，格式 'YYYY-MM-DD'
    api_token : str, optional
        Notion API Token
    
    Returns
    -------
    pd.DataFrame
        工时数据
    
    Examples
    --------
    >>> df = fetch_timesheet("2025-09-22", "2025-09-30")
    >>> print(f"获取到 {len(df)} 条记录")
    """
    connector = NotionConnector(api_token)
    return connector.fetch_timesheet(start_date, end_date)


def save_to_csv(
    df: pd.DataFrame,
    filepath: str,
    encoding: str = 'utf-8-sig'
) -> str:
    """
    保存 DataFrame 为 CSV 文件
    
    Parameters
    ----------
    df : pd.DataFrame
        数据
    filepath : str
        保存路径
    encoding : str
        编码，默认 utf-8-sig（兼容 Excel）
    
    Returns
    -------
    str
        保存的文件路径
    """
    df.to_csv(filepath, index=False, encoding=encoding)
    return filepath


# ============================================
# 命令行支持
# ============================================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="从 Notion 获取工时数据")
    parser.add_argument("--start", "-s", required=True, help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end", "-e", required=True, help="结束日期 YYYY-MM-DD")
    parser.add_argument("--output", "-o", default="timesheet_export.csv", help="输出文件路径")
    parser.add_argument("--token", "-t", help="Notion API Token（或设置环境变量 NOTION_API_TOKEN）")
    
    args = parser.parse_args()
    
    print(f"📅 获取 {args.start} 至 {args.end} 的工时数据...")
    
    try:
        df = fetch_timesheet(args.start, args.end, args.token)
        print(f"✅ 获取到 {len(df)} 条记录")
        
        save_to_csv(df, args.output)
        print(f"💾 已保存到: {args.output}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
