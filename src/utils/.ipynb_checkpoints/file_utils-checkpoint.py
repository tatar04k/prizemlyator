"""Утилиты для работы с файлами"""
import os
from typing import List


def cleanup_old_plots(max_files: int = 50):
    """Очищает старые файлы графиков, оставляя только последние max_files"""
    try:
        # Получаем все файлы графиков в текущей директории
        plot_files = [f for f in os.listdir('.') if f.startswith('plot_') and f.endswith('.png')]

        # Если файлов больше чем max_files, удаляем самые старые
        if len(plot_files) > max_files:
            # Сортируем по времени создания
            plot_files.sort(key=lambda x: os.path.getctime(x))

            # Удаляем самые старые файлы
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
    """Получает список файлов в директории с указанными расширениями"""
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
    """Создает директорию если она не существует"""
    if not os.path.exists(directory):
        os.makedirs(directory)