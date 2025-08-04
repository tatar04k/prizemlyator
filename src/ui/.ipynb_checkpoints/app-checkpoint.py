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
    """Главная функция приложения"""
    # Настройка страницы
    st.set_page_config(
        page_title=config.PAGE_TITLE,
        page_icon=config.PAGE_ICON,
        layout=config.LAYOUT
    )

    # Отображаем заголовок
    render_header()

    # Очищаем старые графики
    cleanup_old_plots(max_files=config.MAX_PLOT_FILES)

    # Инициализация сессии
    initialize_session_state()

    # Загрузка модели и данных при первом запуске
    if "model_loaded" not in st.session_state:
        with st.spinner("Загружаю модель ИИ..."):
            ai_service = AIService()
            ai_service.get_pipe()  # Загружаем модель
            st.session_state.model_loaded = True

    # Проверка подключения к Elasticsearch
    if "es_connection_checked" not in st.session_state:
        with st.spinner("Проверяю подключение к базе данных..."):
            search_service = SearchService()
            search_service.get_client()
            st.session_state.es_connection_checked = True

    # Инициализация данных
    if "data_loaded" not in st.session_state:
        with st.spinner("Загрузка данных..."):
            data_service = DataService()
            df, message = data_service.load_work_plan_data()
            st.session_state.data_loaded = True
            st.success(message)

    # Отображение истории чата
    render_chat_history()

    # Обработка выбора отчета если ожидается
    if st.session_state.waiting_for_report_selection and st.session_state.current_state:
        render_report_selector()
        return

    # Поле ввода сообщения
    prompt = st.chat_input(
        "Задайте вопрос о нефтегазовой отрасли...",
        disabled=st.session_state.waiting_for_report_selection
    )

    if prompt and not st.session_state.waiting_for_report_selection:
        handle_user_input(prompt)


def handle_user_input(prompt: str):
    """Обрабатывает ввод пользователя"""
    # Добавляем сообщение пользователя
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # Генерируем ответ
    with st.chat_message("assistant"):
        with st.spinner("🧠 Анализирую ваш запрос..."):
            # Создаем граф и начальное состояние
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

            # Выполняем роутер для определения типа запроса
            from src.services import AIService, SearchService
            ai_service = AIService()
            search_service = SearchService()

            from src.graph.nodes import RouterNode
            router_node = RouterNode(ai_service, search_service)
            router_result = router_node(initial_state)

            # Обрабатываем результат роутинга
            process_router_result(router_result, graph, initial_state)


def process_router_result(router_result, graph, initial_state):
    """Обрабатывает результат роутинга"""
    if router_result.get("route_decision") == "general":
        st.info("💭 Определен как общий вопрос")
        final_state = graph.invoke(initial_state)
        display_result(final_state)

    elif router_result.get("route_decision") == "documentation":
        st.info("📚 Определен как запрос документации. Ищу в базе знаний...")
        final_state = graph.invoke(initial_state)
        display_result(final_state)

    elif router_result.get("waiting_for_selection", False) and router_result.get("report_options"):
        # Показываем информацию о найденных отчетах
        if router_result.get("route_decision") == "elasticsearch_based":
            st.info("📊 Определен как запрос на анализ отчетов. Найдены релевантные отчеты.")
        else:
            st.info("📊 Определен как запрос на анализ отчетов. Показываю все доступные отчеты.")

        # Сохраняем состояние для обработки выбора
        st.session_state.waiting_for_report_selection = True
        st.session_state.current_state = router_result
        st.session_state.current_graph = graph

        # Показываем сообщение о выборе
        if router_result.get("route_decision") == "elasticsearch_based":
            st.markdown("Я нашел релевантные отчеты для вашего запроса. Выберите подходящие:")
        else:
            st.markdown("Я не нашел точного соответствия в базе, но вот все доступные отчеты. Выберите подходящие:")

        st.rerun()
    else:
        # Неожиданная ситуация - выполняем полный граф
        final_state = graph.invoke(initial_state)
        display_result(final_state)


if __name__ == "__main__":
    main()