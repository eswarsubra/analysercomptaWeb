from nicegui import ui
from typing import Callable


def header():
    """Application header with navigation and theme toggle."""
    with ui.header().classes(
        'bg-gradient-to-r from-blue-700 to-indigo-800 text-white items-center justify-between px-6 shadow-lg'
    ):
        # Logo and title
        with ui.row().classes('items-center gap-3'):
            ui.image('/static/isotipo-preferente-color_positivo.png').classes('w-9 h-9')
            ui.label('AnalyzerCompta').classes('text-xl font-bold tracking-wide')

        # Navigation items
        with ui.row().classes('items-center gap-2'):
            # Dashboard - direct link
            _nav_item('Dashboard', 'dashboard', '/')

            # Supplier dropdown menu
            _nav_dropdown('Supplier', 'business', [
                ('Suppliers', 'store', '/suppliers'),
                ('Products', 'inventory', '/products'),
                ('Factures', 'receipt_long', '/factures'),
                ('Review Pending', 'rate_review', '/review'),
            ])

            # Transactions dropdown menu
            _nav_dropdown('Transactions', 'account_balance', [
                ('View Transactions', 'list_alt', '/transactions'),
                ('Explore Transactions', 'explore', '/transactions/explore'),
            ])

            # Sales dropdown menu
            _nav_dropdown('Sales', 'point_of_sale', [
                ('Explore Sales', 'explore', '/sales/explore'),
            ])

        # Theme toggle
        with ui.row().classes('items-center'):
            dark_mode = ui.dark_mode()
            ui.button(icon='dark_mode', on_click=dark_mode.toggle).props('flat round dense').classes(
                'hover:bg-white/20 transition-colors'
            )


def _nav_item(label: str, icon: str, path: str, highlight: bool = False):
    """Create a navigation item for the top bar."""
    props = 'flat dense'
    classes = 'text-white hover:bg-white/20 rounded-lg transition-colors duration-150'
    if highlight:
        classes += ' bg-amber-600'

    ui.button(
        label,
        icon=icon,
        on_click=lambda: ui.navigate.to(path)
    ).props(props).classes(classes)


def _nav_dropdown(label: str, icon: str, items: list[tuple[str, str, str]]):
    """Create a dropdown navigation menu.

    Args:
        label: Menu button label
        icon: Menu button icon
        items: List of tuples (label, icon, path) for menu items
    """
    with ui.button(label, icon=icon).props('flat dense dropdown-icon="expand_more"').classes(
        'text-white hover:bg-white/20 rounded-lg transition-colors duration-150'
    ):
        with ui.menu().props('transition-show="jump-down" transition-hide="jump-up"').classes(
            'rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 '
            'bg-white dark:bg-gray-800 min-w-48'
        ):
            if items:
                for item_label, item_icon, item_path in items:
                    with ui.menu_item(on_click=lambda p=item_path: ui.navigate.to(p)).classes(
                        'hover:bg-blue-50 dark:hover:bg-gray-700 rounded-md mx-1 my-0.5 '
                        'transition-colors duration-150'
                    ):
                        with ui.row().classes('items-center gap-3 px-2 py-1'):
                            ui.icon(item_icon).classes('text-blue-600 dark:text-blue-400 text-lg')
                            ui.label(item_label).classes('text-gray-700 dark:text-gray-200 font-medium')
            else:
                with ui.menu_item().props('disable').classes('mx-1'):
                    with ui.row().classes('items-center gap-3 px-2 py-1'):
                        ui.icon('hourglass_empty').classes('text-gray-400 text-lg')
                        ui.label('Coming soon...').classes('text-gray-400 italic')


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
