"""Утилиты для обработки текста и выполнения кода"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import io
import os
import uuid
from contextlib import redirect_stdout
from datetime import datetime
from typing import Tuple, Optional


def execute_generated_code(code: str, target_df: Optional[pd.DataFrame] = None) -> Tuple[str, Optional[str], str]:
    """Выполняет сгенерированный код и возвращает результат с уникальным именем файла для графика"""
    # Буфер для перехвата вывода print
    output_buffer = io.StringIO()

    # Флаг, показывающий, был ли вызов plt.show()
    has_plot = False
    plot_path = None

    try:
        # Проверяем, есть ли plt.show() в коде
        if "plt.show()" in code:
            has_plot = True

            # Создаем уникальное имя файла для каждого графика
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            unique_plot_name = f"plot_{timestamp}_{unique_id}.png"

            # Если в коде уже есть plt.figure(), не добавляем новый
            if "plt.figure(" not in code:
                code = "plt.figure(figsize=(10, 6))\n" + code

            # Заменяем plt.show() на сохранение с уникальным именем
            code = code.replace("plt.show()",
                                f"plt.tight_layout()\nplt.savefig('{unique_plot_name}', dpi=150, bbox_inches='tight')")
            plot_path = unique_plot_name

        # Создаем локальный словарь для выполнения кода
        local_vars = {
            'df': target_df,
            'pd': pd,
            'plt': plt,
            'np': np
        }

        # Добавляем обработку ошибок внутри выполняемого кода
        indented_code = code.strip()
        if not indented_code:
            indented_code = "pass"

        # Правильная сборка кода без лишних отступов у try/except
        safe_code = "try:\n"
        for line in indented_code.splitlines():
            safe_code += f"    {line}\n"
        safe_code += "except Exception as e:\n"
        safe_code += "    print(f\"Ошибка при выполнении анализа: {str(e)}\")\n"

        # Выполняем код, перехватывая вывод print
        with redirect_stdout(output_buffer):
            exec(safe_code, local_vars)

        # Получаем текстовый вывод
        output_text = output_buffer.getvalue()

        # Проверяем, что файл действительно создался
        if has_plot and plot_path and os.path.exists(plot_path) and "Ошибка" not in output_text:
            # Файл успешно создан
            pass
        else:
            plot_path = None

        return output_text, plot_path, code

    except Exception as e:
        return f"Ошибка при выполнении кода:\n{str(e)}", None, code