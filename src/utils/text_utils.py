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
    """
    Выполняет сгенерированный Python-код с возможностью использования matplotlib и pandas,
    а также безопасно обрабатывает ошибки и перехватывает текстовый вывод.
    
    Если в коде используется `plt.show()`, он будет заменен на `plt.savefig()` с уникальным именем PNG-файла.
    
    Аргументы:
        code (str): Сырый Python-код, содержащий команды визуализации и анализа.
        target_df (Optional[pd.DataFrame]): DataFrame, доступный в контексте исполнения под именем `df`.
    
    Возвращает:
        Tuple[str, Optional[str], str]:
            - Стандартный текстовый вывод (например, из `print()`).
            - Путь к сохраненному графику (если он был создан), иначе None.
            - Модифицированный код, с учетом преобразований (например, подстановки `plt.savefig()`).
    """

    output_buffer = io.StringIO()

    has_plot = False
    plot_path = None

    try:
        if "plt.show()" in code:
            has_plot = True

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            unique_plot_name = f"plot_{timestamp}_{unique_id}.png"

            if "plt.figure(" not in code:
                code = "plt.figure(figsize=(10, 6))\n" + code

            code = code.replace("plt.show()",
                                f"plt.tight_layout()\nplt.savefig('{unique_plot_name}', dpi=150, bbox_inches='tight')")
            plot_path = unique_plot_name

        local_vars = {
            'df': target_df,
            'pd': pd,
            'plt': plt,
            'np': np
        }

        indented_code = code.strip()
        if not indented_code:
            indented_code = "pass"

        safe_code = "try:\n"
        for line in indented_code.splitlines():
            safe_code += f"    {line}\n"
        safe_code += "except Exception as e:\n"
        safe_code += "    print(f\"Ошибка при выполнении анализа: {str(e)}\")\n"

        with redirect_stdout(output_buffer):
            exec(safe_code, local_vars)

        output_text = output_buffer.getvalue()

        if has_plot and plot_path and os.path.exists(plot_path) and "Ошибка" not in output_text:
            pass
        else:
            plot_path = None

        return output_text, plot_path, code

    except Exception as e:
        return f"Ошибка при выполнении кода:\n{str(e)}", None, code