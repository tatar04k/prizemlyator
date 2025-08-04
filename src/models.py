"""Модели данных и состояний для OIS-GPT"""
from typing import TypedDict, Literal, List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

class AgentState(TypedDict):
    """
    Состояние агента LangGraph, передаваемое между узлами графа.

    Поля:
        user_input: Исходный запрос пользователя.
        route_decision: Тип маршрута (general, documentation, report).
        response: Финальный текстовый ответ.
        summary_type: Тип итогового анализа или категории ответа.
        analysis_code: Сгенерированный Python-код.
        analysis_result: Результаты выполнения кода.
        plot_path: Путь к сгенерированному графику.
        report_options: Список найденных/возможных отчетов.
        selected_report: ID выбранного отчета (если применимо).
        waiting_for_selection: Флаг ожидания выбора пользователем.
        generated_data: Дополнительные промежуточные данные.
    """
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

@dataclass
class ReportOption:
    """
    Модель одного отчета для выбора пользователем.
    """
    id: str
    title: str
    description: str

@dataclass
class SearchResult:
    """
    Результат поиска в Elasticsearch.
    """
    id: str
    score: float
    title: str
    description: str
    tags: List[str]

@dataclass
class DocumentResult:
    """
    Релевантный документ, найденный в базе документации.
    """
    score: float
    content: str

@dataclass
class QueueItem:
    """
    Элемент в очереди обработки запроса.

    Атрибуты:
        request_id: Уникальный идентификатор запроса.
        session_id: Идентификатор пользовательской сессии.
        timestamp: Время постановки в очередь.
        request_data: Данные запроса (тип, параметры и т.д.).
        status: Текущий статус (waiting, processing, completed, error).
    """
    request_id: str
    session_id: str
    timestamp: datetime
    request_data: Dict
    status: str

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

RouteDecision = Literal["reports_analysis", "documentation_search", "general_question"]
NodeType = Literal["work_plan", "drilling_report", "measurement_report", "gas_utilization", "general", "documentation"]

@dataclass
class AnalysisResult:
    """
    Результат выполнения анализа.

    Атрибуты:
        code: Выполненный Python-код.
        result_text: Текст с результатами анализа.
        plot_path: Путь к графику, если был создан.
        summary_type: Тип анализа или категория ответа.
        error: Сообщение об ошибке, если возникла.
    """
    code: str
    result_text: str
    plot_path: Optional[str] = None
    summary_type: str = ""
    error: Optional[str] = None