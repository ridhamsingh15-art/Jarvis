"""AMOLED theme preset — pure black for OLED displays."""

from gui.themes.theme import Theme

AMOLED_THEME = Theme(
    name="AMOLED",
    # Backgrounds
    background="#000000",
    surface="#0a0a0a",
    surface_alt="#111111",
    sidebar="#000000",
    # Borders
    border="#1a1a1a",
    border_light="#141414",
    # Text
    text="#f0f0f0",
    text_secondary="#b3b3b3",
    text_muted="#666666",
    # Accent
    accent="#6d9fff",
    accent_hover="#93b8ff",
    accent_muted="rgba(109,159,255,0.12)",
    # Bubbles
    user_bubble="#0d1f3c",
    bot_bubble="#0a0a0a",
    error_bubble="rgba(248,81,73,0.08)",
    system_bubble="rgba(102,102,102,0.06)",
    # Status
    success="#4ade80",
    warning="#fbbf24",
    error="#f87171",
    # Input
    input_bg="#000000",
    input_border="#1a1a1a",
    # Cards
    card_bg="#0a0a0a",
    card_border="#1a1a1a",
    # Misc
    scrollbar_bg="transparent",
    scrollbar_handle="#1a1a1a",
    hover_overlay="rgba(255,255,255,0.04)",
    shadow="rgba(0,0,0,0.5)",
)
