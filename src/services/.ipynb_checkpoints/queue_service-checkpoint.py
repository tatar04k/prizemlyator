"""Сервис управления очередью запросов"""
import queue
import threading
import time
import uuid
from datetime import datetime
from typing import Dict, Tuple, Any, Optional
from src.models import QueueItem


class QueueService:
    """Сервис для управления очередью обработки запросов"""

    def __init__(self):
        self.queue = queue.Queue()
        self.processing_status = {}
        self.current_processing = None
        self.worker_thread = None
        self.is_processing = False

    def add_to_queue(self, session_id: str, request_data: Dict[str, Any]) -> str:
        """Добавляет запрос в очередь"""
        request_id = str(uuid.uuid4())[:8]
        queue_item = QueueItem(
            request_id=request_id,
            session_id=session_id,
            timestamp=datetime.now(),
            request_data=request_data,
            status='waiting'
        )

        self.queue.put(queue_item.__dict__)
        self.processing_status[request_id] = queue_item.__dict__

        # Запускаем обработчик, если он не запущен
        if not self.is_processing:
            self.start_worker()

        return request_id

    def get_queue_position(self, request_id: str) -> Tuple[int, str]:
        """Возвращает позицию в очереди"""
        if request_id not in self.processing_status:
            return -1, "Запрос не найден"

        status = self.processing_status[request_id]
        if status['status'] == 'processing':
            return 0, "Обрабатывается"
        elif status['status'] == 'completed':
            return -1, "Завершено"
        elif status['status'] == 'error':
            return -1, "Ошибка"

        # Подсчитываем позицию в очереди
        position = 0
        queue_list = list(self.queue.queue)

        for i, item in enumerate(queue_list):
            if item['request_id'] == request_id:
                position = i + 1
                break

        return position, f"В очереди (позиция {position})"

    def start_worker(self):
        """Запускает обработчик очереди"""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.is_processing = True
            self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
            self.worker_thread.start()

    def _process_queue(self):
        """Обрабатывает очередь в отдельном потоке"""
        while True:
            try:
                # Получаем следующий запрос
                queue_item = self.queue.get(timeout=30)  # Ждем 30 секунд

                self.current_processing = queue_item['request_id']
                self.processing_status[queue_item['request_id']]['status'] = 'processing'

                # Обрабатываем запрос
                result = self._execute_request(queue_item)

                # Помечаем как завершенный
                self.processing_status[queue_item['request_id']]['status'] = 'completed'
                self.processing_status[queue_item['request_id']]['result'] = result
                self.current_processing = None

                self.queue.task_done()

            except queue.Empty:
                # Очередь пуста, останавливаем обработчик
                self.is_processing = False
                break
            except Exception as e:
                # Ошибка обработки
                if 'queue_item' in locals():
                    self.processing_status[queue_item['request_id']]['status'] = 'error'
                    self.processing_status[queue_item['request_id']]['error'] = str(e)
                    self.current_processing = None

    def _execute_request(self, queue_item: Dict[str, Any]) -> Any:
        """Выполняет запрос из очереди"""
        # Импортируем здесь чтобы избежать циклических импортов
        from src.services.ai_service import AIService
        from src.graph.nodes import CodeGeneratorNode

        request_data = queue_item['request_data']
        request_type = request_data['type']

        ai_service = AIService()
        code_generator = CodeGeneratorNode(ai_service)

        # Выполняем различные типы запросов
        if request_type == 'generate_work_plan_code':
            return code_generator.generate_work_plan_code(
                request_data['query'],
                request_data['df_info'],
                request_data.get('selected_option')
            )
        elif request_type == 'generate_drilling_code':
            return code_generator.generate_drilling_code(
                request_data['query'],
                request_data.get('selected_option')
            )
        elif request_type == 'generate_measurement_code':
            return code_generator.generate_measurement_code(
                request_data['query'],
                request_data.get('selected_option')
            )
        elif request_type == 'generate_gas_utilization_code':
            return code_generator.generate_gas_utilization_code(
                request_data['query'],
                request_data.get('selected_option')
            )
        elif request_type == 'generate_final_response':
            return code_generator.generate_final_response(request_data['state'])
        elif request_type == 'generate_documentation_response':
            return ai_service.generate_documentation_response(
                request_data['query'],
                request_data['doc_results']
            )
        else:
            raise ValueError(f"Неизвестный тип запроса: {request_type}")

    def get_result(self, request_id: str) -> Optional[Any]:
        """Получает результат обработки"""
        if request_id in self.processing_status:
            status = self.processing_status[request_id]
            if status['status'] == 'completed':
                return status.get('result')
            elif status['status'] == 'error':
                raise Exception(status.get('error', 'Неизвестная ошибка'))
        return None


# Глобальный экземпляр менеджера очереди
queue_service = QueueService()


def queue_aware_generation(session_id: str, request_type: str, request_data: Dict[str, Any]) -> Any:
    """Функция для постановки в очередь с отображением статуса"""
    import streamlit as st

    # Добавляем в очередь
    request_id = queue_service.add_to_queue(session_id, {
        'type': request_type,
        **request_data
    })

    # Отображаем статус очереди
    status_placeholder = st.empty()
    progress_bar = st.progress(0)

    # Ждем обработки
    start_time = time.time()
    while True:
        position, status_text = queue_service.get_queue_position(request_id)

        if position == -1:
            if "Завершено" in status_text:
                status_placeholder.success("✅ Обработка завершена!")
                progress_bar.progress(100)
                result = queue_service.get_result(request_id)
                break
            elif "Ошибка" in status_text:
                status_placeholder.error("❌ Произошла ошибка при обработке")
                break
            else:
                status_placeholder.info(status_text)
                break
        elif position == 0:
            elapsed = int(time.time() - start_time)
            status_placeholder.info(f"🔄 Ваш запрос обрабатывается... ({elapsed}с)")
            progress_bar.progress(75)
        else:
            status_placeholder.info(f"⏳ Ваша позиция в очереди: {position}")
            # Прогресс на основе позиции
            progress = max(5, min(50, (10 - position) * 10))
            progress_bar.progress(progress)

        time.sleep(1)  # Обновляем каждую секунду

    # Очищаем индикаторы
    status_placeholder.empty()
    progress_bar.empty()

    return result