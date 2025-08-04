"""Узлы LangGraph для обработки различных типов запросов"""
import streamlit as st
import pandas as pd
from typing import Dict, List, Optional
from src.models import AgentState
from src.services import AIService, DataService, SearchService
from src.services.queue_service import queue_aware_generation
from src.constants import SYSTEM_PROMPTS, REPORT_DATA_DESCRIPTIONS
from src.utils.text_utils import execute_generated_code


class BaseNode:
    """Базовый класс для всех узлов LangGraph"""

    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service


class RouterNode(BaseNode):
    """Узел маршрутизации: определяет, как обрабатывать пользовательский запрос — общий, документационный или отчетный."""

    def __init__(self, ai_service: AIService, search_service: SearchService):
        super().__init__(ai_service)
        self.search_service = search_service

    def __call__(self, state: AgentState) -> AgentState:
        """
        Определяет, к какому типу относится пользовательский запрос (общий, документация, отчеты),
        и обновляет состояние соответствующими параметрами маршрутизации.
    
        Возвращает:
            Обновлённое состояние `AgentState` с ключами:
            - route_decision: general | documentation | elasticsearch_based | all_reports_fallback
            - report_options: список возможных отчетов
            - waiting_for_selection: True, если ожидается выбор отчета пользователем
        """

        user_query = state['user_input']
        print(f"Мастер-роутер получил запрос: '{user_query}'")

        master_decision = self.ai_service.master_router_decision(user_query)
        print(f"Решение мастер-роутера: {master_decision}")

        if master_decision == "general_question":
            state["route_decision"] = "general"
            state["report_options"] = []
            state["waiting_for_selection"] = False
            state["selected_report"] = "general"
        elif master_decision == "documentation_search":
            state["route_decision"] = "documentation"
            state["report_options"] = []
            state["waiting_for_selection"] = False
            state["selected_report"] = "documentation"
        else:
            ordered_reports = self.search_service.get_ordered_report_options(user_query)

            if ordered_reports:
                state["route_decision"] = "elasticsearch_based"
                state["report_options"] = ordered_reports
                state["waiting_for_selection"] = True
            else:
                from src.models import PREDEFINED_REPORTS
                state["route_decision"] = "all_reports_fallback"
                state["report_options"] = PREDEFINED_REPORTS.copy()
                state["waiting_for_selection"] = True

        state["generated_data"] = {}
        return state


class ReportSelectorNode(BaseNode):
    """Узел, отвечающий за возврат состояния во время выбора отчета. Сам выбор происходит в UI."""

    def __call__(self, state: AgentState) -> AgentState:
        """Возвращает текущее состояние без изменений. Используется в момент выбора отчета пользователем"""
        return state


class CodeGeneratorNode(BaseNode):
    """Генератор кода анализа данных для разных типов отчетов."""

    def generate_work_plan_code(self, query: str, df_info: str, selected_option: Optional[Dict] = None) -> str:     
        """
        Генерирует Python-код для анализа данных по планам работ.
        
        Возвращает:
            Строка с кодом на Python, предназначенная для выполнения на объекте `df`.
        """
        pipe = get_model_pipe()
        
        try:
            if selected_option:
                modified_query = f"{query} (фокус на: {selected_option['title']} - {selected_option['description']})"
            else:
                modified_query = query
            
            system_prompt = """Ты - опытный программист Python и специалист по анализу данных с pandas.
            Твоя задача - написать код для анализа нефтепромысловых данных по запросу пользователя.
            Пиши ТОЛЬКО PYTHON КОД без лишних объяснений. Код должен быть выполнимым и работать с СУЩЕСТВУЮЩИМ DataFrame.
            НЕ СОЗДАВАЙ новый DataFrame - используй только существующий, который уже доступен в переменной 'df'.
            """
         
            user_prompt = f"""Напиши код на Python, который анализирует DataFrame по следующему запросу: "{query}"
            Вот информация о DataFrame:
            {df_info}
    
            СТРУКТУРА ДАННЫХ:
            1. "№ п/п" - порядковый номер записи (целое число)
            2. "№ скважины, месторождение" - составной идентификатор в формате "[номер скважины] [название месторождения]", например "152s2 ДАВЫДОВСКОЕ"
            3. "Планируемая дата проведения работ" - временной интервал в формате "DD.MM.YYYY HH:MM-DD.MM.YYYY HH:MM", например "09.10.2024 09:00-09.10.2024 13:00"
            4. "Мероприятие" - код и описание работ, например "РП-24 Ремонт запорной арматуры" 
            5. "Бригада, цех" - информация о бригаде в формате "Бригада №[номер] [название цеха]", например "Бригада №8 ЦДНГ-2"
            6. "Время простоя, ч" - числовое значение с плавающей точкой, например "4.0"
            7. "Суточный дебит нефти, Т в сут." - числовое значение с плавающей точкой, например "13.0" (в тоннах)
            8. "Потери нефти, т" - числовое значение с плавающей точкой, например "1.1" (в тоннах)
            9. "Примечание" - текстовое поле, может содержать "нет" или другую информацию
            
            ВАЖНО:
            1. НЕ СОЗДАВАЙ новый DataFrame и не используй определение данных. Используй ТОЛЬКО существующий DataFrame 'df'.
            2. НЕ ИСПОЛЬЗУЙ pd.DataFrame() или другие способы создания тестовых данных.
            3. Используй точное написание колонок, с сохранением регистра, пробелов и знаков препинания.
            
            4. Правила обработки дат:
               - Разделяй временной интервал в "Планируемая дата проведения работ" на начало и конец
               - Для извлечения даты начала: df["Планируемая дата проведения работ"].str.split("-", expand=True)[0]
               - Для извлечения даты окончания: df["Планируемая дата проведения работ"].str.split("-", expand=True)[1]
               - Используй pd.to_datetime() с параметром format="%d.%m.%Y %H:%M" для преобразования
            
            5. Правила обработки составных идентификаторов:
               - Для поиска по номеру скважины: df["№ скважины, месторождение"].str.split(expand=True)[0] == "НОМЕР" 
               - Для поиска по месторождению: df["№ скважины, месторождение"].str.contains("НАЗВАНИЕ")
               - Для точного совпадения всего идентификатора: df["№ скважины, месторождение"] == "НОМЕР НАЗВАНИЕ"
            
            6. Правила обработки информации о бригадах:
               - Для поиска по номеру бригады: df["Бригада, цех"].str.contains("НАЗВАНИЕ №НОМЕР")
               - Для поиска по цеху: df["Бригада, цех"].str.contains("ЦЕХ")
            
            7. Правила обработки числовых данных:
               - Столбцы "Время простоя, ч", "Суточный дебит нефти, Т в сут.", "Потери нефти, т" содержат числа с плавающей точкой
               - При расчетах преобразуй их в числовой формат: pd.to_numeric(df["Время простоя, ч"])
            
            DataFrame уже доступен через переменную 'df'.
            Выводи результат анализа через print().
            Если требуется визуализация, используй matplotlib с соответствующими подписями осей на русском языке.
            """
         
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
         
            generation_args = {
                "max_new_tokens": 10000,
                "return_full_text": False,
                "temperature": 0.0,
                "top_p": 0.9,
                "do_sample": False
            }
         
            output = pipe(messages, **generation_args)
            generated_text = output[0]['generated_text']
         
            if "```python" in generated_text:
                code_start = generated_text.find("```python") + 9
                code_end = generated_text.find("```", code_start)
                if code_end == -1:
                    code = generated_text[code_start:]
                else:
                    code = generated_text[code_start:code_end]
            else:
                code = generated_text
         
            return code.strip()
         
        except Exception as e:
            return f"# Ошибка при генерации кода: {str(e)}\n# Используем базовый анализ\nprint(df.describe())"

    def generate_drilling_code(self, query: str, selected_option: Optional[Dict] = None) -> str: 
        """
        Генерирует код для анализа шахматки плотности и КВЧ по бурению.
        
        Возвращает:
            Строка с кодом анализа
        """
        pipe = get_model_pipe()
        
        try:
            if selected_option:
                modified_query = f"{query} (фокус на: {selected_option['title']} - {selected_option['description']})"
            else:
                modified_query = query
            
            system_prompt = """Ты - опытный программист Python и специалист по анализу данных с pandas.
            Твоя задача - написать код для анализа данных о замерной добыче нефти по запросу пользователя.
            Пиши ТОЛЬКО PYTHON КОД без лишних объяснений. Код должен быть выполнимым и работать с СУЩЕСТВУЮЩИМ DataFrame.
            НЕ СОЗДАВАЙ новый DataFrame - используй только существующий, который уже доступен в переменной 'df'.
            """
         
            user_prompt = f"""Напиши код на Python, который анализирует DataFrame по следующему запросу: "{query} "
            
            СТРУКТУРА ДАННЫХ:
            DataFrame содержит следующие колонки (ИСПОЛЬЗУЙ ТОЧНО ТАКИЕ ЖЕ НАЗВАНИЯ):
            1. "Месторождение" - название месторождения нефти (object/string) - например: "БЕРЕЗИНСКОЕ"
            2. "Горизонт" - геологический горизонт добычи (object/string, может содержать пропуски), содержит МИНУИМУМ ДВЕ БУКВЫ, ЕСЛЬ МНЕЬШЕ - ЭТО НЕ ГОРИЗОНТ!
            3. "БЕ" - бизнес-единица (object/string) - например: 'Е-14 ЦППС'
            4. "№ скв" - номер скважины (object/string), иожет содержать буквы и цифры, например 172s
            5. "Бригада" - название бригады и цеха (object/string), например: "Бригада № ЦДНГ-2"
            6. "Режим (дебит), Qж,  м3/сут" - режимный дебит жидкости (float64)
            7. "Режим (дебит), Qн, т/сут" - режимный дебит нефти (float64)
            8. "Режим (дебит), %" - обводненность в режиме (float64)
            9. "Режим (дебит), T, сут" - время работы в режиме (float64)
            10. "Замерная (дебит до вычета ТО), Qж,  м3/сут" - замерный дебит жидкости до вычета ТО (float64)
            11. "Замерная (дебит до вычета ТО), Qн, т/сут" - замерный дебит нефти до вычета ТО (float64)
            12. "Замерная (дебит до вычета ТО), %" - обводненность замерная до вычета ТО (float64)
            13. "Замерная (дебит до вычета ТО), T, сут" - время работы замерное до вычета ТО (float64)
            14. "Факт (дебит), Qж,  м3/сут" - фактический дебит жидкости (float64)
            15. "Факт (дебит), Qн, т/сут" - фактический дебит нефти (float64)
            16. "Факт (дебит), %" - фактическая обводненность (float64)
            17. "Факт (дебит), T, сут" - фактическое время работы (float64)
            18. "ΔQн, Зам. - Реж." - разность замерного и режимного дебита нефти (float64)
            19. "ΔQн, Факт - Режим" - разность фактического и режимного дебита нефти (float64)
            20. "К прив. нефть" - коэффициент приведения нефти (object)
            21. "К прив. вода" - коэффициент приведения воды (object)
            22. "КУ" - коэффициент утилизации (object)
            23. "За период (добыча), Режим, т" - добыча нефти за период по режиму (float64)
            24. "За период (добыча), Замер., т" - добыча нефти за период по замерам (float64)
            25. "За период (добыча), Факт, т" - фактическая добыча нефти за период (float64)
            26. "За период (добыча), Откл замер - реж." - отклонение замерной добычи от режимной (float64)
            27. "За период (добыча), Откл факт-режим" - отклонение фактической добычи от режимной (float64)
            28. "Отклонения Замерная-Режим, Qж дебит скважины, м3" - отклонение дебита жидкости (float64)
            29. "Отклонения Замерная-Режим, Т период работы, сут" - отклонение времени работы (float64)
            
            ВАЖНО:
            1. НЕ СОЗДАВАЙ новый DataFrame и не используй определение данных. Используй ТОЛЬКО существующий DataFrame 'df'.
            2. НЕ ИСПОЛЬЗУЙ pd.DataFrame() или другие способы создания тестовых данных.
            3. Используй ТОЧНОЕ написание колонок, с сохранением регистра, пробелов и знаков препинания.
            4. Данные относятся к нефтедобыче, где:
               - Qж - дебит жидкости (нефть + вода)
               - Qн - дебит нефти (чистая нефть)
               - % - обводненность (доля воды в добываемой жидкости)
               - T - время работы скважины в сутках
               - ТО - технологические операции
               - КУ - коэффициент утилизации
            5. Числовые колонки уже преобразованы в float64, но могут содержать NaN значения.
            6. При работе с группировкой используй столбцы "Месторождение", "Горизонт", "Бригада", "№ скв".        
            7. При анализе дебитов обращай внимание на различие между режимными, замерными и фактическими значениями.
            8. Строй графики только тогда, когда тебя просят
            9. При фильтрации строковых значений используй **поиск по вхождению**: `.str.contains(..., case=False, na=False)`, чтобы учесть возможные отличия в записи.
            DataFrame уже доступен через переменную 'df'.
            Выводи результат анализа через print().
            Если требуется визуализация, используй matplotlib с соответствующими подписями осей на русском языке и легендой.
            """
         
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
         
            generation_args = {
                "max_new_tokens": 10000,
                "return_full_text": False,
                "temperature": 0.0,
                "top_p": 0.9,
                "do_sample": False
            }
         
            output = pipe(messages, **generation_args)
            generated_text = output[0]['generated_text']
         
            if "```python" in generated_text:
                code_start = generated_text.find("```python") + 9
                code_end = generated_text.find("```", code_start)
                if code_end == -1:
                    code = generated_text[code_start:]
                else:
                    code = generated_text[code_start:code_end]
            else:
                code = generated_text
         
            return code.strip()
         
        except Exception as e:
            return f"# Ошибка при генерации кода: {str(e)}\n# Создаем базовые данные для анализа\nimport numpy as np\nprint('Базовая статистика по дебитам:')\nprint(df.describe())"

    def generate_measurement_code(self, query: str, selected_option: Optional[Dict] = None) -> str:
        """
        Генерирует код анализа данных по утилизации газа.
        
        Возвращает:
            Строка с кодом анализа
        """
        pipe = get_model_pipe()
        
        try:
            if selected_option:
                modified_query = f"{query} (фокус на: {selected_option['title']} - {selected_option['description']})"
            else:
                modified_query = query
            
            system_prompt = """Ты - опытный программист Python и специалист по анализу данных с pandas.
            Твоя задача - написать код для анализа данных о добыче и поставке газа по запросу пользователя.
            Пиши ТОЛЬКО PYTHON КОД без лишних объяснений. Код должен быть выполнимым и работать с СУЩЕСТВУЮЩИМ DataFrame.
            НЕ СОЗДАВАЙ новый DataFrame - используй только существующий, который уже доступен в переменной 'df'.
            """
         
            user_prompt = f"""Напиши код на Python, который анализирует DataFrame по следующему запросу: "{query}"
            
            СТРУКТУРА ДАННЫХ:
            DataFrame содержит следующие колонки (ИСПОЛЬЗУЙ ТОЧНО ТАКИЕ ЖЕ НАЗВАНИЯ):
            1. "Месяц" - дата в формате "YYYY-MM-DD 00:00:00", хранится как строка (object)
            2. "Газ НГДУ,\nтыс. м3 Всего" - объем газа НГДУ
            3. "Добыча газа, тыс. м3 План" - плановый объем добычи газа
            4. "Добыча газа, тыс. м3 Факт" - фактический объем добычи газа
            5. "Добыча газа, тыс. м3 Откл-е" - отклонение от плана
            6. "Поставка газа, тыс. м3 БГПЗ Всего План" - плановый объем поставки газа на БГПЗ
            7. "Поставка газа, тыс. м3 БГПЗ Всего Факт" - фактический объем поставки газа на БГПЗ
            8. "Поставка газа, тыс. м3 БГПЗ Всего Откл-е" - отклонение от плана
            9. "Поставка газа, тыс. м3 БГПЗ В том числе Попутный нефтяной газ План" - план поставки попутного газа
            10. "Поставка газа, тыс. м3 БГПЗ В том числе Попутный нефтяной газ Факт" - факт поставки попутного газа
            11. "Поставка газа, тыс. м3 БГПЗ В том числе Попутный нефтяной газ Откл-е" - отклонение плана поставки попутного газа
            12. "Поставка газа, тыс. м3 БГПЗ В том числе От стабилизации нефти План" - план поставки газа от стабилизации
            13. "Поставка газа, тыс. м3 БГПЗ В том числе От стабилизации нефти Факт" - факт поставки газа от стабилизации
            14. "Поставка газа, тыс. м3 БГПЗ В том числе От стабилизации нефти Откл-е" - отклонение плана поставки газа от стабилизации
            15. "Поставка газа, тыс. м3 БГПЗ В том числе Газ отдувки К-1 План" - план поставки газа отдувки К-1
            16. "Поставка газа, тыс. м3 БГПЗ В том числе Газ отдувки К-1 Факт" - факт поставки газа отдувки К-1
            17. "Поставка газа, тыс. м3 БГПЗ В том числе Газ отдувки К-1 Откл-е" - отклонение плана поставки газа отдувки К-1
            18. 'Поставка газа, тыс. м3 "Нужды БГПЗ" - сырой газ План' - план поставки сырого газа на нужды БГПЗ
            19. 'Поставка газа, тыс. м3 "Нужды БГПЗ" - сырой газ Факт' - факт поставки сырого газа на нужды БГПЗ
            20. 'Поставка газа, тыс. м3 "Нужды БГПЗ" - сырой газ Откл-е' - отклонение плана поставки сырого газа на нужды БГПЗ
            21. 'Поставка газа, тыс. м3 ГП "Белоруснефть-Промсервис" (НСП "Виша") План' - план поставки на ГП
            22. 'Поставка газа, тыс. м3 ГП "Белоруснефть-Промсервис" (НСП "Виша") Факт' - факт поставки на ГП
            23. 'Поставка газа, тыс. м3 ГП "Белоруснефть-Промсервис" (НСП "Виша") Откл-е' - отклонение плана поставки на ГП
            24. "Поставка газа, тыс. м3 Прочие потребители План" - план поставки прочим потребителям
            25. "Поставка газа, тыс. м3 Прочие потребители Факт" - факт поставки прочим потребителям
            26. "Поставка газа, тыс. м3 Прочие потребители Откл-е" - отклонение плана поставки прочим потребителям
            27. "Потери газа, тыс. м3 План" - плановые потери газа
            28. "Потери газа, тыс. м3 Факт" - фактические потери газа
            29. "Потери газа, тыс. м3 Откл-е" - отклонение плановых потерь газа
            30. "Сухой газ, тыс. м3 Технологические нужды НГДУ План" - план использования на технологические нужды
            31. "Сухой газ, тыс. м3 Технологические нужды НГДУ Факт" - факт использования на технологические нужды
            32. "Сухой газ, тыс. м3 Технологические нужды НГДУ Откл-е" - отклонение плана использования на технологические нужды
            33. "Сухой газ, тыс. м3 Для оптимизации технологии стабилизации нефти План" - план для оптимизации
            34. "Сухой газ, тыс. м3 Для оптимизации технологии стабилизации нефти Факт" - факт для оптимизации
            35. "Сухой газ, тыс. м3 Для оптимизации технологии стабилизации нефти Откл-е" - отклонение плана для оптимизации
            36. "Сухой газ, тыс. м3 Всего План" - общий план сухого газа
            37. "Сухой газ, тыс. м3 Всего Факт" - общий факт сухого газа
            38. "Сухой газ, тыс. м3 Всего Откл-е" - общее отклонение плана сухого газа
            
            ВАЖНО:
            1. НЕ СОЗДАВАЙ новый DataFrame и не используй определение данных. Используй ТОЛЬКО существующий DataFrame 'df'.
            2. НЕ ИСПОЛЬЗУЙ pd.DataFrame() или другие способы создания тестовых данных.
            3. Используй ТОЧНОЕ написание колонок, с сохранением регистра, пробелов и знаков препинания.
            
            4. Правила обработки дат:
               - Колонка "Месяц" хранится как строка (object)
               - Для анализа по месяцам сначала преобразуй: df["Месяц"] = pd.to_datetime(df["Месяц"])
               - Текущий год для анализа: 2024 (ВСЕГДА используй 2024 год, если явно не указан другой)
               - Затем извлекай месяц/год: df["Месяц"].dt.month или df["Месяц"].dt.year
            
            5. Правила обработки кварталов:
               - При анализе по кварталам используй следующее определение:
                 * Q1 (Квартал 1): месяцы 1-3 (Январь-Март)
                 * Q2 (Квартал 2): месяцы 4-6 (Апрель-Июнь)
                 * Q3 (Квартал 3): месяцы 7-9 (Июль-Сентябрь)
                 * Q4 (Квартал 4): месяцы 10-12 (Октябрь-Декабрь)
               - Для создания колонки с номером квартала используй:
                 df["Квартал"] = df["Месяц"].dt.quarter
               - Или используй pd.PeriodIndex для создания периода квартала:
                 df["Квартал"] = pd.PeriodIndex(df["Месяц"], freq='Q')
            
            6. Правила обработки числовых данных:
               - ВСЕ числовые колонки хранятся как строки (object) и требуют преобразования
               - При расчетах используй: pd.to_numeric(df["Колонка"], errors='coerce')
               - Данные могут содержать нулевые данные или значения, не преобразуемые в числа
               - После преобразования проверяй на NaN: df["Колонка"].isna().sum()
            
            7. При работе с колонками, содержащими кавычки, используй точное название колонки, например:
               - df['Поставка газа, тыс. м3 "Нужды БГПЗ" - сырой газ Факт']
               - df['Поставка газа, тыс. м3 ГП "Белоруснефть-Промсервис" (НСП "Виша") План']
            
            DataFrame уже доступен через переменную 'df'.
            Выводи результат анализа через print().
            Если требуется визуализация, используй matplotlib с соответствующими подписями осей на русском языке и легендой.
            """
         
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
         
            generation_args = {
                "max_new_tokens": 10000,
                "return_full_text": False,
                "temperature": 0.0,
                "top_p": 0.9,
                "do_sample": False
            }
         
            output = pipe(messages, **generation_args)
            generated_text = output[0]['generated_text']
         
            if "```python" in generated_text:
                code_start = generated_text.find("```python") + 9
                code_end = generated_text.find("```", code_start)
                if code_end == -1:
                    code = generated_text[code_start:]
                else:
                    code = generated_text[code_start:code_end]
            else:
                code = generated_text
         
            return code.strip()
         
        except Exception as e:
            return f"# Ошибка при генерации кода: {str(e)}\n# Создаем базовые данные для анализа\nprint('Базовая статистика по газу:')\nprint(df.describe())"

    def generate_gas_utilization_code(self, query: str, selected_option: Optional[Dict] = None) -> str:
        """
        Генерирует код анализа данных по замерной добыче.
        
        Возвращает:
            Строка с кодом анализа
        """
        pipe = get_model_pipe()
        
        try:
            if selected_option:
                modified_query = f"{query} (фокус на: {selected_option['title']} - {selected_option['description']})"
            else:
                modified_query = query
            
            system_prompt = """Ты - опытный программист Python и специалист по анализу данных с pandas.
            Твоя задача - написать код для анализа данных о замерной добыче нефти по запросу пользователя.
            Пиши ТОЛЬКО PYTHON КОД без лишних объяснений. Код должен быть выполнимым и работать с СУЩЕСТВУЮЩИМ DataFrame.
            НЕ СОЗДАВАЙ новый DataFrame - используй только существующий, который уже доступен в переменной 'df'.
            """
         
            user_prompt = f"""Напиши код на Python, который анализирует DataFrame по следующему запросу: "{query} "
            
            СТРУКТУРА ДАННЫХ:
            DataFrame содержит следующие колонки (ИСПОЛЬЗУЙ ТОЧНО ТАКИЕ ЖЕ НАЗВАНИЯ):
            1. "Месторождение" - название месторождения нефти (object/string) - например: "БЕРЕЗИНСКОЕ"
            2. "Горизонт" - геологический горизонт добычи (object/string, может содержать пропуски), содержит МИНУИМУМ ДВЕ БУКВЫ, ЕСЛЬ МНЕЬШЕ - ЭТО НЕ ГОРИЗОНТ!
            3. "БЕ" - бизнес-единица (object/string) - например: 'Е-14 ЦППС'
            4. "№ скв" - номер скважины (object/string), иожет содержать буквы и цифры, например 172s
            5. "Бригада" - название бригады и цеха (object/string), например: "Бригада № ЦДНГ-2"
            6. "Режим (дебит), Qж,  м3/сут" - режимный дебит жидкости (float64)
            7. "Режим (дебит), Qн, т/сут" - режимный дебит нефти (float64)
            8. "Режим (дебит), %" - обводненность в режиме (float64)
            9. "Режим (дебит), T, сут" - время работы в режиме (float64)
            10. "Замерная (дебит до вычета ТО), Qж,  м3/сут" - замерный дебит жидкости до вычета ТО (float64)
            11. "Замерная (дебит до вычета ТО), Qн, т/сут" - замерный дебит нефти до вычета ТО (float64)
            12. "Замерная (дебит до вычета ТО), %" - обводненность замерная до вычета ТО (float64)
            13. "Замерная (дебит до вычета ТО), T, сут" - время работы замерное до вычета ТО (float64)
            14. "Факт (дебит), Qж,  м3/сут" - фактический дебит жидкости (float64)
            15. "Факт (дебит), Qн, т/сут" - фактический дебит нефти (float64)
            16. "Факт (дебит), %" - фактическая обводненность (float64)
            17. "Факт (дебит), T, сут" - фактическое время работы (float64)
            18. "ΔQн, Зам. - Реж." - разность замерного и режимного дебита нефти (float64)
            19. "ΔQн, Факт - Режим" - разность фактического и режимного дебита нефти (float64)
            20. "К прив. нефть" - коэффициент приведения нефти (object)
            21. "К прив. вода" - коэффициент приведения воды (object)
            22. "КУ" - коэффициент утилизации (object)
            23. "За период (добыча), Режим, т" - добыча нефти за период по режиму (float64)
            24. "За период (добыча), Замер., т" - добыча нефти за период по замерам (float64)
            25. "За период (добыча), Факт, т" - фактическая добыча нефти за период (float64)
            26. "За период (добыча), Откл замер - реж." - отклонение замерной добычи от режимной (float64)
            27. "За период (добыча), Откл факт-режим" - отклонение фактической добычи от режимной (float64)
            28. "Отклонения Замерная-Режим, Qж дебит скважины, м3" - отклонение дебита жидкости (float64)
            29. "Отклонения Замерная-Режим, Т период работы, сут" - отклонение времени работы (float64)
            
            ВАЖНО:
            1. НЕ СОЗДАВАЙ новый DataFrame и не используй определение данных. Используй ТОЛЬКО существующий DataFrame 'df'.
            2. НЕ ИСПОЛЬЗУЙ pd.DataFrame() или другие способы создания тестовых данных.
            3. Используй ТОЧНОЕ написание колонок, с сохранением регистра, пробелов и знаков препинания.
            4. Данные относятся к нефтедобыче, где:
               - Qж - дебит жидкости (нефть + вода)
               - Qн - дебит нефти (чистая нефть)
               - % - обводненность (доля воды в добываемой жидкости)
               - T - время работы скважины в сутках
               - ТО - технологические операции
               - КУ - коэффициент утилизации
            5. Числовые колонки уже преобразованы в float64, но могут содержать NaN значения.
            6. При работе с группировкой используй столбцы "Месторождение", "Горизонт", "Бригада", "№ скв".        
            7. При анализе дебитов обращай внимание на различие между режимными, замерными и фактическими значениями.
            8. Строй графики только тогда, когда тебя просят
            9. При фильтрации строковых значений используй **поиск по вхождению**: `.str.contains(..., case=False, na=False)`, чтобы учесть возможные отличия в записи.
            DataFrame уже доступен через переменную 'df'.
            Выводи результат анализа через print().
            Если требуется визуализация, используй matplotlib с соответствующими подписями осей на русском языке и легендой.
            """
         
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
         
            generation_args = {
                "max_new_tokens": 10000,
                "return_full_text": False,
                "temperature": 0.0,
                "top_p": 0.9,
                "do_sample": False
            }
         
            output = pipe(messages, **generation_args)
            generated_text = output[0]['generated_text']
         
            if "```python" in generated_text:
                code_start = generated_text.find("```python") + 9
                code_end = generated_text.find("```", code_start)
                if code_end == -1:
                    code = generated_text[code_start:]
                else:
                    code = generated_text[code_start:code_end]
            else:
                code = generated_text
         
            return code.strip()
         
        except Exception as e:
            return f"# Ошибка при генерации кода: {str(e)}\n# Создаем базовые данные для анализа\nimport numpy as np\nprint('Базовая статистика по дебитам:')\nprint(df.describe())"

    def generate_final_response(self, state: AgentState) -> str:
        """
        Формирует финальное текстовое объяснение на основе результатов анализа и типа отчета.
        
        Возвращает:
            Строка — объяснение на русском языке, с пояснениями переменных и формулами.
        """
        selected_option = None
        if state.get("selected_report") and state.get("report_options"):
            for option in state["report_options"]:
                if option["id"] == state["selected_report"]:
                    selected_option = option
                    break

        context = f"""Ты AI-ассистент. Отвечай кратко и информативно.

ПРАВИЛА ДЛЯ ФОРМУЛ И ПОЯСНЕНИЙ:
1. Обычные числа пиши как текст: "дебит 25.5 т/сут"
2. Формулы заключай в $...$ 
3. В пояснениях переменных используй НОРМАЛЬНЫЕ скобки для единиц измерения
4. Пиши пояснения через тире с правильными скобками: "Q — дебит нефти (в т/сут)"

ПРИМЕР:
$Q = \\frac{{V}}{{t}}$

где:
- Q — дебит нефти (в т/сут)
- V — объем нефти (в тоннах) 
- t — время (в сутках)

        Исходный запрос пользователя: {state['user_input']}
        Тип отчета: {state['route_decision']}
        Выбранный вариант отчета: {selected_option['title'] if selected_option else 'Стандартный анализ'}
        Результаты анализа данных:
        {state['analysis_result']}

        Объясни результаты понятным языком, отвечая на исходный вопрос пользователя с учетом выбранного типа отчета.
        """

        messages = [
            {"role": "system", "content": context},
            {"role": "user", "content": f"Объясни результаты анализа по запросу: {state['user_input']}"}
        ]

        return self.ai_service.generate_response(messages, max_tokens=5000, temperature=0.1)


class WorkPlanNode(BaseNode):
    """Узел для обработки и анализа отчетов по планам работ."""

    def __init__(self, ai_service: AIService, data_service: DataService):
        super().__init__(ai_service)
        self.data_service = data_service
        self.code_generator = CodeGeneratorNode(ai_service)

    def __call__(self, state: AgentState) -> AgentState:
        """
        Загружает данные планов, генерирует и выполняет код анализа, формирует текстовый ответ и график (если нужен).
    
        Возвращает:
            Обновлённое состояние с результатами анализа
        """
        work_plan_df, _ = self.data_service.load_work_plan_data()

        selected_option = None
        if state.get("selected_report") and state.get("report_options"):
            for option in state["report_options"]:
                if option["id"] == state["selected_report"]:
                    selected_option = option
                    break

        df_info = f"""
Типы данных: {work_plan_df.dtypes}
Количество записей: {len(work_plan_df)}
Столбцы: {list(work_plan_df.columns)}
"""

        status_placeholder = st.empty()
        status_placeholder.info("🔄 Генерирую код анализа для планов работы...")

        session_id = st.session_state.get('session_id', 'default')
        generated_code = queue_aware_generation(session_id, 'generate_work_plan_code', {
            'query': state['user_input'],
            'df_info': df_info,
            'selected_option': selected_option
        })

        status_placeholder.info("⚙️ Выполняю анализ данных...")

        result_text, plot_path, code = execute_generated_code(generated_code, work_plan_df)

        summary_type = selected_option['title'] if selected_option else "План работы на промыслах"

        status_placeholder.info("💭 Формирую итоговый ответ...")

        state["analysis_code"] = code
        state["analysis_result"] = result_text
        state["plot_path"] = plot_path or ""
        state["summary_type"] = summary_type
        state["waiting_for_selection"] = False

        state["generated_data"] = {
            "data_source": "work_plan_analysis",
            "selected_option": selected_option,
            "has_visualization": bool(plot_path),
            "status_placeholder": status_placeholder
        }

        return state


class DrillingReportNode(BaseNode):
    """Узел для анализа шахматки плотности и КВЧ (отчеты по бурению)."""

    def __init__(self, ai_service: AIService, data_service: DataService):
        super().__init__(ai_service)
        self.data_service = data_service
        self.code_generator = CodeGeneratorNode(ai_service)

    def __call__(self, state: AgentState) -> AgentState:
        """Обрабатывает вопросы о бурении"""
        drilling_df, message = self.data_service.load_drilling_data()
        if drilling_df is None:
            st.warning("⚠️ Не удалось загрузить данные шахматки. Используются тестовые данные.")
            drilling_df = pd.DataFrame({
                'id': ['#1', '#2'],
                'well': ['126', '127'],
                'field': ['ВИШАНСКОЕ', 'СЕВЕРНОЕ'],
                'date': [pd.Timestamp('2024-08-01'), pd.Timestamp('2024-08-02')],
                'plotnost': ['1.05', '1.10'],
                'plotnost_itog': ['Нет отклонений', 'Есть отклонения'],
                'kvch': ['0.85', '0.90'],
                'kvch_itog': ['Нет отклонений', 'Нет отклонений']
            })

        selected_option = None
        if state.get("selected_report") and state.get("report_options"):
            for option in state["report_options"]:
                if option["id"] == state["selected_report"]:
                    selected_option = option
                    break

        status_placeholder = st.empty()
        status_placeholder.info("🔄 Генерирую код анализа для отчетов по бурению...")

        session_id = st.session_state.get('session_id', 'default')
        generated_code = queue_aware_generation(session_id, 'generate_drilling_code', {
            'query': state['user_input'],
            'selected_option': selected_option
        })

        status_placeholder.info("⚙️ Выполняю анализ данных...")

        result_text, plot_path, code = execute_generated_code(generated_code, drilling_df)

        summary_type = selected_option['title'] if selected_option else "Шахматка проб по плотности и КВЧ"

        status_placeholder.info("💭 Формирую итоговый ответ...")

        state["analysis_code"] = code
        state["analysis_result"] = result_text
        state["plot_path"] = plot_path or ""
        state["summary_type"] = summary_type
        state["waiting_for_selection"] = False

        state["generated_data"] = {
            "data_source": "drilling_analysis",
            "selected_option": selected_option,
            "has_visualization": bool(plot_path),
            "status_placeholder": status_placeholder
        }

        return state


class MeasurementReportNode(BaseNode):
    """Узел для обработки отчетов по замерной добыче нефти."""

    def __init__(self, ai_service: AIService, data_service: DataService):
        super().__init__(ai_service)
        self.data_service = data_service
        self.code_generator = CodeGeneratorNode(ai_service)

    def __call__(self, state: AgentState) -> AgentState:
        """Обрабатывает вопросы о замерной добыче"""
        measurement_df, message = self.data_service.load_measurement_data()
        if measurement_df is None:
            st.warning("⚠️ Не удалось загрузить данные замерной добычи. Создаем тестовые данные.")
            measurement_df = pd.DataFrame({
                'Месторождение': ['БЕРЕЗИНСКОЕ', 'СЕВЕРНОЕ', 'ВОСТОЧНОЕ'],
                '№ скв': ['152', '234', '345'],
                'Режим (дебит), Qн, т/сут': [13.0, 25.5, 18.2],
                'Замерная (дебит до вычета ТО), Qн, т/сут': [12.5, 24.8, 17.9],
                'Факт (дебит), Qн, т/сут': [12.1, 24.2, 17.5]
            })

        selected_option = None
        if state.get("selected_report") and state.get("report_options"):
            for option in state["report_options"]:
                if option["id"] == state["selected_report"]:
                    selected_option = option
                    break

        status_placeholder = st.empty()
        status_placeholder.info("🔄 Генерирую код анализа для замерной добычи...")

        session_id = st.session_state.get('session_id', 'default')
        generated_code = queue_aware_generation(session_id, 'generate_measurement_code', {
            'query': state['user_input'],
            'selected_option': selected_option
        })

        status_placeholder.info("⚙️ Выполняю анализ данных...")

        result_text, plot_path, code = execute_generated_code(generated_code, measurement_df)

        summary_type = selected_option['title'] if selected_option else "Отчёт по замерной добыче за период"

        status_placeholder.info("💭 Формирую итоговый ответ...")

        state["analysis_code"] = code
        state["analysis_result"] = result_text
        state["plot_path"] = plot_path or ""
        state["summary_type"] = summary_type
        state["waiting_for_selection"] = False

        state["generated_data"] = {
            "data_source": "measurement_analysis",
            "selected_option": selected_option,
            "has_visualization": bool(plot_path),
            "status_placeholder": status_placeholder
        }

        return state


class GasUtilizationNode(BaseNode):
    """Узел для анализа отчетов по добыче и утилизации газа."""

    def __init__(self, ai_service: AIService, data_service: DataService):
        super().__init__(ai_service)
        self.data_service = data_service
        self.code_generator = CodeGeneratorNode(ai_service)

    def __call__(self, state: AgentState) -> AgentState:
        """Обрабатывает вопросы об утилизации газа"""
        gas_df, message = self.data_service.load_gas_utilization_data()
        if gas_df is None:
            st.warning("⚠️ Не удалось загрузить данные утилизации газа. Создаем тестовые данные.")
            gas_df = pd.DataFrame({
                'Месяц': ['2024-01-01', '2024-02-01', '2024-03-01'],
                'Добыча газа, тыс. м3 План': ['100', '120', '110'],
                'Добыча газа, тыс. м3 Факт': ['105', '115', '108'],
                'Потери газа, тыс. м3 План': ['5', '6', '5.5'],
                'Потери газа, тыс. м3 Факт': ['4.8', '5.9', '5.2']
            })

        selected_option = None
        if state.get("selected_report") and state.get("report_options"):
            for option in state["report_options"]:
                if option["id"] == state["selected_report"]:
                    selected_option = option
                    break

        status_placeholder = st.empty()
        status_placeholder.info("🔄 Генерирую код анализа для утилизации газа...")

        session_id = st.session_state.get('session_id', 'default')
        generated_code = queue_aware_generation(session_id, 'generate_gas_utilization_code', {
            'query': state['user_input'],
            'selected_option': selected_option
        })

        status_placeholder.info("⚙️ Выполняю анализ данных...")

        result_text, plot_path, code = execute_generated_code(generated_code, gas_df)

        summary_type = selected_option['title'] if selected_option else "Отчёт о выполнении утилизации газа"

        status_placeholder.info("💭 Формирую итоговый ответ...")

        state["analysis_code"] = code
        state["analysis_result"] = result_text
        state["plot_path"] = plot_path or ""
        state["summary_type"] = summary_type
        state["waiting_for_selection"] = False

        state["generated_data"] = {
            "data_source": "gas_utilization_analysis",
            "selected_option": selected_option,
            "has_visualization": bool(plot_path),
            "status_placeholder": status_placeholder
        }

        return state


class DocumentationNode(BaseNode):
    """Узел обработки запросов по документации: выполняет поиск и формирует ответ на основе релевантных документов."""

    def __init__(self, ai_service: AIService, search_service: SearchService):
        super().__init__(ai_service)
        self.search_service = search_service

    def __call__(self, state: AgentState) -> AgentState:
        """
        Ищет релевантные документы по запросу и формирует объяснение на их основе.

        Возвращает:
            Обновлённое состояние с найденными документами и сформированным ответом
        """
        user_query = state['user_input']

        status_placeholder = st.empty()
        status_placeholder.info("🔍 Ищу информацию в документации...")

        doc_results = self.search_service.search_documentation(user_query)

        status_placeholder.info("💭 Формирую ответ на основе найденной документации...")

        session_id = st.session_state.get('session_id', 'default')
        response = queue_aware_generation(session_id, 'generate_documentation_response', {
            'query': user_query,
            'doc_results': [doc.__dict__ for doc in doc_results]
        })

        status_placeholder.empty()

        state["response"] = response
        state["doc_results"] = [doc.__dict__ for doc in doc_results]
        state["summary_type"] = "Документация системы"
        state["analysis_code"] = ""
        state["analysis_result"] = ""
        state["plot_path"] = ""
        state["waiting_for_selection"] = False
        state["generated_data"] = {
            "data_source": "documentation_search",
            "found_docs": len(doc_results),
            "status_placeholder": status_placeholder
        }

        return state


class GeneralNode(BaseNode):
    """Узел для обработки общих (неспециализированных) вопросов пользователя."""

    def __call__(self, state: AgentState) -> AgentState:
         """
        Генерирует ответ на общий вопрос, не связанный с отчетами или документацией.
    
        Возвращает:
            Обновлённое состояние с текстом ответа
        """
        response = self.ai_service.generate_general_response(state['user_input'])

        state["response"] = response
        state["summary_type"] = "Общий вопрос"
        state["waiting_for_selection"] = False
        state["analysis_code"] = ""
        state["analysis_result"] = ""
        state["plot_path"] = ""
        state["generated_data"] = {"data_source": "general_response"}

        return state


class ResponseGeneratorNode(BaseNode):
    """Финальный узел: формирует окончательный ответ на основе анализа или генерации."""

    def __call__(self, state: AgentState) -> AgentState:
        """
        Завершает обработку: очищает статус и, при необходимости, генерирует финальный ответ по результатам анализа.
    
        Возвращает:
            Обновлённое состояние с полем 'response'
        """
        if state.get("generated_data") and "status_placeholder" in state["generated_data"]:
            state["generated_data"]["status_placeholder"].empty()

        if state["route_decision"] not in ["general", "documentation"]:
            if "response" not in state or not state["response"]:
                code_generator = CodeGeneratorNode(self.ai_service)
                state["response"] = code_generator.generate_final_response(state)

        return state