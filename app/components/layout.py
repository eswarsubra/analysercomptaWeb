from nicegui import ui
from typing import Callable


def header():
    """Application header with navigation and theme toggle."""
    with ui.header().classes('bg-primary text-white items-center justify-between px-4'):
        # Logo and title
        with ui.row().classes('items-center gap-2'):
            ui.image('/static/isotipo-preferente-color_positivo.png').classes('w-8 h-8')
            ui.label('AnalyzerCompta').classes('text-lg font-bold')

        # Navigation items
        with ui.row().classes('items-center gap-1'):
            _nav_item('Dashboard', 'dashboard', '/')
            _nav_item('Suppliers', 'business', '/suppliers')
            _nav_item('Products', 'inventory', '/products')
            _nav_item('Factures', 'receipt_long', '/factures')
            ui.separator().props('vertical').classes('mx-2 bg-white/30')
            _nav_item('Review Pending', 'rate_review', '/review', highlight=True)

        # Theme toggle
        with ui.row().classes('items-center'):
            dark_mode = ui.dark_mode()
            ui.button(icon='dark_mode', on_click=dark_mode.toggle).props('flat round dense')


def _nav_item(label: str, icon: str, path: str, highlight: bool = False):
    """Create a navigation item for the top bar."""
    props = 'flat dense'
    classes = 'text-white'
    if highlight:
        classes += ' bg-amber-600'

    ui.button(
        label,
        icon=icon,
        on_click=lambda: ui.navigate.to(path)
    ).props(props).classes(classes)


def layout(title: str = ''):
    """
    Main layout wrapper for pages.
    Usage:
        @ui.page('/mypage')
        def my_page():
            with layout('My Page Title'):
                # page content here
    """
    class LayoutContext:
        def __enter__(self):
            header()
            self.container = ui.column().classes('p-4 w-full')
            if title:
                with self.container:
                    ui.label(title).classes('text-2xl font-bold mb-4 text-gray-800 dark:text-gray-200')
            return self.container.__enter__()

        def __exit__(self, *args):
            return self.container.__exit__(*args)

    return LayoutContext()
