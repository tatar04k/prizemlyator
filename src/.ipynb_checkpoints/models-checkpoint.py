"""Модели данных и состояний для OIS-GPT"""
from typing import TypedDict, Literal, List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

# LangGraph State
class AgentState(TypedDict):
    user_input: str
    route_decision: str
    response: str
    summary_type: str
    analysis_code: str
    analysis_result: str
    plot_path: str
    report_options: List[Dict[str, str]]
    selected_report: str
    waiting_for_selection: bool
    generated_data: Dict

# Report Models
@dataclass
class ReportOption:
    id: str
    title: str
    description: str

@dataclass
class SearchResult:
    id: str
    score: float
    title: str
    description: str
    tags: List[str]

@dataclass
class DocumentResult:
    score: float
    content: str

@dataclass
class QueueItem:
    request_id: str
    session_id: str
    timestamp: datetime
    request_data: Dict
    status: str

# Predefined Reports
PREDEFINED_REPORTS = [
    {"id": "work_plan", "title": "План работы на промыслах",
     "description": "Анализ планов работы, ремонта скважин и добычи нефти"},
    {"id": "drilling_report", "title": "Шахматка проб по плотности и КВЧ",
     "description": "Отчеты по бурению, плотности растворов и коэффициенту восстановления циркуляции"},
    {"id": "measurement_report", "title": "Отчёт по замерной добыче за период",
     "description": "Анализ замерной добычи, дебитов скважин и обводненности"},
    {"id": "gas_utilization", "title": "Отчёт о выполнении утилизации газа",
     "description": "Анализ утилизации попутного газа и эффективности газоперерабатывающих установок"}
]

# Route Types
RouteDecision = Literal["reports_analysis", "documentation_search", "general_question"]
NodeType = Literal["work_plan", "drilling_report", "measurement_report", "gas_utilization", "general", "documentation"]

# Analysis Types
@dataclass
class AnalysisResult:
    code: str
    result_text: str
    plot_path: Optional[str] = None
    summary_type: str = ""
    error: Optional[str] = None