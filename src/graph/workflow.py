"""
Создание и настройка workflow для LangGraph.

Этот модуль определяет граф обработки пользовательских запросов с помощью узлов,
реализующих различные этапы: маршрутизацию, выбор отчета, анализ данных и генерацию финального ответа.
"""

import streamlit as st
from langgraph.graph import StateGraph, START, END
from src.models import AgentState
from src.services import AIService, DataService, SearchService
from src.graph.nodes import (
    RouterNode, ReportSelectorNode, WorkPlanNode, DrillingReportNode,
    MeasurementReportNode, GasUtilizationNode, DocumentationNode,
    GeneralNode, ResponseGeneratorNode
)
from src.graph.edges import route_question, route_after_selection


@st.cache_resource
def create_workflow():
    """
    Создаёт и компилирует LangGraph workflow на основе состояния пользователя (AgentState).

    Структура графа:
        - START → router → [report_selector | general | documentation]
        - report_selector → [work_plan | drilling_report | measurement_report | gas_utilization | general]
        - Все узлы → response_generator → END

    Узлы:
        - router: Определяет тип запроса (общий, документация, отчеты)
        - report_selector: Возвращает интерфейс для выбора отчета
        - work_plan: Анализирует планы работы
        - drilling_report: Обрабатывает шахматки бурения
        - measurement_report: Анализирует замерную добычу
        - gas_utilization: Анализирует утилизацию газа
        - general: Обрабатывает общие вопросы
        - documentation: Ищет ответы в документации
        - response_generator: Финализирует результат

    Возвращает:
        Скомпилированный LangGraph workflow, готовый к запуску.
    """

    ai_service = AIService()
    data_service = DataService()
    search_service = SearchService()

    workflow = StateGraph(AgentState)

    router_node = RouterNode(ai_service, search_service)
    report_selector_node = ReportSelectorNode(ai_service)
    work_plan_node = WorkPlanNode(ai_service, data_service)
    drilling_report_node = DrillingReportNode(ai_service, data_service)
    measurement_report_node = MeasurementReportNode(ai_service, data_service)
    gas_utilization_node = GasUtilizationNode(ai_service, data_service)
    documentation_node = DocumentationNode(ai_service, search_service)
    general_node = GeneralNode(ai_service)
    response_generator_node = ResponseGeneratorNode(ai_service)

    workflow.add_node("router", router_node)
    workflow.add_node("report_selector", report_selector_node)
    workflow.add_node("work_plan", work_plan_node)
    workflow.add_node("drilling_report", drilling_report_node)
    workflow.add_node("measurement_report", measurement_report_node)
    workflow.add_node("gas_utilization", gas_utilization_node)
    workflow.add_node("general", general_node)
    workflow.add_node("documentation", documentation_node)
    workflow.add_node("response_generator", response_generator_node)

    workflow.add_edge(START, "router")

    workflow.add_conditional_edges(
        "router",
        route_question,
        {
            "report_selector": "report_selector",
            "general": "general",
            "documentation": "documentation"
        }
    )

    workflow.add_conditional_edges(
        "report_selector",
        route_after_selection,
        {
            "work_plan": "work_plan",
            "drilling_report": "drilling_report",
            "measurement_report": "measurement_report",
            "gas_utilization": "gas_utilization",
            "general": "general"
        }
    )

    workflow.add_edge("work_plan", "response_generator")
    workflow.add_edge("drilling_report", "response_generator")
    workflow.add_edge("measurement_report", "response_generator")
    workflow.add_edge("gas_utilization", "response_generator")

    workflow.add_edge("general", "response_generator")
    workflow.add_edge("documentation", "response_generator")

    workflow.add_edge("response_generator", END)

    return workflow.compile()