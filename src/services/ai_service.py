"""Сервис для работы с AI моделями"""
import torch
import streamlit as st
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from typing import List, Dict, Optional
from config import config
from src.constants import SYSTEM_PROMPTS, REPORT_DATA_DESCRIPTIONS


class AIService:
    """Сервис для взаимодействия с AI-моделью: генерация ответов, маршрутизация запросов и анализ данных."""

    def __init__(self):
        self._pipe = None

    @st.cache_resource
    def _load_model(_self):
        """
        Загружает и кэширует языковую модель и токенизатор.
        
        Возвращает:
            Pipeline для генерации текста с помощью HuggingFace Transformers.
        """
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
        """
        Получает кэшированный пайплайн модели. Загружает модель, если ещё не была загружена.
        
        Возвращает:
            Готовый pipeline генерации текста.
        """
        if self._pipe is None:
            self._pipe = self._load_model()
        return self._pipe

    def generate_response(self, messages: List[Dict[str, str]],
                          max_tokens: int = None, temperature: float = None) -> str:
        """
        Генерирует ответ от AI-модели на основе истории сообщений.
        
        Аргументы:
            messages (List[Dict[str, str]]): История сообщений в формате ChatML.
            max_tokens (int, optional): Максимальное количество токенов в ответе.
            temperature (float, optional): Параметр генерации
        
        Возвращает:
            Сгенерированный текст (str).
        """
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
        """
        Определяет намерение пользователя по запросу: анализ отчетов, документация или общий вопрос.
        
        Аргументы:
            user_query (str): Ввод пользователя.
        
        Возвращает:
            Строка: 'reports_analysis' | 'documentation_search' | 'general_question'
        """
        try:
            pipe = get_model_pipe()
            
            system_prompt = """Ты - специалист по анализу намерений пользователей в системе анализа нефтегазовых данных.
            
            Твоя задача - определить, хочет ли пользователь:
            1. АНАЛИЗ ОТЧЕТОВ (reports_analysis) - когда пользователь хочет проанализировать конкретные данные из отчетов
            2. ДОКУМЕНТАЦИЮ (documentation_search) - когда пользователь ищет информацию о работе системы
            3. ОБЩИЙ ВОПРОС (general_question) - когда пользователь задает общий вопрос
            
            ПРИЗНАКИ ЗАПРОСА НА АНАЛИЗ ОТЧЕТОВ:
            - Упоминание конкретных показателей: дебит, добыча, плотность, КВЧ, газ, утилизация, потери
            - Упоминание скважин, месторождений, бригад, цехов
            - Запросы на сравнение, анализ, статистику по производственным данным
            - Упоминание планов работы, ремонта, бурения, замеров
            - Просьбы показать данные, построить графики, проанализировать показатели
            - Вопросы о конкретных периодах работы, эффективности, отклонениях
            
            ПРИЗНАКИ ЗАПРОСА НА ДОКУМЕНТАЦИЮ:
            - Запросы инструкций и объяснений для настройки функционала системы
            - Вопросы о функциональности системы и об особенностях её работы
            - Вопросы о назначении элементов интерфейса системы
            - Просьбы помочь с настройкой или использованием системы
            - Вопросы типа "как сделать", "где найти", "как настроить" относительно системы
            - Запросы руководств, инструкций, документации
            - Вопросы о возможностях и ограничениях системы
            - Вопросы со словами: "как пользоваться", "инструкция", "настройка", "интерфейс", "функция системы"
            
            ПРИЗНАКИ ОБЩЕГО ВОПРОСА:
            - Общие вопросы о нефтегазовой отрасли без запроса конкретных данных
            - Вопросы о терминологии, определениях (не связанных с системой)
            - Просьбы объяснить процессы без анализа данных
            - Приветствия, благодарности, общение
            - Теоретические вопросы
            
            ОТВЕЧАЙ ТОЛЬКО: "reports_analysis", "documentation_search" или "general_question"
            """
            
            user_prompt = f"""Проанализируй следующий запрос пользователя и определи его намерение:
    
            "{user_query}"
            
            Ответь только одним из вариантов:
            - reports_analysis (если пользователь хочет анализировать отчеты/данные)
            - documentation_search (если пользователь ищет документацию или помощь по системе)
            - general_question (если это общий вопрос)
            """
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            generation_args = {
                "max_new_tokens": 50,  
                "return_full_text": False,
                "temperature": 0.0,
                "do_sample": False,
            }
            
            output = pipe(messages, **generation_args)
            response = output[0]['generated_text'].strip().lower()
            
            print(f"Мастер-роутер получил ответ от модели: '{response}'")
            
            if "documentation_search" in response:
                print("Определено как запрос документации")
                return "documentation_search"
            elif "reports_analysis" in response:
                print("Определено как запрос на анализ отчетов")
                return "reports_analysis"
            elif "general_question" in response:
                print("Определено как общий вопрос")
                return "general_question"
            else:
                print(f"Неожиданный ответ мастер-роутера: '{response}'. Анализируем ключевые слова.")
                
                doc_keywords = ["как", "инструкция", "настройка", "интерфейс", "функция", "система", 
                               "пользоваться", "настроить", "где найти", "руководство", "документация"]
                
                report_keywords = ["дебит", "добыча", "скважина", "газ", "нефть", "анализ", "график", 
                                  "показать", "данные", "отчет", "статистика"]
                
                query_lower = user_query.lower()
                
                doc_score = sum(1 for word in doc_keywords if word in query_lower)
                report_score = sum(1 for word in report_keywords if word in query_lower)
                
                if doc_score > report_score and doc_score > 0:
                    print(f"Fallback: определено как документация (score: {doc_score})")
                    return "documentation_search"
                elif report_score > 0:
                    print(f"Fallback: определено как анализ отчетов (score: {report_score})")
                    return "reports_analysis"
                else:
                    print("Fallback: определено как общий вопрос")
                    return "general_question"
                
        except Exception as e:
            print(f"Ошибка в мастер-роутере: {str(e)}")
            return "general_question"


    def decompose_query_for_reports(self, original_query: str, selected_report_ids: List[str]) -> Dict[str, str]:
        """
        Разбивает общий вопрос пользователя на специализированные под каждый выбранный отчет.
        
        Аргументы:
            original_query (str): Исходный пользовательский запрос.
            selected_report_ids (List[str]): Идентификаторы выбранных отчетов.
        
        Возвращает:
            Dict[str, str]: Словарь вида {report_id: уточнённый вопрос}
        """
        try:
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

            specific_queries = {}
            for line in response_text.split('\n'):
                line = line.strip()
                if ':' in line and any(report_id in line for report_id in selected_report_ids):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        report_key = parts[0].strip()
                        query = parts[1].strip()

                        if query.startswith('[') and query.endswith(']'):
                            query = query[1:-1]
                        if query.startswith('"') and query.endswith('"'):
                            query = query[1:-1]

                        if "базовый" in query.lower():
                            query = f"Проведи обзорный анализ данных по теме: {original_query}"

                        specific_queries[report_key] = query

            for report_id in selected_report_ids:
                if report_id not in specific_queries:
                    specific_queries[report_id] = f"Проведи анализ данных в контексте вопроса: {original_query}"

            return specific_queries

        except Exception as e:
            print(f"Ошибка при декомпозиции вопроса: {str(e)}")
            return {report_id: original_query for report_id in selected_report_ids}

    def generate_general_response(self, user_input: str) -> str:
        """
        Генерирует развернутый ответ на общий вопрос пользователя, не связанный с отчетами или документацией.
        
        Аргументы:
            user_input (str): Ввод пользователя.
        
        Возвращает:
            Ответ в виде строки.
        """
        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS["ai_assistant"]},
            {"role": "user", "content": user_input}
        ]

        return self.generate_response(messages, max_tokens=1000, temperature=0.0)

    def generate_documentation_response(self, query: str, doc_results: List[Dict]) -> str:
        """Генерирует ответ на основе найденной документации"""
        if not doc_results:
            return "К сожалению, я не нашел релевантной информации в документации по вашему запросу. Попробуйте переформулировать вопрос или обратитесь к администратору системы."

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
        """
        Генерирует ответ по пользовательскому запросу на основе найденных документов.
        
        Аргументы:
            query (str): Вопрос пользователя.
            doc_results (List[Dict]): Найденные фрагменты документации (содержат ключ 'content').
        
        Возвращает:
            Ответ на основе документации или сообщение об отсутствии результатов.
        """
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

            return self.generate_response(messages, max_tokens=6000, temperature=0.0)

        except Exception as e:
            return f"Не удалось сгенерировать сводный анализ: {str(e)}"