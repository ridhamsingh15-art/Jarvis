"""Dark neon theme preset for the JARVIS control center."""

from gui.themes.theme import Theme

DARK_THEME = Theme(
    name="Dark",
    # Backgrounds
    background="#080D14",
    surface="#0C1420",
    surface_alt="#101D2A",
    sidebar="#080D14",
    # Borders
    border="#172B3D",
    border_light="#203548",
    # Text
    text="#E7F7FF",
    text_secondary="#BED0DD",
    text_muted="#8298AA",
    # Accent
    accent="#00D9FF",
    accent_hover="#57E7FF",
    accent_muted="rgba(0,217,255,0.13)",
    # Bubbles
    user_bubble="#0D2A3A",
    bot_bubble="#0C1420",
    error_bubble="rgba(255,102,122,0.10)",
    system_bubble="rgba(130,152,170,0.08)",
    # Status
    success="#20DCA0",
    warning="#FFC857",
    error="#FF667A",
    # Input
    input_bg="#080D14",
    input_border="#244052",
    # Cards
    card_bg="#0C1420",
    card_border="#172B3D",
    # Misc
    scrollbar_bg="transparent",
    scrollbar_handle="#244052",
    hover_overlay="rgba(0,217,255,0.07)",
    shadow="rgba(0,0,0,0.36)",
)
