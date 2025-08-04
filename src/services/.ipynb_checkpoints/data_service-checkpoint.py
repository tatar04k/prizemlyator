"""Сервис для работы с данными"""
import pandas as pd
import json
import streamlit as st
from typing import Tuple, Optional
from src.utils.data_loaders import ExcelLoader, ElasticsearchLoader

class DataService:
    """Сервис для загрузки и обработки данных"""

    def __init__(self):
        self.excel_loader = ExcelLoader()
        self.es_loader = ElasticsearchLoader()
        self._cached_data = {}

    def load_work_plan_data(self) -> Tuple[Optional[pd.DataFrame], str]:
        """Загружает данные планов работы"""
        if 'work_plan' in self._cached_data:
            return self._cached_data['work_plan']

        # Сначала пытаемся загрузить из Elasticsearch
        df, message = self.es_loader.extract_table('oil_event')

        if df is not None:
            self._cached_data['work_plan'] = (df, message)
            return df, message

        # Если не получилось, используем локальную загрузку
        st.warning("⚠️ Загружаю данные из локального файла...")
        try:
            excel_file = pd.ExcelFile('шамков.xlsx')
            df = pd.read_excel(excel_file, skiprows=21, nrows=48, usecols='Q:Y')

            self._cached_data['work_plan'] = (df, "DataFrame загружен из локального файла")
            return df, "DataFrame загружен из локального файла"
        except Exception as e:
            # Создаем тестовые данные как fallback
            test_data = self._create_test_work_plan_data()
            df = pd.DataFrame(test_data)

            message = "Загружены тестовые данные (файл и Elasticsearch недоступны)"
            self._cached_data['work_plan'] = (df, message)
            return df, message

    def load_drilling_data(self) -> Tuple[Optional[pd.DataFrame], str]:
        """Загружает данные шахматки проб"""
        if 'drilling' in self._cached_data:
            return self._cached_data['drilling']

        # Сначала пытаемся загрузить из Elasticsearch
        df, message = self.es_loader.extract_table('chess_rep')

        if df is not None:
            self._cached_data['drilling'] = (df, message)
            return df, message

        # Если не получилось, используем локальную загрузку
        st.warning("⚠️ Загружаю данные из локального файла...")
        try:
            df = self.excel_loader.parse_drilling_excel('шамков 3.xlsx')

            if df.empty:
                return None, "Ошибка: получен пустой DataFrame после парсинга"

            message = f"DataFrame загружен из локального файла! Содержит {len(df)} строк с данными о пробах."
            self._cached_data['drilling'] = (df, message)
            return df, message
        except Exception as e:
            return None, f"Ошибка при загрузке файла: {str(e)}"

    def load_measurement_data(self) -> Tuple[Optional[pd.DataFrame], str]:
        """Загружает данные замерной добычи"""
        if 'measurement' in self._cached_data:
            return self._cached_data['measurement']

        # Сначала пытаемся загрузить из Elasticsearch
        df, message = self.es_loader.extract_table('measure_rep')

        if df is not None:
            self._cached_data['measurement'] = (df, message)
            return df, message

        # Если не получилось, используем локальную загрузку
        st.warning("⚠️ Загружаю данные из локального файла...")
        try:
            df = self.excel_loader.parse_measurement_excel('шамков 4.xlsx')

            message = "DataFrame замерной добычи загружен из локального файла!"
            self._cached_data['measurement'] = (df, message)
            return df, message
        except Exception as e:
            return None, f"Ошибка при загрузке файла замерной добычи: {str(e)}"

    def load_gas_utilization_data(self) -> Tuple[Optional[pd.DataFrame], str]:
        """Загружает данные утилизации газа"""
        if 'gas_utilization' in self._cached_data:
            return self._cached_data['gas_utilization']

        # Сначала пытаемся загрузить из Elasticsearch
        df, message = self.es_loader.extract_table('gaz_rep')

        if df is not None:
            self._cached_data['gas_utilization'] = (df, message)
            return df, message

        # Если не получилось, используем локальную загрузку
        st.warning("⚠️ Загружаю данные из локального файла...")
        try:
            df = self.excel_loader.parse_gas_excel('шамков 2.xlsx')

            message = "DataFrame утилизации газа загружен из локального файла!"
            self._cached_data['gas_utilization'] = (df, message)
            return df, message
        except Exception as e:
            return None, f"Ошибка при загрузке файла утилизации газа: {str(e)}"

    def get_data_info(self, data_type: str) -> str:
        """Возвращает информацию о структуре данных"""
        info_map = {
            'work_plan': self._get_work_plan_info(),
            'drilling': self._get_drilling_info(),
            'measurement': self._get_measurement_info(),
            'gas_utilization': self._get_gas_info()
        }
        return info_map.get(data_type, "Неизвестный тип данных")

    def _get_work_plan_info(self) -> str:
        """Возвращает информацию о структуре планов работы"""
        return """
СТРУКТУРА ДАННЫХ ПЛАНОВ РАБОТЫ:
1. "№ п/п" - порядковый номер записи (целое число)
2. "№ скважины, месторождение" - составной идентификатор в формате "[номер скважины] [название месторождения]"
3. "Планируемая дата проведения работ" - временной интервал в формате "DD.MM.YYYY HH:MM-DD.MM.YYYY HH:MM"
4. "Мероприятие" - код и описание работ, например "РП-24 Ремонт запорной арматуры"
5. "Бригада, цех" - информация о бригаде в формате "Бригада №[номер] [название цеха]"
6. "Время простоя, ч" - числовое значение с плавающей точкой
7. "Суточный дебит нефти, Т в сут." - числовое значение с плавающей точкой (в тоннах)
8. "Потери нефти, т" - числовое значение с плавающей точкой (в тоннах)
9. "Примечание" - текстовое поле
"""

    def _get_drilling_info(self) -> str:
        """Возвращает информацию о структуре шахматки проб"""
        return """
СТРУКТУРА ДАННЫХ ШАХМАТКИ ПРОБ:
1. "id" - идентификатор скважины (строка, начинается с '#')
2. "well" - номер скважины (строка)
3. "field" - месторождение (строка)
4. "date" - дата пробы (datetime объект)
5. "plotnost" - значение плотности (строка, может быть "нет" если нет данных)
6. "plotnost_itog" - итог по плотности (строка, может быть "Есть отклонения" или "Нет отклонений")
7. "kvch" - значение КВЧ (Крупно-взвешенные частицы) (строка, может быть "нет" если нет данных)
8. "kvch_itog" - итог по КВЧ (строка, может быть "Есть отклонения" или "Нет отклонений")
"""

    def _get_measurement_info(self) -> str:
        """Возвращает информацию о структуре замерной добычи"""
        return """
СТРУКТУРА ДАННЫХ ЗАМЕРНОЙ ДОБЫЧИ:
1. "Месторождение" - название месторождения нефти (object/string)
2. "Горизонт" - геологический горизонт добычи (object/string)
3. "БЕ" - бизнес-единица (object/string)
4. "№ скв" - номер скважины (object/string)
5. "Бригада" - название бригады и цеха (object/string)
6. "Режим (дебит), Qж, м3/сут" - режимный дебит жидкости (float64)
7. "Режим (дебит), Qн, т/сут" - режимный дебит нефти (float64)
8. "Режим (дебит), %" - обводненность в режиме (float64)
9. "Замерная (дебит до вычета ТО), Qж, м3/сут" - замерный дебит жидкости (float64)
10. "Замерная (дебит до вычета ТО), Qн, т/сут" - замерный дебит нефти (float64)
11. "Факт (дебит), Qж, м3/сут" - фактический дебит жидкости (float64)
12. "Факт (дебит), Qн, т/сут" - фактический дебит нефти (float64)
И другие колонки с отклонениями и коэффициентами.
"""

    def _get_gas_info(self) -> str:
        """Возвращает информацию о структуре утилизации газа"""
        return """
СТРУКТУРА ДАННЫХ УТИЛИЗАЦИИ ГАЗА:
1. "Месяц" - дата в формате "YYYY-MM-DD 00:00:00", хранится как строка (object)
2. "Добыча газа, тыс. м3 План" - плановый объем добычи газа
3. "Добыча газа, тыс. м3 Факт" - фактический объем добычи газа
4. "Добыча газа, тыс. м3 Откл-е" - отклонение от плана
5. "Поставка газа, тыс. м3 БГПЗ Всего План" - плановый объем поставки газа на БГПЗ
6. "Поставка газа, тыс. м3 БГПЗ Всего Факт" - фактический объем поставки газа на БГПЗ
7. "Потери газа, тыс. м3 План" - плановые потери газа
8. "Потери газа, тыс. м3 Факт" - фактические потери газа
И другие колонки с различными направлениями использования газа.
"""

    def _create_test_work_plan_data(self) -> dict:
        """Создает тестовые данные для планов работы"""
        return {
            '№ п/п': range(1, 11),
            '№ скважины, месторождение': [
                '152s2 ДАВЫДОВСКОЕ', '234 СЕВЕРНОЕ', '345s1 ВОСТОЧНОЕ',
                '456 ЮЖНОЕ', '567s3 ЦЕНТРАЛЬНОЕ', '678 ЗАПАДНОЕ',
                '789s2 НОВОЕ', '890 СТАРОЕ', '901s1 КРАЙНЕЕ', '012 ДАЛЬНЕЕ'
            ],
            'Планируемая дата проведения работ': [
                '09.10.2024 09:00-09.10.2024 13:00', '10.10.2024 08:00-10.10.2024 16:00',
                '11.10.2024 10:00-11.10.2024 14:00', '12.10.2024 09:00-12.10.2024 15:00',
                '13.10.2024 07:00-13.10.2024 12:00', '14.10.2024 11:00-14.10.2024 17:00',
                '15.10.2024 08:30-15.10.2024 13:30', '16.10.2024 09:15-16.10.2024 16:15',
                '17.10.2024 10:30-17.10.2024 15:30', '18.10.2024 08:45-18.10.2024 14:45'
            ],
            'Мероприятие': [
                'РП-24 Ремонт запорной арматуры', 'КРС-15 Капитальный ремонт скважины',
                'ТРС-8 Текущий ремонт', 'РП-12 Замена оборудования',
                'КРС-20 Капитальный ремонт', 'ТРС-5 Профилактические работы',
                'РП-18 Ремонт насосного оборудования', 'КРС-25 Капитальный ремонт',
                'ТРС-10 Текущий ремонт', 'РП-30 Ремонт трубопровода'
            ],
            'Бригада, цех': [
                'Бригада №8 ЦДНГ-2', 'Бригада №5 ЦДНГ-1', 'Бригада №12 ЦДНГ-3',
                'Бригада №3 ЦДНГ-1', 'Бригада №15 ЦДНГ-2', 'Бригада №7 ЦДНГ-3',
                'Бригада №9 ЦДНГ-1', 'Бригада №11 ЦДНГ-2', 'Бригада №4 ЦДНГ-3',
                'Бригада №6 ЦДНГ-1'
            ],
            'Время простоя, ч': [4.0, 8.0, 5.0, 6.0, 5.0, 7.0, 5.5, 7.5, 4.5, 6.0],
            'Суточный дебит нефти, Т в сут.': [13.0, 25.5, 18.2, 22.1, 16.8, 28.3, 19.7, 24.0, 15.5, 21.9],
            'Потери нефти, т': [1.1, 4.5, 2.0, 2.9, 1.8, 4.4, 2.4, 4.0, 1.5, 2.8],
            'Примечание': ['нет', 'требуется доп. оборудование', 'нет', 'согласовать с диспетчером',
                        'нет', 'подготовить материалы', 'нет', 'проверить безопасность',
                        'нет', 'координация с соседними скважинами']
        }

    def clear_cache(self):
        """Очищает кеш данных"""
        self._cached_data.clear()

    def get_cached_data_types(self) -> list:
        """Возвращает список типов данных в кеше"""
        return list(self._cached_data.keys())

    def validate_data(self, df: pd.DataFrame, data_type: str) -> bool:
        """Валидирует структуру данных"""
        if df is None or df.empty:
            return False

        required_columns = {
            'work_plan': ['№ п/п', '№ скважины, месторождение', 'Планируемая дата проведения работ'],
            'drilling': ['id', 'well', 'field', 'date'],
            'measurement': ['Месторождение', '№ скв', 'Режим (дебит), Qн, т/сут'],
            'gas_utilization': ['Месяц', 'Добыча газа, тыс. м3 План']
        }

        if data_type not in required_columns:
            return False

        return all(col in df.columns for col in required_columns[data_type])