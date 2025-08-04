"""Утилиты для работы с файлами"""
import os
from typing import List


def cleanup_old_plots(max_files: int = 50):
    """
    Удаляет старые PNG-файлы графиков из текущей директории, если их больше заданного лимита.
    
    Аргументы:
        max_files (int): Максимальное количество графиков, которое следует оставить. 
                         Остальные будут удалены, начиная с самых старых.
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


def get_file_list(directory: str, extensions: List[str] = None) -> List[str]:
    """
    Возвращает список файлов из указанной директории с заданными расширениями.
    
    Аргументы:
        directory (str): Путь к директории, из которой нужно получить файлы.
        extensions (List[str], optional): Список допустимых расширений файлов (например, ['.png', '.csv']).
                                          Если None, возвращаются все файлы.
    
    Возвращает:
        List[str]: Список путей к найденным файлам.
    """
    if not os.path.exists(directory):
        return []

    files = []
    for file in os.listdir(directory):
        if extensions:
            if any(file.lower().endswith(ext.lower()) for ext in extensions):
                files.append(os.path.join(directory, file))
        else:
            files.append(os.path.join(directory, file))

    return files


def ensure_directory_exists(directory: str):
    """
    Создает указанную директорию, если она еще не существует.
    
    Аргументы:
        directory (str): Путь к создаваемой директории.
    """
    if not os.path.exists(directory):
        os.makedirs(directory)