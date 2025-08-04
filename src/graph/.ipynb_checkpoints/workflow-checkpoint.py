"""Создание и конфигурация LangGraph workflow"""
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
    """Создает и возвращает скомпилированный LangGraph workflow"""

    # Инициализируем сервисы
    ai_service = AIService()
    data_service = DataService()
    search_service = SearchService()

    # Создаем граф
    workflow = StateGraph(AgentState)

    # Создаем узлы с зависимостями
    router_node = RouterNode(ai_service, search_service)
    report_selector_node = ReportSelectorNode(ai_service)
    work_plan_node = WorkPlanNode(ai_service, data_service)
    drilling_report_node = DrillingReportNode(ai_service, data_service)
    measurement_report_node = MeasurementReportNode(ai_service, data_service)
    gas_utilization_node = GasUtilizationNode(ai_service, data_service)
    documentation_node = DocumentationNode(ai_service, search_service)
    general_node = GeneralNode(ai_service)
    response_generator_node = ResponseGeneratorNode(ai_service)

    # Добавляем узлы в граф
    workflow.add_node("router", router_node)
    workflow.add_node("report_selector", report_selector_node)
    workflow.add_node("work_plan", work_plan_node)
    workflow.add_node("drilling_report", drilling_report_node)
    workflow.add_node("measurement_report", measurement_report_node)
    workflow.add_node("gas_utilization", gas_utilization_node)
    workflow.add_node("general", general_node)
    workflow.add_node("documentation", documentation_node)
    workflow.add_node("response_generator", response_generator_node)

    # Добавляем рёбра
    workflow.add_edge(START, "router")

    # После роутера идем к соответствующему узлу
    workflow.add_conditional_edges(
        "router",
        route_question,
        {
            "report_selector": "report_selector",
            "general": "general",
            "documentation": "documentation"
        }
    )

    # После выбора отчета переходим к соответствующему узлу обработки
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

    # Все специализированные узлы ведут к генератору ответа
    workflow.add_edge("work_plan", "response_generator")
    workflow.add_edge("drilling_report", "response_generator")
    workflow.add_edge("measurement_report", "response_generator")
    workflow.add_edge("gas_utilization", "response_generator")

    # Общий узел и документация ведут к генератору ответа
    workflow.add_edge("general", "response_generator")
    workflow.add_edge("documentation", "response_generator")

    # Генератор ответа ведет к концу
    workflow.add_edge("response_generator", END)

    return workflow.compile()