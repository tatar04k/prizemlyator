"""Основное Streamlit приложение"""
import streamlit as st
import uuid
from config import config
from src.services import AIService, DataService, SearchService
from src.graph import create_workflow
from src.ui.components import (
    render_header, render_chat_history, render_report_selector,
    display_result, cleanup_old_plots
)
from src.ui.utils import initialize_session_state


def main():
    """
    Главная функция приложения Streamlit.
    
    Выполняет:
    - Настройку интерфейса
    - Инициализацию модели, данных, подключения к Elasticsearch
    - Отображение истории чата и поля ввода
    - Обработку пользовательского ввода через LangGraph
    """

    st.set_page_config(
        page_title=config.PAGE_TITLE,
        page_icon=config.PAGE_ICON,
        layout=config.LAYOUT
    )

    render_header()

    cleanup_old_plots(max_files=config.MAX_PLOT_FILES)

    initialize_session_state()

    if "model_loaded" not in st.session_state:
        with st.spinner("Загружаю модель ИИ..."):
            ai_service = AIService()
            ai_service.get_pipe()  # Загружаем модель
            st.session_state.model_loaded = True

    if "es_connection_checked" not in st.session_state:
        with st.spinner("Проверяю подключение к базе данных..."):
            search_service = SearchService()
            search_service.get_client()
            st.session_state.es_connection_checked = True

    if "data_loaded" not in st.session_state:
        with st.spinner("Загрузка данных..."):
            data_service = DataService()
            df, message = data_service.load_work_plan_data()
            st.session_state.data_loaded = True
            st.success(message)

    render_chat_history()

    if st.session_state.waiting_for_report_selection and st.session_state.current_state:
        render_report_selector()
        return

    prompt = st.chat_input(
        "Задайте вопрос о нефтегазовой отрасли...",
        disabled=st.session_state.waiting_for_report_selection
    )

    if prompt and not st.session_state.waiting_for_report_selection:
        handle_user_input(prompt)


def handle_user_input(prompt: str):
    """
    Обрабатывает текст, введённый пользователем в чат.
    
    Аргументы:
        prompt (str): Вопрос/команда от пользователя.
    
    Действия:
    - Сохраняет сообщение
    - Отображает его в UI
    - Создаёт граф LangGraph и начальное состояние
    - Выполняет маршрутизацию запроса
    """
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("🧠 Анализирую ваш запрос..."):
            graph = create_workflow()

            initial_state = {
                "user_input": prompt,
                "route_decision": "",
                "response": "",
                "summary_type": "",
                "analysis_code": "",
                "analysis_result": "",
                "plot_path": "",
                "report_options": [],
                "selected_report": "",
                "waiting_for_selection": False,
                "generated_data": {}
            }

            from src.services import AIService, SearchService
            ai_service = AIService()
            search_service = SearchService()

            from src.graph.nodes import RouterNode
            router_node = RouterNode(ai_service, search_service)
            router_result = router_node(initial_state)

            process_router_result(router_result, graph, initial_state)


def process_router_result(router_result, graph, initial_state):
    """
    Обрабатывает результат от роутера (определение типа запроса) и запускает соответствующую ветку обработки.
    
    Аргументы:
        router_result (dict): Состояние после выполнения RouterNode.
        graph (LangGraph): Скомпилированный workflow.
        initial_state (dict): Начальное состояние перед запуском графа.
    
    Обрабатывает:
    - Общие вопросы
    - Документационные запросы
    - Отчётные запросы с выбором
    - Запросы без отчётного выбора (выполняются сразу)
    """
    if router_result.get("route_decision") == "general":
        st.info("💭 Определен как общий вопрос")
        final_state = graph.invoke(initial_state)
        display_result(final_state)

    elif router_result.get("route_decision") == "documentation":
        st.info("📚 Определен как запрос документации. Ищу в базе знаний...")
        final_state = graph.invoke(initial_state)
        display_result(final_state)

    elif router_result.get("waiting_for_selection", False) and router_result.get("report_options"):
        if router_result.get("route_decision") == "elasticsearch_based":
            st.info("📊 Определен как запрос на анализ отчетов. Найдены релевантные отчеты.")
        else:
            st.info("📊 Определен как запрос на анализ отчетов. Показываю все доступные отчеты.")

        st.session_state.waiting_for_report_selection = True
        st.session_state.current_state = router_result
        st.session_state.current_graph = graph

        if router_result.get("route_decision") == "elasticsearch_based":
            st.markdown("Я нашел релевантные отчеты для вашего запроса. Выберите подходящие:")
        else:
            st.markdown("Я не нашел точного соответствия в базе, но вот все доступные отчеты. Выберите подходящие:")

        st.rerun()
    else:
        final_state = graph.invoke(initial_state)
        display_result(final_state)


if __name__ == "__main__":
    main()