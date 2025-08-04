"""UI компоненты для Streamlit приложения"""
import streamlit as st
import os
import hashlib
from typing import List, Dict, Any
from src.constants import REPORT_ICONS
from src.ui.utils import render_response_with_latex


def render_header():
    """
    Отображает заголовок приложения в стиле с иконкой и названием.
    """
    st.markdown("""
    <div style="display: flex; align-items: center; margin-bottom: 2rem;">
        <div style="background: #ff6b6b; border-radius: 8px; padding: 8px; margin-right: 12px;">
            <span style="color: white; font-size: 20px;">🤖</span>
        </div>
        <h1 style="margin: 0; color: #333;">OIS-GPT</h1>
    </div>
    """, unsafe_allow_html=True)


def render_chat_history():
    """
    Отображает историю чата из `st.session_state.messages`, включая:
    - Вопросы пользователя
    - Ответы ИИ с форматированием
    - Графики, код анализа и текстовые результаты
    """

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant" and "summary_type" in message:
                st.markdown(f"**{message['summary_type']}**")

            if message["role"] == "assistant":
                render_response_with_latex(message["content"])
            else:
                st.markdown(message["content"])

            if message["role"] == "assistant" and "plot_path" in message and message["plot_path"]:
                try:
                    if os.path.exists(message["plot_path"]):
                        st.image(message["plot_path"], caption="Результат анализа данных")
                except:
                    pass

            if message["role"] == "assistant" and "analysis_code" in message and message["analysis_code"]:
                with st.expander("Показать код анализа"):
                    st.code(message["analysis_code"], language="python")

            if message["role"] == "assistant" and "analysis_result" in message and message["analysis_result"]:
                with st.expander("Показать результаты анализа"):
                    st.text(message["analysis_result"])


def render_report_selector():
    """
    Отображает интерфейс выбора отчетов пользователем:
    - Список чекбоксов для выбора
    - Кнопка запуска анализа
    - Информация о типе маршрутизации
    - Сообщения при отсутствии результатов
    
    Если пользователь выбирает отчеты, инициируется `process_report_selection`.
    """
    st.markdown("---")

    current_state = st.session_state.current_state
    report_count = len(current_state["report_options"])

    if report_count == 0:
        st.markdown("### ❌ Релевантные отчеты не найдены")
        st.markdown("В базе данных Elasticsearch не найдено отчетов, соответствующих вашему запросу.")
        st.markdown("Попробуйте переформулировать вопрос или обратитесь к администратору.")

        if st.button("🔄 Задать общий вопрос"):
            st.session_state.waiting_for_report_selection = False
            st.session_state.current_state = None
            st.session_state.current_graph = None
            st.rerun()
        return

    if current_state.get("route_decision") == "elasticsearch_based":
        st.markdown(f"### 📊 Найдено {report_count} релевантных отчетов:")
        st.markdown("*Отчеты упорядочены по релевантности к вашему запросу*")
    elif current_state.get("route_decision") == "all_reports_fallback":
        st.markdown(f"### 📊 Доступные отчеты для анализа:")
        st.markdown("*Точного соответствия не найдено. Выберите подходящий тип анализа:*")
    else:
        st.markdown(f"### 📊 Найдено {report_count} отчетов:")

    selected_options = []

    if report_count == 1:
        col1, col2, col3 = st.columns([1, 2, 1])
        columns = [col2]
    elif report_count == 2:
        col1, col2 = st.columns(2)
        columns = [col1, col2]
    else:
        col1, col2 = st.columns(2)
        columns = [col1, col2]

    for i, option in enumerate(current_state["report_options"]):
        icon = REPORT_ICONS.get(option["id"], "📊")
        target_col = columns[i % len(columns)]

        with target_col:
            relevance_indicator = ""
            if i == 0:
                relevance_indicator = " 1️⃣"
            elif i == 1:
                relevance_indicator = " 2️⃣"
            elif i == 2:
                relevance_indicator = " 3️⃣"

            state_hash = hashlib.md5(str(current_state["report_options"]).encode()).hexdigest()[:8]
            checkbox_key = f"report_check_{option['id']}_{i}_{state_hash}"
            checkbox_label = f"{icon} {option['title']}{relevance_indicator}"

            if st.checkbox(checkbox_label, key=checkbox_key):
                selected_options.append(option["id"])

            st.caption(option["description"])

            if i < len(current_state["report_options"]) - 1:
                st.markdown("")

    if st.button("🚀 Анализировать выбранные отчеты", disabled=len(selected_options) == 0):
        st.session_state.selected_reports = selected_options
        st.session_state.process_selection = True

    if st.session_state.get("process_selection", False) and st.session_state.selected_reports:
        process_report_selection()


def process_report_selection():
    """
    Обрабатывает выбранные пользователем отчеты:
    - Декомпозирует исходный вопрос на частные запросы
    - Выполняет граф анализа для каждого отчета
    - Отображает результаты по каждому или формирует сводный анализ
    - Сохраняет результаты в историю
    
    После выполнения очищает временное состояние выбора.
    """
    with st.chat_message("assistant"):
        from src.services import AIService
        ai_service = AIService()

        with st.spinner("🧠 Анализирую ваш вопрос и адаптирую его под каждый отчет..."):
            original_query = st.session_state.current_state.get("user_input", "")
            specific_queries = ai_service.decompose_query_for_reports(
                original_query,
                st.session_state.selected_reports
            )

        st.markdown("### 🔍 Адаптированные вопросы для каждого отчета:")
        for i, report_id in enumerate(st.session_state.selected_reports, 1):
            from src.models import PREDEFINED_REPORTS
            report_name = next((opt["title"] for opt in PREDEFINED_REPORTS if opt["id"] == report_id), report_id)
            specific_query = specific_queries.get(report_id, original_query)

            if specific_query != original_query:
                st.markdown(f"**{i}. {report_name}:** _{specific_query}_ ✨")
            else:
                st.markdown(f"**{i}. {report_name}:** _{specific_query}_")

        st.markdown("---")

        all_final_states = []

        for i, report_id in enumerate(st.session_state.selected_reports):
            specific_query = specific_queries.get(report_id, original_query)
            report_name = next((opt["title"] for opt in PREDEFINED_REPORTS if opt["id"] == report_id), report_id)

            with st.spinner(f"Обрабатываю {report_name} ({i + 1}/{len(st.session_state.selected_reports)})..."):
                report_state = st.session_state.current_state.copy()
                report_state["selected_report"] = report_id
                report_state["waiting_for_selection"] = False
                report_state["user_input"] = specific_query

                graph = st.session_state.current_graph
                final_state = graph.invoke(report_state)

                final_state["original_user_input"] = original_query
                final_state["specific_user_input"] = specific_query
                all_final_states.append(final_state)

        if len(all_final_states) > 1:
            st.markdown("## 🎯 Сводный анализ по всем отчетам:")

            combined_summary = ai_service.generate_combined_analysis(
                all_final_states,
                st.session_state.selected_reports,
                original_query
            )
            render_response_with_latex(combined_summary)

            st.session_state.messages.append({
                "role": "assistant",
                "content": combined_summary,
                "summary_type": "Сводный анализ",
                "analysis_code": "",
                "analysis_result": "",
                "plot_path": ""
            })
        else:
            final_state = all_final_states[0]
            display_single_report_result(final_state, ai_service)

        st.session_state.waiting_for_report_selection = False
        st.session_state.current_state = None
        st.session_state.current_graph = None
        st.session_state.process_selection = False
        st.session_state.selected_reports = []


def display_single_report_result(final_state: Dict[str, Any], ai_service):
    """
    Отображает результат анализа для одного отчета:
    - Запрашивает финальный ответ через очередь
    - Отображает график (если есть)
    - Выводит итоговый текст ответа
    - Сохраняет сообщение в чат-историю
    
    Аргументы:
        final_state (dict): Состояние после анализа одного отчета
        ai_service (AIService): Сервис для генерации ответов
    """
    from src.services.queue_service import queue_aware_generation

    session_id = st.session_state.get('session_id', 'default')

    with st.spinner("💭 Формирую итоговый ответ..."):
        final_response = queue_aware_generation(session_id, 'generate_final_response', {
            'state': final_state
        })

    if final_state.get("plot_path") and os.path.exists(final_state["plot_path"]):
        try:
            st.image(final_state["plot_path"], caption="Результат анализа данных")
        except Exception as e:
            st.warning(f"Не удалось отобразить график: {str(e)}")

    render_response_with_latex(final_response)

    st.session_state.messages.append({
        "role": "assistant",
        "content": final_response,
        "summary_type": final_state["summary_type"],
        "analysis_code": final_state.get("analysis_code", ""),
        "analysis_result": final_state.get("analysis_result", ""),
        "plot_path": final_state.get("plot_path", "")
    })


def display_result(final_state: Dict[str, Any]):
    """
    Отображает результат анализа по типу маршрута:
    - Общий вопрос → текст с LaTeX
    - Документация → ответ и источники
    - Специализированные отчеты → ничего (результат уже обработан отдельно)
    
    Аргументы:
        final_state (dict): Финальное состояние графа
    """
    if final_state["route_decision"] == "general":
        render_response_with_latex(final_state["response"])

    elif final_state["route_decision"] == "documentation":
        st.markdown("### 📚 Информация из документации:")
        render_response_with_latex(final_state["response"])

        doc_results = final_state.get("doc_results", [])
        if doc_results:
            with st.expander(f"📄 Источники ({len(doc_results)} документов)", expanded=False):
                for i, doc in enumerate(doc_results, 1):
                    st.markdown(f"**Документ {i} (релевантность: {doc['score']:.2f})**")
                    preview = doc['content'][:500] + "..." if len(doc['content']) > 500 else doc['content']
                    st.text(preview)
                    st.markdown("---")

    else:
        return

    st.session_state.messages.append({
        "role": "assistant",
        "content": final_state["response"],
        "summary_type": final_state.get("summary_type", ""),
        "analysis_code": final_state.get("analysis_code", ""),
        "analysis_result": final_state.get("analysis_result", ""),
        "plot_path": final_state.get("plot_path", "")
    })


def cleanup_old_plots(max_files: int = 50):
    """
    Удаляет устаревшие PNG-файлы графиков, если их число превышает `max_files`.
    
    Аргументы:
        max_files (int): Максимально допустимое количество графиков.
    """
    try:
        plot_files = [f for f in os.listdir('.') if f.startswith('plot_') and f.endswith('.png')]

        if len(plot_files) > max_files:
            plot_files.sort(key=lambda x: os.path.getctime(x))
            files_to_delete = plot_files[:-max_files]
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    print(f"Удален старый файл графика: {file_path}")
                except:
                    pass
    except Exception as e:
        print(f"Ошибка при очистке старых графиков: {str(e)}")