from django.core.management.base import BaseCommand

from warehouse.services import reset_all_stock


class Command(BaseCommand):
    help = 'Обнулить все остатки на складе и очистить журнал движений'

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Подтвердить обнуление без интерактивного вопроса',
        )
        parser.add_argument(
            '--keep-movements',
            action='store_true',
            help='Не удалять записи журнала движений склада',
        )

    def handle(self, *args, **options):
        if not options['yes']:
            self.stderr.write(
                'Добавьте флаг --yes, чтобы подтвердить полное обнуление остатков.'
            )
            return

        result = reset_all_stock(clear_movements=not options['keep_movements'])
        self.stdout.write(
            self.style.SUCCESS(
                f'Обнулено остатков: {result["stocks_zeroed"]}. '
                f'Удалено движений: {result["movements_deleted"]}.'
            )
        )
