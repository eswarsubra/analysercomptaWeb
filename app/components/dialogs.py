from nicegui import ui
from typing import Callable, Optional


def confirm_dialog(title: str, message: str, on_confirm: Callable, on_cancel: Optional[Callable] = None):
    """
    Create a confirmation dialog.
    Returns the dialog object so it can be opened with dialog.open()
    """
    with ui.dialog() as dialog, ui.card().classes('p-4'):
        ui.label(title).classes('text-lg font-semibold')
        ui.label(message).classes('text-gray-600 dark:text-gray-400 my-4')

        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=lambda: _handle_cancel(dialog, on_cancel)).props('flat')
            ui.button('Confirm', on_click=lambda: _handle_confirm(dialog, on_confirm)).props('color=primary')

    return dialog


def _handle_confirm(dialog, callback):
    dialog.close()
    if callback:
        callback()


def _handle_cancel(dialog, callback):
    dialog.close()
    if callback:
        callback()


def form_dialog(title: str, fields: list[dict], on_submit: Callable, on_cancel: Optional[Callable] = None):
    """
    Create a form dialog.

    fields: list of dicts with keys:
        - name: field name
        - label: display label
        - type: 'text', 'number', 'select', 'textarea'
        - value: initial value
        - options: for select type, list of options
        - required: bool

    Returns (dialog, get_values_func) tuple
    """
    field_refs = {}

    with ui.dialog() as dialog, ui.card().classes('p-4 min-w-96'):
        ui.label(title).classes('text-lg font-semibold mb-4')

        for field in fields:
            field_name = field['name']
            field_label = field.get('label', field_name)
            field_type = field.get('type', 'text')
            field_value = field.get('value', '')
            field_options = field.get('options', [])
            field_required = field.get('required', False)

            if field_type == 'text':
                field_refs[field_name] = ui.input(
                    label=field_label,
                    value=field_value
                ).classes('w-full')
                if field_required:
                    field_refs[field_name].props('required')

            elif field_type == 'number':
                field_refs[field_name] = ui.number(
                    label=field_label,
                    value=field_value
                ).classes('w-full')

            elif field_type == 'select':
                field_refs[field_name] = ui.select(
                    label=field_label,
                    options=field_options,
                    value=field_value
                ).classes('w-full')

            elif field_type == 'textarea':
                field_refs[field_name] = ui.textarea(
                    label=field_label,
                    value=field_value
                ).classes('w-full')

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button('Cancel', on_click=lambda: _handle_cancel(dialog, on_cancel)).props('flat')
            ui.button('Save', on_click=lambda: _handle_form_submit(dialog, field_refs, on_submit)).props('color=primary')

    def get_values():
        return {name: ref.value for name, ref in field_refs.items()}

    return dialog, get_values


def _handle_form_submit(dialog, field_refs, callback):
    values = {name: ref.value for name, ref in field_refs.items()}
    dialog.close()
    if callback:
        callback(values)
