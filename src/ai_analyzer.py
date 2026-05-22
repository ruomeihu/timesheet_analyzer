"""
AI 分析模块

使用 Claude API 进行深度工时分析
支持四个维度、十个关键指标的全面分析
"""
import os
import re
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from datetime import date
import pandas as pd

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_employees_config


@dataclass
class AIAnalysisConfig:
    """AI 分析配置"""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 8192
    temperature: float = 0.3


@dataclass
class AnalysisDimension:
    """分析维度结果"""
    dimension: str          # 维度名称
    indicators: List[Dict]  # 指标列表
    summary: str            # 维度总结
    severity: str           # 整体严重程度: low/medium/high


@dataclass
class QuickScanResult:
    """15分钟快速扫视结果"""
    anomalies: List[Dict] = field(default_factory=list)       # 异常值
    core_projects: List[Dict] = field(default_factory=list)   # 核心项目状态
    black_holes: List[Dict] = field(default_factory=list)     # 黑洞时间
    action_items: List[str] = field(default_factory=list)     # 立即行动项


@dataclass
class AIInsightResult:
    """AI 分析完整结果"""
    dimensions: List[AnalysisDimension] = field(default_factory=list)
    quick_scan: QuickScanResult = field(default_factory=QuickScanResult)
    executive_summary: str = ""
    recommendations: List[Dict] = field(default_factory=list)
    raw_response: str = ""  # 保留原始响应用于调试


def serialize_ai_insights(result: AIInsightResult) -> Dict[str, Any]:
    """把 AIInsightResult 转为可 JSON 序列化的 dict。"""
    return asdict(result)


def deserialize_ai_insights(data: Dict[str, Any]) -> AIInsightResult:
    """从 sidecar JSON 里的 dict 重建 AIInsightResult,重建嵌套 dataclass。"""
    quick = QuickScanResult(**(data.get("quick_scan") or {}))
    dims = [AnalysisDimension(**d) for d in (data.get("dimensions") or [])]
    return AIInsightResult(
        dimensions=dims,
        quick_scan=quick,
        executive_summary=data.get("executive_summary", "") or "",
        recommendations=data.get("recommendations") or [],
        raw_response=data.get("raw_response", "") or "",
    )


class AIAnalyzer:
    """
    Claude AI 驱动的深度工时分析器

    支持四个维度、十个关键指标：

    维度一：战略一致性
    - 1. 战略 vs 琐事比例
    - 2. 重点项目投入度

    维度二：执行效率与模式
    - 3. 碎片化程度
    - 4. 会议/协作占比
    - 5. 预估 vs 实际偏差

    维度三：团队健康与风险
    - 6. 隐性加班与负荷分布
    - 7. 异常空白或通用填充

    维度四：财务与合规
    - 8. 资本化工时占比
    - 9. 跨部门支持成本

    快速扫视框架：异常值 + 核心项目 + 黑洞时间
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 AI 分析器

        Parameters
        ----------
        api_key : str, optional
            Anthropic API Key，如果不提供则从环境变量读取
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "anthropic 库未安装。请运行: pip install anthropic"
            )

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API Key 未配置。"
                "请设置环境变量 ANTHROPIC_API_KEY 或在初始化时传入。"
            )

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.config = get_employees_config()
        self.ai_config = self._load_ai_config()

    def _load_ai_config(self) -> AIAnalysisConfig:
        """加载 AI 分析配置"""
        defaults = self.config.get('defaults', {})
        ai_settings = defaults.get('ai_analysis', {})

        return AIAnalysisConfig(
            model=ai_settings.get('model', 'claude-sonnet-4-20250514'),
            max_tokens=ai_settings.get('max_tokens', 8192),
            temperature=ai_settings.get('temperature', 0.3)
        )

    def analyze(
        self,
        df: pd.DataFrame,
        member_results: List,
        project_results: List,
        summary: Dict,
        period: str = "本周"
    ) -> AIInsightResult:
        """
        执行 AI 深度分析

        Parameters
        ----------
        df : pd.DataFrame
            原始工时数据（已预处理）
        member_results : List[MemberAnalysis]
            成员分析结果
        project_results : List[ProjectAnalysis]
            项目分析结果
        summary : Dict
            周期汇总信息
        period : str
            分析周期

        Returns
        -------
        AIInsightResult
            完整的 AI 分析结果
        """
        # 1. 准备分析数据
        analysis_data = self._prepare_analysis_data(
            df, member_results, project_results, summary, period
        )

        # 2. 构建 Prompt
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(analysis_data)

        # 3. 调用 Claude API
        response, stop_reason = self._call_claude(system_prompt, user_prompt)

        # 4. 解析响应
        result = self._parse_response(response, stop_reason)

        return result

    def _prepare_analysis_data(
        self,
        df: pd.DataFrame,
        member_results: List,
        project_results: List,
        summary: Dict,
        period: str
    ) -> Dict:
        """准备传递给 LLM 的分析数据"""

        # 获取团队配置
        employees = self.config.get('employees', [])
        department_info = self.config.get('department', {})

        # 构建员工详情
        employee_details = []
        for emp in employees:
            emp_data = {
                'name': emp.get('name_cn'),
                'position': emp.get('position', emp.get('description', '')),
                'type': emp.get('type'),
                'responsibilities': emp.get('responsibilities', []),
                'onboard_date': emp.get('onboard_date'),
            }
            employee_details.append(emp_data)

        # 成员工时统计
        member_stats = []
        for m in member_results:
            member_stats.append({
                'name': m.name,
                'type': m.type,
                'total_hours': m.total_hours,
                'standard_hours': m.standard_hours,
                'achievement_rate': m.achievement_rate,
                'daily_avg': m.daily_avg,
                'task_count': m.task_count,
                'working_days': m.working_days,
                'status': m.status,
                'leave_days': m.leave_days
            })

        # 项目投入统计
        project_stats = []
        for p in project_results:
            project_stats.append({
                'name': p.name,
                'total_hours': p.total_hours,
                'percentage': p.percentage,
                'member_count': p.member_count,
                'task_count': p.task_count,
                'attribute': p.attribute,
                'priority': p.priority
            })

        # 原始条目详情（用于深度分析）
        raw_entries = []
        df_period = df[df['周期类型'] == period].copy()
        for _, row in df_period.iterrows():
            entry = {
                'date': str(row['日期_date']),
                'weekday': row.get('星期', ''),
                'member': row['成员_中文'],
                'project': row['项目名称_清理'],
                'project_content': row.get('项目内容', ''),
                'hours': row['工时 h'],
                'attribute': row.get('项目属性', '未分类'),
                'stage': row.get('工作阶段', ''),
                'description': row.get('工作内容', '') or row.get('概要', '')
            }
            raw_entries.append(entry)

        # 计算碎片化指标
        fragmentation_data = self._calculate_fragmentation(df_period)

        # 构建完整数据包
        return {
            'period': period,
            'date_range': summary.get('date_range', ['', '']),
            'department': department_info,
            'employee_profiles': employee_details,
            'summary': {
                'total_hours': summary.get('total_hours', 0),
                'working_days': summary.get('working_days', 0),
                'project_count': summary.get('project_count', 0),
                'member_count': summary.get('member_count', 0),
                'task_count': summary.get('task_count', 0)
            },
            'member_stats': member_stats,
            'project_stats': project_stats,
            'raw_entries': raw_entries,
            'fragmentation': fragmentation_data,
            'project_categories': self.config.get('project_categories', {})
        }

    def _calculate_fragmentation(self, df: pd.DataFrame) -> Dict:
        """计算碎片化程度指标"""
        fragmentation = {}

        if '成员_中文' not in df.columns or '项目名称_清理' not in df.columns:
            return fragmentation

        for member in df['成员_中文'].unique():
            member_data = df[df['成员_中文'] == member]

            # 每日切换项目数
            if '日期_date' in df.columns:
                daily_switches = member_data.groupby('日期_date')['项目名称_清理'].nunique()
                avg_daily = round(daily_switches.mean(), 1) if len(daily_switches) > 0 else 0
                max_daily = int(daily_switches.max()) if len(daily_switches) > 0 else 0
            else:
                avg_daily = 0
                max_daily = 0

            fragmentation[member] = {
                'avg_daily_projects': avg_daily,
                'max_daily_projects': max_daily,
                'total_unique_projects': int(member_data['项目名称_清理'].nunique()),
                'avg_task_duration': round(
                    member_data['工时 h'].mean(), 1
                ) if len(member_data) > 0 else 0
            }

        return fragmentation

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        return """你是一位资深的企业管理咨询顾问，专精于团队效能分析和工时管理。

你将收到一个团队的周度工时数据，需要从以下四个维度、十个关键指标进行深度分析：

## 分析框架

### 第一维度：战略一致性（做正确的事）
1. **战略 vs 琐事比例** - 战略项目与维持性事务的工时比例是否合理
2. **重点项目投入度** - TOP 3 重点项目是否获得足够资源

### 第二维度：执行效率与模式（正确地做事）
3. **碎片化程度** - 员工一天内切换不同项目/任务的频率是否过高
4. **会议/协作占比** - 会议和沟通时间是否过多，影响深度工作
5. **预估 vs 实际偏差** - 如果有预估数据，分析偏差原因

### 第三维度：团队健康与风险（可持续性）
6. **隐性加班与负荷分布** - 是否存在单点依赖或过度负荷
7. **异常空白或通用填充** - 笼统描述可能隐藏的问题

### 第四维度：财务与合规（投入产出比）
8. **资本化工时占比** - CapEx vs OpEx 的分布（如果项目属性包含相关信息）
9. **跨部门支持成本** - 帮助其他部门的时间投入

### 快速扫视框架（15分钟审视）
- **异常值**：工时极低（<30h）或极高（>60h）的全职人员
- **核心项目**：本周最重要项目投入是否足够
- **黑洞时间**："其他"、"行政"、"会议"占比是否过高

## 输出要求

请以 JSON 格式输出分析结果，结构如下：

```json
{
  "executive_summary": "一段话总结本周团队工时的核心发现（100-200字）",
  "dimensions": [
    {
      "dimension": "战略一致性",
      "indicators": [
        {
          "name": "战略 vs 琐事比例",
          "value": "战略项目 35%, 维持性事务 65%",
          "assessment": "偏低",
          "finding": "具体发现描述...",
          "severity": "medium"
        }
      ],
      "summary": "该维度总结",
      "severity": "medium"
    }
  ],
  "quick_scan": {
    "anomalies": [
      {"type": "工时异常", "member": "xxx", "value": "xxx", "concern": "具体关注点"}
    ],
    "core_projects": [
      {"project": "xxx", "hours": 10, "status": "充足/不足", "comment": "说明"}
    ],
    "black_holes": [
      {"category": "xxx", "hours": 5, "percentage": "10%", "risk": "风险说明"}
    ],
    "action_items": ["立即需要做的事项1", "立即需要做的事项2"]
  },
  "recommendations": [
    {
      "priority": "high",
      "category": "战略/效率/健康/财务",
      "title": "建议标题",
      "description": "具体建议内容",
      "expected_impact": "预期效果"
    }
  ]
}
```

## 数据字段说明

每条原始工时条目包含以下字段：
- **project**: 项目名称（经过清理的简称）
- **project_content**: 项目内容（更详细的项目分类或具体内容描述，有助于理解项目的实际工作方向）
- **description**: 具体的工作内容描述
- **attribute**: 项目属性
- **stage**: 工作阶段

请特别关注 `project_content` 字段，它提供了比项目名称更具体的内容信息，有助于判断工作的战略价值、工作性质和资源分配合理性。

## 分析原则

1. 结合每位员工的职位和职责进行个性化分析
2. 考虑全职/兼职/按需的不同工作模式
3. 关注趋势和模式，而非孤立数据点
4. 给出具体、可操作的建议
5. 用数据支撑每个结论
6. 如果某些指标数据不足，请明确说明而非猜测
7. 利用 project_content 字段深入理解每个项目的实际工作内容和方向

请确保输出的是合法的 JSON 格式，可以被直接解析。不要在 JSON 外添加任何说明文字。"""

    def _build_user_prompt(self, data: Dict) -> str:
        """构建用户提示"""
        # 限制原始条目数量，避免超出 token 限制
        raw_entries = data['raw_entries']
        if len(raw_entries) > 100:
            raw_entries = raw_entries[:100]
            entries_note = f"\n（注：原始条目过多，仅展示前 100 条，共 {len(data['raw_entries'])} 条）"
        else:
            entries_note = ""

        return f"""请分析以下团队工时数据：

## 基本信息
- 分析周期：{data['period']}
- 日期范围：{data['date_range'][0]} 至 {data['date_range'][1]}
- 部门：{data['department'].get('name', '未知')}
- 部门职责：{data['department'].get('responsibilities', '未知')}

## 团队概览
- 总工时：{data['summary']['total_hours']} 小时
- 工作天数：{data['summary']['working_days']} 天
- 项目数：{data['summary']['project_count']} 个
- 团队成员：{data['summary']['member_count']} 人
- 任务条目：{data['summary']['task_count']} 条

## 团队成员档案
{json.dumps(data['employee_profiles'], ensure_ascii=False, indent=2)}

## 成员工时统计
{json.dumps(data['member_stats'], ensure_ascii=False, indent=2)}

## 项目投入统计
{json.dumps(data['project_stats'], ensure_ascii=False, indent=2)}

## 碎片化分析
{json.dumps(data['fragmentation'], ensure_ascii=False, indent=2)}

## 项目分类参考
{json.dumps(data['project_categories'], ensure_ascii=False, indent=2)}

## 原始工时条目{entries_note}
{json.dumps(raw_entries, ensure_ascii=False, indent=2)}

请根据以上数据，按照系统提示中的分析框架进行深度分析，并以 JSON 格式输出结果。"""

    def _call_claude(self, system_prompt: str, user_prompt: str) -> tuple:
        """调用 Claude API，返回 (text, stop_reason)"""
        message = self.client.messages.create(
            model=self.ai_config.model,
            max_tokens=self.ai_config.max_tokens,
            temperature=self.ai_config.temperature,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        return message.content[0].text, message.stop_reason

    def _clean_json_string(self, raw: str) -> str:
        """
        清理 LLM 输出中的常见 JSON 格式问题

        处理：markdown 代码块包裹、尾部逗号、控制字符、注释等
        """
        text = raw.strip()

        # 1. 去掉 markdown 代码块包裹 (```json ... ``` 或 ``` ... ```)
        text = re.sub(r'^```(?:json)?\s*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)

        # 2. 提取最外层 JSON 对象
        json_start = text.find('{')
        json_end = text.rfind('}')
        if json_start == -1 or json_end == -1:
            return text
        text = text[json_start:json_end + 1]

        # 3. 移除尾部逗号（, 后紧跟 } 或 ]，中间可能有空白/换行）
        text = re.sub(r',\s*([}\]])', r'\1', text)

        # 4. 修复 JSON 字符串值中的未转义控制字符（换行、制表符等）
        #    在 JSON 字符串内部，真正的换行符应该是 \n 而不是字面换行
        text = self._escape_control_chars_in_strings(text)

        return text

    def _escape_control_chars_in_strings(self, text: str) -> str:
        """
        修复 JSON 字符串值中未转义的控制字符

        LLM 输出的 JSON 中，字符串值经常包含字面换行符、制表符等，
        这些在 JSON 标准中是不合法的，需要转义为 \\n、\\t 等。
        """
        result = []
        in_string = False
        escape_next = False
        i = 0

        while i < len(text):
            ch = text[i]

            if escape_next:
                result.append(ch)
                escape_next = False
                i += 1
                continue

            if ch == '\\' and in_string:
                escape_next = True
                result.append(ch)
                i += 1
                continue

            if ch == '"' and not escape_next:
                in_string = not in_string
                result.append(ch)
                i += 1
                continue

            if in_string:
                if ch == '\n':
                    result.append('\\n')
                elif ch == '\r':
                    result.append('\\r')
                elif ch == '\t':
                    result.append('\\t')
                elif ord(ch) < 0x20:
                    result.append(f'\\u{ord(ch):04x}')
                else:
                    result.append(ch)
            else:
                result.append(ch)

            i += 1

        return ''.join(result)

    def _parse_response(self, response: str, stop_reason: str = "end_turn") -> AIInsightResult:
        """解析 Claude 响应"""
        truncated = (stop_reason == "max_tokens")

        # 保存原始响应到调试文件
        try:
            debug_path = Path(__file__).parent.parent / "output"
            debug_path.mkdir(exist_ok=True)
            (debug_path / "ai_raw_response.txt").write_text(
                f"stop_reason: {stop_reason}\n\n{response}",
                encoding='utf-8'
            )
        except Exception:
            pass

        try:
            if not response or not response.strip():
                raise ValueError("AI 返回了空响应")

            # 清理 JSON 字符串
            json_str = self._clean_json_string(response)

            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                # 无论是否截断都尝试修复（LLM 输出的 JSON 可能有格式问题）
                data = self._repair_truncated_json(json_str)

            # 构建维度结果
            dimensions = []
            for dim in data.get('dimensions', []):
                dimensions.append(AnalysisDimension(
                    dimension=dim.get('dimension', ''),
                    indicators=dim.get('indicators', []),
                    summary=dim.get('summary', ''),
                    severity=dim.get('severity', 'low')
                ))

            # 构建快速扫视结果
            qs = data.get('quick_scan', {})
            quick_scan = QuickScanResult(
                anomalies=qs.get('anomalies', []),
                core_projects=qs.get('core_projects', []),
                black_holes=qs.get('black_holes', []),
                action_items=qs.get('action_items', [])
            )

            summary_text = data.get('executive_summary', '')
            if truncated:
                summary_text += "\n\n⚠️ 注意：AI 响应因 token 限制被截断，部分分析结果可能不完整。"

            return AIInsightResult(
                dimensions=dimensions,
                quick_scan=quick_scan,
                executive_summary=summary_text,
                recommendations=data.get('recommendations', []),
                raw_response=response
            )

        except (json.JSONDecodeError, ValueError) as e:
            error_msg = f"AI 分析完成，但响应格式异常: {str(e)}"
            if truncated:
                error_msg = (
                    f"AI 响应因 token 限制被截断导致 JSON 不完整。"
                    f"当前 max_tokens={self.ai_config.max_tokens}，"
                    f"可在 config/employees.yaml 中增大此值。\n原始错误: {str(e)}"
                )
            error_msg += "\n\n原始响应已保存到 output/ai_raw_response.txt，可用于调试。"
            return AIInsightResult(
                dimensions=[],
                quick_scan=QuickScanResult(),
                executive_summary=error_msg,
                recommendations=[],
                raw_response=response
            )

    def _repair_truncated_json(self, json_str: str) -> Dict:
        """
        尝试修复被截断的 JSON 字符串

        策略：逐步去掉尾部字符，补全括号，直到 JSON 合法
        """
        # 去掉尾部不完整的字符串值（如果截断在字符串中间）
        # 找到最后一个完整的键值对
        # 尝试多种修复策略
        for trim in range(min(500, len(json_str))):
            candidate = json_str[:len(json_str) - trim] if trim > 0 else json_str
            # 统计未闭合的括号
            open_braces = candidate.count('{') - candidate.count('}')
            open_brackets = candidate.count('[') - candidate.count(']')

            # 确保不在字符串中间截断
            # 去掉尾部不完整的内容直到遇到逗号、括号或冒号
            stripped = candidate.rstrip()
            if stripped and stripped[-1] not in '{}[],:"0123456789tfn':
                continue

            # 清理尾部可能残留的逗号
            stripped = stripped.rstrip(',').rstrip()

            # 补全括号
            closing = ']' * max(0, open_brackets) + '}' * max(0, open_braces)
            try:
                repaired = stripped + closing
                return json.loads(repaired)
            except json.JSONDecodeError:
                continue

        raise json.JSONDecodeError("无法修复截断的 JSON", json_str, 0)

    def generate_quick_scan(
        self,
        df: pd.DataFrame,
        member_results: List,
        project_results: List,
        summary: Dict,
        period: str = "本周"
    ) -> QuickScanResult:
        """
        快速扫视分析（轻量级，不调用 API）

        用于实时展示，无需等待 API 响应
        """
        anomalies = []
        core_projects = []
        black_holes = []
        action_items = []

        # 检测工时异常
        for m in member_results:
            if m.standard_hours and m.standard_hours > 0:
                # 使用调整后的标准工时（已考虑入职日期、节假日、请假）
                low_threshold = min(30, m.standard_hours * 0.75)
                if m.total_hours < low_threshold and m.type == "全职":
                    anomalies.append({
                        'type': '工时偏低',
                        'member': m.name,
                        'value': f'{m.total_hours}h（标准 {m.standard_hours}h）',
                        'concern': f'全职员工本周仅 {m.total_hours} 小时，标准工时为 {m.standard_hours} 小时'
                    })
                    action_items.append(f"关注 {m.name} 的工时情况，了解原因")
                elif m.total_hours > 60:
                    anomalies.append({
                        'type': '工时过高',
                        'member': m.name,
                        'value': f'{m.total_hours}h',
                        'concern': f'本周工时达 {m.total_hours} 小时，可能存在过度加班'
                    })
                    action_items.append(f"关注 {m.name} 的工作负荷，考虑资源调配")

        # 核心项目状态（取前3个项目）
        for p in project_results[:3]:
            status = "充足" if p.percentage >= 20 else "需关注"
            core_projects.append({
                'project': p.name[:30] + ('...' if len(p.name) > 30 else ''),
                'hours': p.total_hours,
                'percentage': f'{p.percentage:.1f}%',
                'status': status,
                'comment': f'{p.member_count}人参与' if status == "充足" else '投入占比较低'
            })

        # 黑洞时间检测
        df_period = df[df['周期类型'] == period].copy() if '周期类型' in df.columns else df.copy()
        total_hours = df_period['工时 h'].sum() if len(df_period) > 0 else 0

        black_hole_keywords = ['其他', '行政', '会议', '杂项', '临时', '未分类', '沟通']
        for keyword in black_hole_keywords:
            if '项目名称_清理' in df_period.columns:
                matching = df_period[
                    df_period['项目名称_清理'].str.contains(keyword, na=False)
                ]['工时 h'].sum()
            else:
                matching = 0

            if matching > 0:
                pct = matching / total_hours * 100 if total_hours > 0 else 0
                if pct >= 10:  # 超过 10% 视为需要关注
                    black_holes.append({
                        'category': keyword,
                        'hours': round(matching, 1),
                        'percentage': f'{pct:.1f}%',
                        'risk': '占比较高，建议细化分类或减少此类工作'
                    })

        return QuickScanResult(
            anomalies=anomalies,
            core_projects=core_projects,
            black_holes=black_holes,
            action_items=action_items
        )


def get_ai_analyzer(api_key: Optional[str] = None) -> Optional[AIAnalyzer]:
    """
    获取 AI 分析器实例

    如果 API Key 未配置或 anthropic 未安装，返回 None 而非抛出异常
    """
    if not ANTHROPIC_AVAILABLE:
        return None

    try:
        return AIAnalyzer(api_key)
    except (ValueError, ImportError):
        return None


def is_ai_available(api_key: Optional[str] = None) -> bool:
    """检查 AI 分析功能是否可用"""
    if not ANTHROPIC_AVAILABLE:
        return False

    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    return key is not None and len(key) > 0
