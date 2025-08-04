"""Сервис для работы с AI моделями"""
import torch
import streamlit as st
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from typing import List, Dict, Optional
from config import config
from src.constants import SYSTEM_PROMPTS, REPORT_DATA_DESCRIPTIONS


class AIService:
    """Сервис для работы с AI моделью"""

    def __init__(self):
        self._pipe = None

    @st.cache_resource
    def _load_model(_self):
        """Загружает модель с кешированием"""
        torch.random.manual_seed(0)

        model = AutoModelForCausalLM.from_pretrained(
            config.MODEL_PATH,
            cache_dir=config.MODEL_CACHE_DIR,
            device_map="cuda",
            torch_dtype="auto",
            trust_remote_code=True,
        )
        tokenizer = AutoTokenizer.from_pretrained(config.MODEL_PATH)

        pipe = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
        )

        return pipe

    def get_pipe(self):
        """Получает пайплайн модели"""
        if self._pipe is None:
            self._pipe = self._load_model()
        return self._pipe

    def generate_response(self, messages: List[Dict[str, str]],
                          max_tokens: int = None, temperature: float = None) -> str:
        """Генерирует ответ модели"""
        pipe = self.get_pipe()

        generation_args = {
            "max_new_tokens": max_tokens or config.MAX_NEW_TOKENS,
            "return_full_text": False,
            "temperature": temperature or config.TEMPERATURE,
            "do_sample": temperature and temperature > 0,
        }

        output = pipe(messages, **generation_args)
        return output[0]['generated_text']

    def master_router_decision(self, user_query: str) -> str:
        """Определяет намерение пользователя"""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS["master_router"]},
            {"role": "user", "content": f"""Проанализируй следующий запрос пользователя и определи его намерение:

            "{user_query}"

            Ответь только одним из вариантов:
            - reports_analysis (если пользователь хочет анализировать отчеты/данные)
            - documentation_search (если пользователь ищет документацию или помощь по системе)
            - general_question (если это общий вопрос)
            """}
        ]

        response = self.generate_response(messages, max_tokens=50, temperature=0.0)
        response = response.strip().lower()

        # Валидация ответа
        if "documentation_search" in response:
            return "documentation_search"
        elif "reports_analysis" in response:
            return "reports_analysis"
        elif "general_question" in response:
            return "general_question"
        else:
            # Fallback: анализируем ключевые слова
            doc_keywords = ["как", "инструкция", "настройка", "интерфейс", "функция", "система"]
            report_keywords = ["дебит", "добыча", "скважина", "газ", "нефть", "анализ", "график"]

            query_lower = user_query.lower()

            doc_score = sum(1 for word in doc_keywords if word in query_lower)
            report_score = sum(1 for word in report_keywords if word in query_lower)

            if doc_score > report_score and doc_score > 0:
                return "documentation_search"
            elif report_score > 0:
                return "reports_analysis"
            else:
                return "general_question"

    def decompose_query_for_reports(self, original_query: str, selected_report_ids: List[str]) -> Dict[str, str]:
        """Декомпозирует общий вопрос на специфичные для каждого отчета"""
        try:
            # Получаем детальную информацию о выбранных отчетах
            reports_details = []
            for report_id in selected_report_ids:
                if report_id in REPORT_DATA_DESCRIPTIONS:
                    reports_details.append(f"""
{report_id}:
- Описание: {REPORT_DATA_DESCRIPTIONS[report_id]}""")

            system_prompt = """Ты - эксперт по анализу данных нефтегазовой отрасли. 
            Твоя задача - разбить общий вопрос пользователя на специфичные вопросы для каждого типа отчета."""

            user_prompt = f"""Общий вопрос пользователя: "{original_query}"

Выбранные отчеты и их предметные области:
{chr(10).join(reports_details)}

ЗАДАЧА: Проанализируй общий вопрос и разбей его на специфичные вопросы для каждого отчета.

Ответь СТРОГО в формате:
work_plan: [специфичный вопрос]
drilling_report: [специфичный вопрос]
measurement_report: [специфичный вопрос] 
gas_utilization: [специфичный вопрос]

Отвечай только теми строками, которые соответствуют выбранным отчетам: {', '.join(selected_report_ids)}"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            response_text = self.generate_response(messages, max_tokens=1000, temperature=0.0)

            # Парсим ответ модели
            specific_queries = {}
            for line in response_text.split('\n'):
                line = line.strip()
                if ':' in line and any(report_id in line for report_id in selected_report_ids):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        report_key = parts[0].strip()
                        query = parts[1].strip()

                        # Очищаем от возможных скобок или кавычек
                        if query.startswith('[') and query.endswith(']'):
                            query = query[1:-1]
                        if query.startswith('"') and query.endswith('"'):
                            query = query[1:-1]

                        # Заменяем "базовый обзор данных" на более конкретный вопрос
                        if "базовый" in query.lower():
                            query = f"Проведи обзорный анализ данных по теме: {original_query}"

                        specific_queries[report_key] = query

            # Проверяем, что у нас есть вопросы для всех выбранных отчетов
            for report_id in selected_report_ids:
                if report_id not in specific_queries:
                    specific_queries[report_id] = f"Проведи анализ данных в контексте вопроса: {original_query}"

            return specific_queries

        except Exception as e:
            print(f"Ошибка при декомпозиции вопроса: {str(e)}")
            # Fallback: используем исходный вопрос для всех отчетов
            return {report_id: original_query for report_id in selected_report_ids}

    def generate_general_response(self, user_input: str) -> str:
        """Генерирует ответ на общий вопрос"""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS["ai_assistant"]},
            {"role": "user", "content": user_input}
        ]

        return self.generate_response(messages, max_tokens=1000, temperature=0.2)

    def generate_documentation_response(self, query: str, doc_results: List[Dict]) -> str:
        """Генерирует ответ на основе найденной документации"""
        if not doc_results:
            return "К сожалению, я не нашел релевантной информации в документации по вашему запросу. Попробуйте переформулировать вопрос или обратитесь к администратору системы."

        # Формируем контекст из найденных документов
        context_parts = []
        for i, doc in enumerate(doc_results, 1):
            content = doc['content']
            context_parts.append(f"Документ {i}:\n{content}")

        context = "\n\n".join(context_parts)

        system_prompt = """Ты - специалист по технической поддержке системы анализа нефтегазовых данных.
        Твоя задача - отвечать на вопросы пользователей о работе системы, основываясь на предоставленной документации.

        ПРАВИЛА:
        1. Отвечай только на основе предоставленной документации
        2. Если в документации нет точного ответа, честно об этом скажи
        3. Давай конкретные и практические советы
        4. Используй дружелюбный и профессиональный тон
        5. Структурируй ответ для лучшего понимания"""

        user_prompt = f"""На основе следующей документации ответь на вопрос пользователя:

ДОКУМЕНТАЦИЯ:
{context}

ВОПРОС ПОЛЬЗОВАТЕЛЯ: {query}

Дай полный и понятный ответ, основываясь только на предоставленной документации."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return self.generate_response(messages, max_tokens=7000, temperature=0.0)

    def generate_combined_analysis(self, all_final_states: List[Dict],
                                   selected_report_ids: List[str], user_query: str) -> str:
        """Генерирует сводный анализ для нескольких отчетов"""
        try:
            # Собираем все результаты анализа
            combined_results = []
            for i, state in enumerate(all_final_states, 1):
                combined_results.append(f"Отчет {i} ({state['summary_type']}):\n{state['response']}")

            # Создаем промпт для сводного анализа
            system_prompt = f"""Ты - аналитик нефтегазовой отрасли. Создай краткий сводный анализ на основе результатов нескольких отчетов.

ПРАВИЛА ДЛЯ ФОРМУЛ:
1. Обычные числа пиши как текст: "дебит 25.5 т/сут"
2. Формулы заключай в $$...$$ например: $$K = \\frac{{Q_{{факт}}}}{{Q_{{план}}}}$$"""

            user_prompt = f"""Исходный вопрос пользователя: "{user_query}"

На основе следующих отчетов создай краткий сводный анализ, который отвечает на исходный вопрос:

{chr(10).join(combined_results)}"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            return self.generate_response(messages, max_tokens=6000, temperature=0.1)

        except Exception as e:
            return f"Не удалось сгенерировать сводный анализ: {str(e)}"