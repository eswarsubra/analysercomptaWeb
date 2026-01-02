from nicegui import ui


# Status color mapping
STATUS_COLORS = {
    'CLOSED': ('green', 'check_circle'),
    'CREATE PRODUCT': ('blue', 'add_circle'),
    'IGNORE PRODUCT': ('amber', 'warning'),
    'MODIFY PRODUCT': ('orange', 'edit'),
    'MODIFY ITEM': ('purple', 'edit_note'),
    'FULL IGNORE': ('red', 'cancel'),
    'OBSOLETE': ('gray', 'delete'),
    'INCOMPLETE': ('pink', 'error')
}


def status_badge(status: str):
    """Create a colored status badge."""
    color, icon = STATUS_COLORS.get(status, ('gray', 'help'))

    with ui.row().classes('items-center gap-1'):
        ui.icon(icon, size='xs').classes(f'text-{color}-500')
        ui.label(status).classes(f'text-{color}-600 dark:text-{color}-400 text-sm font-medium')


def status_chip(status: str):
    """Create a chip-style status indicator."""
    color, icon = STATUS_COLORS.get(status, ('gray', 'help'))
    ui.chip(status, icon=icon, color=color).props('dense')
