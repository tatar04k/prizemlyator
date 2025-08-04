"""Сервис для поиска в Elasticsearch"""
import streamlit as st
from elasticsearch import Elasticsearch
from typing import List, Dict, Optional
from config import config
from src.constants import ES_ID_TO_REPORT
from src.models import PREDEFINED_REPORTS, SearchResult, DocumentResult


class SearchService:
    """Сервис для работы с Elasticsearch"""

    def __init__(self):
        self._es_client = None

    def get_client(self) -> Optional[Elasticsearch]:
        """Получает клиент Elasticsearch с кешированием"""
        if self._es_client is None:
            try:
                self._es_client = Elasticsearch(hosts=config.ES_HOST, verify_certs=False)
                # Проверяем подключение
                if not self._es_client.ping():
                    st.warning("⚠️ Не удается подключиться к Elasticsearch. Используются локальные данные.")
                    self._es_client = None
            except Exception as e:
                st.warning(f"⚠️ Ошибка подключения к Elasticsearch: {str(e)}. Используются локальные данные.")
                self._es_client = None
        return self._es_client

    def search_reports(self, query: str) -> List[str]:
        """Сбалансированный поиск по всем полям отчетов"""
        try:
            es = self.get_client()
            if es is None:
                print("Elasticsearch недоступен")
                return []

            if not es.indices.exists(index=config.ES_INDEX):
                print(f"Индекс {config.ES_INDEX} не существует")
                return []

            # Проверяем существующие документы
            existing_docs = []
            known_ids = ['oil_event', 'chess_rep', 'measure_rep', 'gaz_rep']

            for doc_id in known_ids:
                try:
                    response = es.get(index=config.ES_INDEX, id=doc_id)
                    if response['found']:
                        existing_docs.append(doc_id)
                except Exception:
                    continue

            if not existing_docs:
                print("В Elasticsearch не найдено документов")
                return []

            # Поисковый запрос
            search_body = {
                "query": {
                    "bool": {
                        "must": [
                            {"terms": {"_id": existing_docs}}
                        ],
                        "should": [
                                      {
                                          "match": {
                                              "report_description": {
                                                  "query": query,
                                                  "operator": "or",
                                                  "boost": 3.0
                                              }
                                          }
                                      },
                                      {
                                          "match": {
                                              "searchable_content": {
                                                  "query": query,
                                                  "operator": "or",
                                                  "boost": 4.0
                                              }
                                          }
                                      },
                                      {
                                          "match": {
                                              "tags": {
                                                  "query": query,
                                                  "operator": "or",
                                                  "boost": 3.5
                                              }
                                          }
                                      },
                                      {
                                          "multi_match": {
                                              "query": query,
                                              "fields": [
                                                  "searchable_content^3",
                                                  "report_description^3",
                                                  "tags^2"
                                              ],
                                              "type": "best_fields",
                                              "operator": "or"
                                          }
                                      },
                                      {
                                          "wildcard": {
                                              "searchable_content": {
                                                  "value": f"*{query.lower()}*",
                                                  "boost": 2.0
                                              }
                                          }
                                      }
                                  ] + [
                                      {
                                          "wildcard": {
                                              "searchable_content": {
                                                  "value": f"*{word.lower()}*",
                                                  "boost": 1.5
                                              }
                                          }
                                      } for word in query.split() if len(word) > 2
                                  ] + [
                                      {
                                          "match": {
                                              "searchable_content": {
                                                  "query": query,
                                                  "fuzziness": "AUTO",
                                                  "boost": 1.0
                                              }
                                          }
                                      }
                                  ],
                        "minimum_should_match": 1
                    }
                },
                "size": len(existing_docs),
                "_source": ["_id", "searchable_content", "report_description", "tags"],
                "sort": [
                    {"_score": {"order": "desc"}},
                ]
            }

            print(f"Поиск для запроса: '{query}' среди документов: {existing_docs}")

            response = es.search(index=config.ES_INDEX, body=search_body)

            # Обработка результатов
            results = []
            for hit in response['hits']['hits']:
                doc_id = hit['_id']
                score = hit['_score']
                source = hit.get('_source', {})

                results.append({
                    'id': doc_id,
                    'score': score,
                    'title': source.get('report_title', ''),
                    'description': source.get('report_description', ''),
                    'tags': source.get('tags', [])
                })

            # Возвращаем отсортированные ID
            results.sort(key=lambda x: x['score'], reverse=True)
            final_ids = [result['id'] for result in results]

            return final_ids

        except Exception as e:
            print(f"❌ Ошибка поиска: {str(e)}")
            return []

    def search_documentation(self, query: str) -> List[DocumentResult]:
        """Поиск в документации через Elasticsearch"""
        try:
            es = self.get_client()
            if es is None:
                print("Elasticsearch недоступен для поиска документации")
                return []

            if not es.indices.exists(index=config.DOC_INDEX):
                print(f"Индекс документации {config.DOC_INDEX} не существует")
                return []

            # Поисковый запрос для документации
            search_body = {
                "query": {
                    "bool": {
                        "should": [
                            {
                                "match": {
                                    "attachment.content": {
                                        "query": query,
                                        "operator": "or",
                                        "boost": 2.0
                                    }
                                }
                            },
                            {
                                "match": {
                                    "attachment.content": {
                                        "query": query,
                                        "fuzziness": "AUTO",
                                        "boost": 1.0
                                    }
                                }
                            },
                            {
                                "wildcard": {
                                    "attachment.content": {
                                        "value": f"*{query.lower()}*",
                                        "boost": 1.5
                                    }
                                }
                            }
                        ],
                        "minimum_should_match": 1
                    }
                },
                "size": 3,
                "_source": ["attachment.content"],
                "sort": [{"_score": {"order": "desc"}}]
            }

            print(f"Поиск документации для запроса: '{query}'")

            response = es.search(index=config.DOC_INDEX, body=search_body)

            results = []
            for hit in response['hits']['hits']:
                content = hit.get('_source', {}).get('attachment', {}).get('content', '')
                if content:
                    results.append(DocumentResult(
                        score=hit['_score'],
                        content=content
                    ))

            print(f"Найдено {len(results)} документов в документации")
            return results

        except Exception as e:
            print(f"Ошибка поиска в документации: {str(e)}")
            return []

    def get_ordered_report_options(self, user_query: str) -> List[Dict[str, str]]:
        """Возвращает отчеты с мягким поиском и fallback"""
        try:
            print(f"Ищем отчеты для запроса: '{user_query}'")

            # Основной поиск
            relevant_ids = self.search_reports(user_query)

            # Если основной поиск не дал результатов, пробуем fallback
            if not relevant_ids:
                print("Основной поиск не дал результатов, пробуем fallback")
                relevant_ids = self._fallback_soft_search(user_query)

            if not relevant_ids:
                print("Не найдено релевантных отчетов")
                return []

            # Маппинг на отчеты
            ordered_reports = []
            for es_id in relevant_ids:
                if es_id in ES_ID_TO_REPORT:
                    report_id = ES_ID_TO_REPORT[es_id]
                    for report in PREDEFINED_REPORTS:
                        if report['id'] == report_id:
                            ordered_reports.append(report.copy())
                            break

            print(f"Найдено {len(ordered_reports)} отчетов: {[r['id'] for r in ordered_reports]}")
            return ordered_reports

        except Exception as e:
            print(f"Ошибка в get_ordered_report_options: {str(e)}")
            return []

    def _fallback_soft_search(self, query: str) -> List[str]:
        """Очень мягкий fallback поиск"""
        try:
            es = self.get_client()
            if es is None:
                return ['oil_event', 'chess_rep', 'measure_rep', 'gaz_rep']

            words = [word.lower() for word in query.split() if len(word) > 1]

            if not words:
                return ['oil_event', 'chess_rep', 'measure_rep', 'gaz_rep']

            existing_docs = ['oil_event', 'chess_rep', 'measure_rep', 'gaz_rep']

            search_body = {
                "query": {
                    "bool": {
                        "must": [{"terms": {"_id": existing_docs}}],
                        "should": [
                                      {
                                          "wildcard": {
                                              "report_title": f"*{word}*"
                                          }
                                      } for word in words
                                  ] + [
                                      {
                                          "wildcard": {
                                              "tags": f"*{word}*"
                                          }
                                      } for word in words
                                  ],
                        "minimum_should_match": 1
                    }
                },
                "size": len(existing_docs),
                "_source": ["_id"]
            }

            response = es.search(index=config.ES_INDEX, body=search_body)
            found_ids = [hit['_id'] for hit in response['hits']['hits']]

            if found_ids:
                print(f"Fallback поиск нашел: {found_ids}")
                return found_ids
            else:
                print("Даже fallback поиск не дал результатов, возвращаем все")
                return existing_docs

        except Exception as e:
            print(f"Ошибка fallback поиска: {str(e)}")
            return ['oil_event', 'chess_rep', 'measure_rep', 'gaz_rep']