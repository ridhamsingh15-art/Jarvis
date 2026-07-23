"""Dark theme preset — GitHub Dark-inspired palette."""

from gui.themes.theme import Theme

DARK_THEME = Theme(
    name="Dark",
    # Backgrounds
    background="#0d1117",
    surface="#161b22",
    surface_alt="#1c2333",
    sidebar="#0d1117",
    # Borders
    border="#30363d",
    border_light="#21262d",
    # Text
    text="#e6edf3",
    text_secondary="#c9d1d9",
    text_muted="#8b949e",
    # Accent
    accent="#58a6ff",
    accent_hover="#79c0ff",
    accent_muted="rgba(88,166,255,0.15)",
    # Bubbles
    user_bubble="#1a3a5c",
    bot_bubble="#161b22",
    error_bubble="rgba(248,81,73,0.1)",
    system_bubble="rgba(139,148,158,0.08)",
    # Status
    success="#3fb950",
    warning="#d29922",
    error="#f85149",
    # Input
    input_bg="#0d1117",
    input_border="#30363d",
    # Cards
    card_bg="#161b22",
    card_border="#30363d",
    # Misc
    scrollbar_bg="transparent",
    scrollbar_handle="#30363d",
    hover_overlay="rgba(177,186,196,0.08)",
    shadow="rgba(0,0,0,0.3)",
)
