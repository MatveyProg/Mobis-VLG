#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def _warn_if_not_venv():
    venv_python = Path(__file__).resolve().parent / '.venv' / 'Scripts' / 'python.exe'
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        print(
            'Подсказка: для этого проекта запускайте '
            '.venv\\Scripts\\python manage.py …\n'
            f'Сейчас используется: {sys.executable}',
            file=sys.stderr,
        )


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    _warn_if_not_venv()
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
