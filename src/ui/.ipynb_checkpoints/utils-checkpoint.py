"""Утилиты для UI"""
import streamlit as st
import re
import uuid
from src.constants import GREEK_LETTER_MAP, SUPERSCRIPT_MAP


def initialize_session_state():
    """Инициализирует состояние сессии"""
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Привет! Я готов помочь с анализом данных по нефтегазовой отрасли. Задавай вопросы о планах работы, бурении, замерной добыче или утилизации газа! 😊"
        })

    if "waiting_for_report_selection" not in st.session_state:
        st.session_state.waiting_for_report_selection = False
        st.session_state.current_state = None
        st.session_state.current_graph = None
        st.session_state.process_selection = False
        st.session_state.selected_reports = []


def strip_latex_from_text(text: str) -> str:
    """Очищает текст от LaTeX разметки"""
    # \text{...} → просто текст
    text = re.sub(r'\\text\{([^}]+)\}', r'\1', text)

    # \times 10^{...} → × 10ⁿ
    text = re.sub(r'\\times\s*10\^{(-?\d+)}', lambda m: f"× 10{_superscript(m.group(1))}", text)

    # \times без степени → просто ×
    text = re.sub(r'\\times', '×', text)

    # 10^{...} → 10ⁿ
    text = re.sub(r'10\^\{(-?\d+)\}', lambda m: f"10{_superscript(m.group(1))}", text)

    # Преобразуем единицы: м^2, см^3 → м², см³
    text = re.sub(r'([мМmсС])\^2', r'\1²', text)
    text = re.sub(r'([мМmсС])\^3', r'\1³', text)

    # Убираем \( ... \)
    text = re.sub(r'\\\((.*?)\\\)', r'\1', text)

    # Замена \mu и прочего на символы
    text = re.sub(r'\\(mu|phi|Delta|alpha|beta|lambda|sigma|gamma|theta|rho)',
                  lambda m: GREEK_LETTER_MAP.get(m.group(1), m.group(0)), text)

    return text


def _superscript(digits: str) -> str:
    """Преобразует цифры в верхний индекс"""
    return digits.translate(SUPERSCRIPT_MAP)


def render_response_with_latex(response_text: str):
    """
    Универсальный рендер ответа с поддержкой:
    - Формул в $$...$$
    - Формул в \begin{align}...\end{align}
    - Очисткой текста от мусора LaTeX
    """
    # Паттерны
    block_pattern = r'\$\$([^$]+?)\$\$'
    align_pattern = r'\\begin\{align\}(.*?)\\end\{align\}'

    matches = []

    for m in re.finditer(block_pattern, response_text, re.DOTALL):
        matches.append({
            'start': m.start(),
            'end': m.end(),
            'content': m.group(1).strip(),
            'type': 'latex'
        })

    for m in re.finditer(align_pattern, response_text, re.DOTALL):
        matches.append({
            'start': m.start(),
            'end': m.end(),
            'content': f"\\begin{{align}}\n{m.group(1).strip()}\n\\end{{align}}",
            'type': 'align'
        })

    matches.sort(key=lambda m: m['start'])

    last = 0
    for m in matches:
        # Выводим текст до формулы (очищенный)
        if m['start'] > last:
            text_chunk = response_text[last:m['start']]
            cleaned = strip_latex_from_text(text_chunk).strip()
            if cleaned:
                st.markdown(cleaned)

        # Формула
        try:
            st.latex(m['content'])
        except Exception:
            st.code(f"[LaTeX ошибка] {m['content']}")

        last = m['end']

    # Выводим оставшийся текст
    if last < len(response_text):
        remaining = strip_latex_from_text(response_text[last:]).strip()
        if remaining:
            st.markdown(remaining)


def format_message_content(message_content: str, message_type: str = "text") -> str:
    """Форматирует содержимое сообщения в зависимости от типа"""
    if message_type == "code":
        return f"```python\n{message_content}\n```"
    elif message_type == "error":
        return f"❌ **Ошибка:** {message_content}"
    elif message_type == "success":
        return f"✅ **Успех:** {message_content}"
    elif message_type == "info":
        return f"ℹ️ **Информация:** {message_content}"
    elif message_type == "warning":
        return f"⚠️ **Предупреждение:** {message_content}"
    else:
        return message_content


def create_status_indicator(status: str) -> str:
    """Создает индикатор статуса"""
    status_icons = {
        "processing": "🔄",
        "completed": "✅",
        "error": "❌",
        "waiting": "⏳",
        "queued": "📋"
    }

    status_colors = {
        "processing": "#1f77b4",
        "completed": "#2ca02c",
        "error": "#d62728",
        "waiting": "#ff7f0e",
        "queued": "#9467bd"
    }

    icon = status_icons.get(status, "⚪")
    color = status_colors.get(status, "#666666")

    return f'<span style="color: {color}">{icon} {status.title()}</span>'


def format_file_size(size_bytes: int) -> str:
    """Форматирует размер файла в человекочитаемый вид"""
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Обрезает текст до указанной длины"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def validate_user_input(user_input: str) -> tuple[bool, str]:
    """Валидирует пользовательский ввод"""
    if not user_input or not user_input.strip():
        return False, "Пустой запрос"

    if len(user_input.strip()) < 3:
        return False, "Слишком короткий запрос (минимум 3 символа)"

    if len(user_input) > 1000:
        return False, "Слишком длинный запрос (максимум 1000 символов)"

    # Проверка на потенциально вредоносный контент
    dangerous_patterns = [
        r'<script.*?>',
        r'javascript:',
        r'eval\s*\(',
        r'exec\s*\('
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, user_input, re.IGNORECASE):
            return False, "Запрос содержит потенциально опасный контент"

    return True, "OK"


def create_progress_indicator(current: int, total: int, prefix: str = "") -> str:
    """Создает индикатор прогресса"""
    if total == 0:
        return f"{prefix} ⏳ Ожидание..."

    percentage = int((current / total) * 100)
    filled_length = int((current / total) * 20)  # 20 символов для полосы

    bar = "█" * filled_length + "░" * (20 - filled_length)

    return f"{prefix} {bar} {percentage}% ({current}/{total})"


def format_duration(seconds: float) -> str:
    """Форматирует продолжительность в человекочитаемый вид"""
    if seconds < 1:
        return f"{int(seconds * 1000)}мс"
    elif seconds < 60:
        return f"{seconds:.1f}с"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}м {secs}с"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}ч {minutes}м"


def create_expandable_section(title: str, content: str, expanded: bool = False) -> None:
    """Создает раскрывающуюся секцию"""
    with st.expander(title, expanded=expanded):
        st.write(content)


def display_dataframe_summary(df, title: str = "Данные"):
    """Отображает краткую сводку по DataFrame"""
    if df is None or df.empty:
        st.warning(f"{title}: данные отсутствуют")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Строк", len(df))

    with col2:
        st.metric("Столбцов", len(df.columns))

    with col3:
        memory_usage = df.memory_usage(deep=True).sum()
        st.metric("Размер", format_file_size(memory_usage))

    # Показываем типы данных
    with st.expander(f"Подробнее о {title}", expanded=False):
        st.write("**Столбцы и типы данных:**")
        for col, dtype in df.dtypes.items():
            st.write(f"- `{col}`: {dtype}")


def create_download_button(data, filename: str, button_text: str = "Скачать"):
    """Создает кнопку для скачивания данных"""
    if isinstance(data, str):
        # Текстовые данные
        st.download_button(
            label=button_text,
            data=data,
            file_name=filename,
            mime="text/plain"
        )
    else:
        # DataFrame или другие данные
        if hasattr(data, 'to_csv'):
            csv_data = data.to_csv(index=False)
            st.download_button(
                label=button_text,
                data=csv_data,
                file_name=filename,
                mime="text/csv"
            )


def show_processing_spinner(message: str = "Обработка..."):
    """Показывает спиннер с сообщением"""
    return st.spinner(message)


def display_error_message(error: str, details: str = None):
    """Отображает сообщение об ошибке"""
    st.error(f"❌ {error}")

    if details:
        with st.expander("Подробности ошибки"):
            st.code(details)


def display_success_message(message: str, details: str = None):
    """Отображает сообщение об успехе"""
    st.success(f"✅ {message}")

    if details:
        with st.expander("Подробности"):
            st.info(details)


def create_info_box(title: str, content: str, box_type: str = "info"):
    """Создает информационный блок"""
    icons = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "❌",
        "success": "✅"
    }

    icon = icons.get(box_type, "ℹ️")

    st.markdown(f"""
    <div style="
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8f9fa;
        border-left: 4px solid #007bff;
        margin: 1rem 0;
    ">
        <h4 style="margin: 0 0 0.5rem 0;">{icon} {title}</h4>
        <p style="margin: 0;">{content}</p>
    </div>
    """, unsafe_allow_html=True)


def format_timestamp(timestamp) -> str:
    """Форматирует временную метку"""
    if hasattr(timestamp, 'strftime'):
        return timestamp.strftime("%d.%m.%Y %H:%M:%S")
    return str(timestamp)


def create_sidebar_info():
    """Создает информационную панель в сайдбаре"""
    with st.sidebar:
        st.markdown("### 📊 Информация о системе")

        st.markdown("""
        **OIS-GPT** - система анализа данных нефтегазовой отрасли

        **Возможности:**
        - 📋 Анализ планов работы
        - 🔧 Отчеты по бурению
        - ⚡ Замерная добыча
        - 🔥 Утилизация газа
        - 📚 Поиск в документации
        """)

        if st.button("🔄 Очистить историю"):
            st.session_state.messages = []
            st.session_state.messages.append({
                "role": "assistant",
                "content": "История очищена. Задавайте новые вопросы!"
            })
            st.rerun()


def highlight_keywords(text: str, keywords: list) -> str:
    """Подсвечивает ключевые слова в тексте"""
    for keyword in keywords:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        text = pattern.sub(f"**{keyword}**", text)
    return text


def create_metric_card(title: str, value: str, delta: str = None, delta_color: str = "normal"):
    """Создает карточку с метрикой"""
    st.metric(
        label=title,
        value=value,
        delta=delta,
        delta_color=delta_color
    )


def format_large_number(number: float) -> str:
    """Форматирует большие числа в удобочитаемый вид"""
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}М"
    elif number >= 1_000:
        return f"{number / 1_000:.1f}К"
    else:
        return f"{number:.1f}"


def create_tooltip(text: str, tooltip: str) -> str:
    """Создает текст с подсказкой"""
    return f'<span title="{tooltip}">{text}</span>'


def validate_file_upload(uploaded_file, allowed_types: list = None, max_size_mb: int = 50):
    """Валидирует загруженный файл"""
    if uploaded_file is None:
        return False, "Файл не выбран"

    # Проверка типа файла
    if allowed_types and uploaded_file.type not in allowed_types:
        return False, f"Неподдерживаемый тип файла. Разрешены: {', '.join(allowed_types)}"

    # Проверка размера файла
    if uploaded_file.size > max_size_mb * 1024 * 1024:
        return False, f"Файл слишком большой. Максимальный размер: {max_size_mb}MB"

    return True, "OK"


def create_column_selector(df, title: str = "Выберите столбцы"):
    """Создает селектор столбцов DataFrame"""
    if df is None or df.empty:
        st.warning("Данные отсутствуют")
        return []

    return st.multiselect(
        title,
        options=df.columns.tolist(),
        default=df.columns.tolist()[:3]  # По умолчанию первые 3 столбца
    )