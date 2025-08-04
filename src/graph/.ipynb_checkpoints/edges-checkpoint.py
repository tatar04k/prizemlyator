"""Условные переходы для LangGraph"""
from typing import Literal
from src.models import AgentState

def route_question(state: AgentState) -> Literal["report_selector", "general", "documentation"]:
    """
    Определяет следующий шаг на основе текущего состояния.

    Возвращает:
        - "general", если запрос относится к общей информации.
        - "documentation", если пользователь интересуется документацией.
        - "report_selector", если требуется выбор отчета и доступны варианты отчетов.
    """
    if state.get("route_decision") == "general":
        return "general"
    elif state.get("route_decision") == "documentation":
        return "documentation"
    elif state.get("waiting_for_selection", False) and state.get("report_options"):
        return "report_selector"
    else:
        return "report_selector"

def route_after_selection(state: AgentState) -> Literal["work_plan", "drilling_report", "measurement_report", "gas_utilization", "general"]:
    """
    Направляет обработку после выбора конкретного отчета пользователем.

    Возвращает:
        Название выбранного отчета (ключ в состоянии 'selected_report'),
        соответствующее одному из допустимых путей.
    """
    return state["selected_report"]